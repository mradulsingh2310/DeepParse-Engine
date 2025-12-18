"""
Level 3: LLM Semantic Evaluation

Uses AWS Bedrock to perform semantic comparison of field names and options
between model output and source of truth.
"""

from __future__ import annotations

import json
import os

import boto3  # type: ignore[import-untyped]
from botocore.config import Config  # type: ignore[import-untyped]
from botocore.exceptions import ClientError  # type: ignore[import-untyped]
from pydantic import BaseModel

from evaluation.models import (
    SectionEvaluation,
    ValidationError,
)
from src.utils.logger import log, log_usage


class LLMFieldComparison(BaseModel):
    """Result of LLM comparison for a single field."""
    source_field_id: int
    model_field_id: int | None
    name_similarity: float  # 0.0-1.0
    options_similarity: float  # 0.0-1.0
    reasoning: str


class LLMSectionComparison(BaseModel):
    """Result of LLM comparison for a section."""
    source_section_name: str
    model_section_name: str | None
    name_similarity: float  # 0.0-1.0
    fields: list[LLMFieldComparison]


class LLMEvaluationResponse(BaseModel):
    """Structured response from LLM evaluation."""
    sections: list[LLMSectionComparison]
    overall_assessment: str


EVALUATION_PROMPT = """You are an evaluation assistant comparing inspection template JSON outputs. Compare the model output against the source of truth.

## Task
For each field pair, evaluate:
1. **name_similarity** (0.0-1.0): How semantically similar are the field names?
   - 1.0: Same meaning (e.g., "Smoke Detectors" vs "Smoke detectors" = 1.0)
   - 0.8-0.9: Minor wording difference (e.g., "Doors and Locks" vs "Doors and lock" = 0.9)
   - 0.5-0.7: Related but different (e.g., "Electrical Fixtures and Outlets" vs "Elec.fixtures/outlets" = 0.8)
   - 0.0-0.4: Different concepts
   
2. **options_similarity** (0.0-1.0): How similar are the options?
   - 1.0: Same options (case-insensitive)
   - 0.9: Same options, different casing (e.g., "Requires Action" vs "Requires action")
   - 0.5-0.8: Most options match
   - 0.0-0.4: Very different options

3. **reasoning**: Brief explanation (max 50 words)

## Schema Validation Errors Found
{schema_errors}

## Source of Truth (Reference)
{source_json}

## Model Output (To Evaluate)
{model_json}

## Instructions
- Compare each source section with the corresponding model section
- Match fields by semantic similarity, not just position
- If a model section is missing, set name_similarity to 0.0 for all its fields
- Be lenient with abbreviations (e.g., "Elec." = "Electrical", "int." = "interior")
- Consider typos in section names (e.g., "Dinning" vs "Dining" should still score 0.9+)

## Output Format
Return ONLY valid JSON matching this structure (no markdown, no explanation):
{{
  "sections": [
    {{
      "source_section_name": "Section Name",
      "model_section_name": "Model Section Name or null",
      "name_similarity": 0.95,
      "fields": [
        {{
          "source_field_id": 1,
          "model_field_id": 1,
          "name_similarity": 0.95,
          "options_similarity": 0.90,
          "reasoning": "Brief explanation"
        }}
      ]
    }}
  ],
  "overall_assessment": "Brief overall assessment of model quality"
}}
"""


class LLMEvaluator:
    """
    Uses AWS Bedrock to perform semantic evaluation of inspection templates.
    """
    
    def __init__(
        self,
        model_id: str = "anthropic.claude-3-sonnet-20240229-v1:0",
        region: str = "us-east-1",
        timeout: int = 300,
    ):
        """
        Initialize LLM Evaluator.
        
        Args:
            model_id: Bedrock model ID for evaluation (text model preferred)
            region: AWS region
            timeout: Request timeout in seconds
        """
        self.model_id = model_id
        self.region = region
        self.timeout = timeout
        self._client = None
    
    def _get_client(self):
        """Get or create the Bedrock client."""
        if self._client is None:
            profile = os.getenv("AWS_PROFILE")
            region = os.getenv("AWS_REGION", self.region)
            
            bedrock_config = Config(
                read_timeout=self.timeout,
                connect_timeout=30,
                retries={"max_attempts": 2}
            )
            
            try:
                session = boto3.Session(profile_name=profile)
                self._client = session.client(
                    "bedrock-runtime",
                    region_name=region,
                    config=bedrock_config
                )
            except Exception as e:
                raise RuntimeError(f"Failed to create Bedrock client: {e}") from e
        
        return self._client
    
    def evaluate(
        self,
        source_json: dict,
        model_json: dict,
        schema_errors: list[ValidationError] | None = None,
        section_evaluations: list[SectionEvaluation] | None = None,
    ) -> LLMEvaluationResponse:
        """
        Perform LLM-based semantic evaluation.
        
        Args:
            source_json: Source of truth JSON
            model_json: Model output JSON
            schema_errors: Optional list of schema validation errors
            section_evaluations: Optional existing section evaluations to update
            
        Returns:
            LLMEvaluationResponse with semantic scores
        """
        log(f"Performing LLM evaluation using [{self.model_id}]")
        
        client = self._get_client()
        
        # Format schema errors
        errors_str = "No schema validation errors found."
        if schema_errors:
            error_lines = [f"- {e.path}: {e.message}" for e in schema_errors[:20]]
            errors_str = "\n".join(error_lines)
            if len(schema_errors) > 20:
                errors_str += f"\n... and {len(schema_errors) - 20} more errors"
        
        # Prepare condensed JSON (just sections and fields for comparison)
        source_condensed = self._extract_for_comparison(source_json)
        model_condensed = self._extract_for_comparison(model_json)
        
        # Build prompt
        prompt = EVALUATION_PROMPT.format(
            schema_errors=errors_str,
            source_json=json.dumps(source_condensed, indent=2),
            model_json=json.dumps(model_condensed, indent=2),
        )
        
        # Send request
        try:
            log("Sending evaluation request to Bedrock...")
            response = client.converse(
                modelId=self.model_id,
                messages=[{"role": "user", "content": [{"text": prompt}]}],
                inferenceConfig={
                    "maxTokens": 8000,
                    "temperature": 0.0,
                }
            )
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_msg = e.response.get("Error", {}).get("Message", str(e))
            log(f"Bedrock API error: {error_code} - {error_msg}")
            # Return fallback response
            return self._create_fallback_response(section_evaluations)
        except Exception as e:
            log(f"Unexpected error calling Bedrock: {e}")
            return self._create_fallback_response(section_evaluations)
        
        # Log usage
        usage = response.get("usage", {})
        log_usage(
            provider="bedrock",
            model=self.model_id,
            input_tokens=usage.get("inputTokens", 0),
            output_tokens=usage.get("outputTokens", 0),
            operation="llm_evaluation"
        )
        
        # Extract response text
        try:
            output_message = response["output"]["message"]
            result_text = output_message["content"][0]["text"]
        except (KeyError, IndexError) as e:
            log(f"Failed to extract response text: {e}")
            return self._create_fallback_response(section_evaluations)
        
        # Parse JSON response
        result_text = self._clean_json_response(result_text)
        
        try:
            result_dict = json.loads(result_text)
            return LLMEvaluationResponse.model_validate(result_dict)
        except (json.JSONDecodeError, Exception) as e:
            log(f"Failed to parse LLM response: {e}")
            log(f"Response: {result_text[:500]}...")
            return self._create_fallback_response(section_evaluations)
    
    def _extract_for_comparison(self, json_data: dict) -> list[dict]:
        """
        Extract sections and fields for comparison (condensed format).
        """
        extracted_sections: list[dict] = []
        data = {k: v for k, v in json_data.items() if k != "_metadata"}
        
        versions = data.get("versions", [])
        if not versions:
            return extracted_sections
        
        structure = versions[0].get("structure", {})
        
        def extract_sections(section: dict) -> None:
            fields = section.get("fields", [])
            if fields:
                extracted_sections.append({
                    "name": section.get("name", "Unknown"),
                    "fields": [
                        {
                            "id": f.get("id"),
                            "name": f.get("name"),
                            "options": f.get("options", []),
                        }
                        for f in fields
                    ]
                })
            
            for subsection in section.get("sections", []):
                extract_sections(subsection)
        
        extract_sections(structure)
        return extracted_sections
    
    def _clean_json_response(self, text: str) -> str:
        """Clean markdown formatting from JSON response."""
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return text.strip()
    
    def _create_fallback_response(
        self,
        section_evaluations: list[SectionEvaluation] | None
    ) -> LLMEvaluationResponse:
        """
        Create fallback response using deterministic similarity scores.
        """
        fallback_sections: list[LLMSectionComparison] = []
        
        if section_evaluations:
            for section_eval in section_evaluations:
                fields: list[LLMFieldComparison] = []
                for field_eval in section_eval.fields:
                    fields.append(LLMFieldComparison(
                        source_field_id=field_eval.source_field_id,
                        model_field_id=field_eval.model_field_id,
                        name_similarity=field_eval.name_similarity,
                        options_similarity=field_eval.options_exact_match,
                        reasoning="Fallback: using deterministic similarity"
                    ))
                
                fallback_sections.append(LLMSectionComparison(
                    source_section_name=section_eval.source_section_name,
                    model_section_name=section_eval.model_section_name,
                    name_similarity=section_eval.section_name_similarity,
                    fields=fields
                ))
        
        return LLMEvaluationResponse(
            sections=fallback_sections,
            overall_assessment="Fallback evaluation using deterministic comparison"
        )


def update_evaluations_with_llm_scores(
    section_evaluations: list[SectionEvaluation],
    llm_response: LLMEvaluationResponse,
) -> list[SectionEvaluation]:
    """
    Update section evaluations with LLM semantic scores.
    
    Args:
        section_evaluations: Existing section evaluations from deterministic comparison
        llm_response: LLM evaluation response with semantic scores
        
    Returns:
        Updated section evaluations
    """
    # Create lookup for LLM results
    llm_sections = {s.source_section_name: s for s in llm_response.sections}
    
    for section_eval in section_evaluations:
        llm_section = llm_sections.get(section_eval.source_section_name)
        
        if llm_section:
            # Update section name similarity
            section_eval.section_name_similarity = llm_section.name_similarity
            
            # Create field lookup
            llm_fields = {f.source_field_id: f for f in llm_section.fields}
            
            for field_eval in section_eval.fields:
                llm_field = llm_fields.get(field_eval.source_field_id)
                
                if llm_field:
                    field_eval.name_similarity = llm_field.name_similarity
                    field_eval.options_similarity = llm_field.options_similarity
                    field_eval.reasoning = llm_field.reasoning
    
    return section_evaluations


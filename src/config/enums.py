"""
Provider and Model Enums for OCR-AI.

These enums define the available providers and models that can be used
for JSON extraction from images.
"""

from enum import Enum


class Provider(str, Enum):
    """Available extraction providers."""
    BEDROCK = "bedrock"
    DEEPSEEK = "deepseek"


class BedrockModel(str, Enum):
    """Available AWS Bedrock models for vision tasks."""
    QWEN3_VL_235B = "qwen.qwen3-vl-235b-a22b"
    # Add more Bedrock models as needed


class OpenAIModel(str, Enum):
    """Available OpenAI models for JSON extraction."""
    GPT_4O = "gpt-4o"
    GPT_4O_MINI = "gpt-4o-mini"
    GPT_5_1 = "gpt-5.1"
    # Add more OpenAI models as needed


class OllamaModel(str, Enum):
    """Available Ollama models for OCR."""
    DEEPSEEK_OCR = "deepseek-ocr"
    # Add more Ollama models as needed


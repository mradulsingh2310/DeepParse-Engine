"""
Configuration Loader for OCR-AI.

Loads and validates configuration from YAML files.
"""

from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, Field

from .enums import Provider


class ModelConfig(BaseModel):
    """Configuration for a single model."""
    model_id: str
    supporting_model_id: str | None = None  # Used by deepseek for JSON extraction model
    max_tokens: int | None = None  # Per-model max tokens (overrides provider default)


class BedrockConfig(BaseModel):
    """Configuration for AWS Bedrock provider."""
    region: str = "us-east-1"
    timeout: int = 1200
    retries: int = 2
    max_tokens: int = 10000
    models: list[ModelConfig] = Field(default_factory=list)


class DeepseekConfig(BaseModel):
    """Configuration for Deepseek (Ollama OCR + OpenAI) provider."""
    # OCR settings
    ocr_timeout: int = 300
    use_grounding: bool = False

    # JSON extraction settings
    json_temperature: float = 0.0

    # Model configurations
    models: list[ModelConfig] = Field(default_factory=list)


class GoogleConfig(BaseModel):
    """Configuration for Google AI provider (Gemini models)."""
    timeout: int = 300
    max_output_tokens: int = 65536
    thinking_level: str = "low"  # minimal, low, medium, high
    models: list[ModelConfig] = Field(default_factory=list)


class AnthropicConfig(BaseModel):
    """Configuration for Anthropic provider (Claude models)."""
    timeout: int = 300
    max_tokens: int = 8192
    models: list[ModelConfig] = Field(default_factory=list)


class OutputConfig(BaseModel):
    """Output settings configuration."""
    save_images: bool = True
    images_dir: str = "img"
    output_dir: str = "output"


class ProviderConfig(BaseModel):
    """Container for all provider configurations."""
    bedrock: BedrockConfig = Field(default_factory=BedrockConfig)
    deepseek: DeepseekConfig = Field(default_factory=DeepseekConfig)
    google: GoogleConfig = Field(default_factory=GoogleConfig)
    anthropic: AnthropicConfig = Field(default_factory=AnthropicConfig)


class AppConfig(BaseModel):
    """Main application configuration."""
    default_provider: Provider = Provider.BEDROCK
    providers: ProviderConfig = Field(default_factory=ProviderConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)


# Global config holder (avoids global statement)
_config_holder: dict[str, Any] = {"config": None}


def _parse_models(models_data: list[dict] | None) -> list[ModelConfig]:
    """Parse a list of model configurations."""
    if not models_data:
        return []
    return [ModelConfig(**m) for m in models_data]


def load_config(config_path: str | Path | None = None) -> AppConfig:
    """
    Load configuration from a YAML file.
    
    Args:
        config_path: Path to the config file. Defaults to src/config/config.yaml
        
    Returns:
        Loaded and validated AppConfig instance
    """
    if config_path is None:
        config_path = Path(__file__).parent / "config.yaml"
    else:
        config_path = Path(config_path)
    
    if not config_path.exists():
        print(f"Config file not found at {config_path}, using defaults")
        config = AppConfig()
        _config_holder["config"] = config
        return config
    
    with open(config_path, "r", encoding="utf-8") as f:
        raw_config = yaml.safe_load(f)
    
    if raw_config is None:
        config = AppConfig()
        _config_holder["config"] = config
        return config
    
    # Parse providers
    providers_data = raw_config.get("providers", {})
    
    # Parse bedrock config
    bedrock_data = providers_data.get("bedrock", {})
    bedrock_models = _parse_models(bedrock_data.pop("models", None))
    bedrock = BedrockConfig(**bedrock_data, models=bedrock_models)
    
    # Parse deepseek config
    deepseek_data = providers_data.get("deepseek", {})
    deepseek_models = _parse_models(deepseek_data.pop("models", None))
    deepseek = DeepseekConfig(**deepseek_data, models=deepseek_models)

    # Parse google config
    google_data = providers_data.get("google", {})
    google_models = _parse_models(google_data.pop("models", None))
    google = GoogleConfig(**google_data, models=google_models)

    # Parse anthropic config
    anthropic_data = providers_data.get("anthropic", {})
    anthropic_models = _parse_models(anthropic_data.pop("models", None))
    anthropic = AnthropicConfig(**anthropic_data, models=anthropic_models)

    providers = ProviderConfig(
        bedrock=bedrock,
        deepseek=deepseek,
        google=google,
        anthropic=anthropic,
    )
    
    # Parse output config
    output = OutputConfig(**raw_config.get("output", {}))
    
    # Parse default provider
    default_provider_str = raw_config.get("default_provider", "bedrock")
    default_provider = Provider(default_provider_str)
    
    config = AppConfig(
        default_provider=default_provider,
        providers=providers,
        output=output,
    )
    _config_holder["config"] = config
    
    return config


def get_config() -> AppConfig:
    """
    Get the current configuration.
    
    Loads from default path if not already loaded.
    
    Returns:
        Current AppConfig instance
    """
    if _config_holder["config"] is None:
        return load_config()
    return _config_holder["config"]

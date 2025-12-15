"""
Configuration Loader for OCR-AI.

Loads and validates configuration from YAML files.
"""

from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, Field

from .enums import Provider


class BedrockConfig(BaseModel):
    """Configuration for AWS Bedrock provider."""
    model_id: str = "qwen.qwen3-vl-235b-a22b"
    region: str = "us-east-1"
    timeout: int = 1200
    retries: int = 2


class DeepseekConfig(BaseModel):
    """Configuration for Deepseek (Ollama OCR + OpenAI) provider."""
    # OCR settings
    ocr_model: str = "deepseek-ocr"
    ocr_timeout: int = 300
    use_grounding: bool = False
    
    # JSON extraction settings
    json_model: str = "gpt-5.1"
    json_temperature: float = 0.0


class OutputConfig(BaseModel):
    """Output settings configuration."""
    save_images: bool = True
    images_dir: str = "img"
    output_dir: str = "output"


class ProviderConfig(BaseModel):
    """Container for all provider configurations."""
    bedrock: BedrockConfig = Field(default_factory=BedrockConfig)
    deepseek: DeepseekConfig = Field(default_factory=DeepseekConfig)


class AppConfig(BaseModel):
    """Main application configuration."""
    default_provider: Provider = Provider.BEDROCK
    providers: ProviderConfig = Field(default_factory=ProviderConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)


# Global config holder (avoids global statement)
_config_holder: dict[str, Any] = {"config": None}


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
    providers = ProviderConfig(
        bedrock=BedrockConfig(**providers_data.get("bedrock", {})),
        deepseek=DeepseekConfig(**providers_data.get("deepseek", {})),
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

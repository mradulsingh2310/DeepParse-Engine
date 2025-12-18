"""
Service Factory for JSON Extraction.

Provides a strategy-based factory that returns the appropriate
service implementation based on the configured provider.
"""

from src.config import Provider, get_config
from src.config.loader import AppConfig, ModelConfig

from .base import JsonExtractionService
from .providers import BedrockService, DeepseekService


def get_service(
    provider: Provider | None = None,
    config: AppConfig | None = None,
    model_config: ModelConfig | None = None,
) -> JsonExtractionService:
    """
    Get the appropriate service implementation based on provider.
    
    This is the strategy chooser - it selects the correct implementation
    based on the specified provider or the default from config.
    
    Args:
        provider: Provider enum value. Uses config default if not specified.
        config: AppConfig instance. Loads from file if not provided.
        model_config: ModelConfig with model_id and optional supporting_model_id.
                      If not provided, uses first model from provider's model list.
        
    Returns:
        JsonExtractionService implementation for the specified provider.
        
    Raises:
        ValueError: If provider is not supported.
    """
    if config is None:
        config = get_config()
    
    # Use config default if no provider specified
    if provider is None:
        provider = config.default_provider
    
    match provider:
        case Provider.BEDROCK:
            return BedrockService(
                config=config.providers.bedrock,
                model_config=model_config,
            )
        case Provider.DEEPSEEK:
            return DeepseekService(
                config=config.providers.deepseek,
                model_config=model_config,
            )
        case _:
            raise ValueError(f"Unsupported provider: {provider}")

"""
Service Factory for JSON Extraction.

Provides a strategy-based factory that returns the appropriate
service implementation based on the configured provider.
"""

from src.config import Provider, get_config
from src.config.loader import AppConfig

from .base import JsonExtractionService
from .providers import BedrockService, DeepseekService


def get_service(
    provider: Provider | None = None,
    config: AppConfig | None = None,
) -> JsonExtractionService:
    """
    Get the appropriate service implementation based on provider.
    
    This is the strategy chooser - it selects the correct implementation
    based on the specified provider or the default from config.
    
    Args:
        provider: Provider enum value. Uses config default if not specified.
        config: AppConfig instance. Loads from file if not provided.
        
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
            return BedrockService(config.providers.bedrock)
        case Provider.DEEPSEEK:
            return DeepseekService(config.providers.deepseek)
        case _:
            raise ValueError(f"Unsupported provider: {provider}")


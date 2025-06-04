from typing import Dict, Type, Any, Optional
from app.providers.base import NotificationProvider
from app.core.exceptions import ProviderNotFoundError

class ProviderRegistry:
    """
    Registry for notification providers.
    """
    _providers: Dict[str, Type[NotificationProvider]] = {}
    
    @classmethod
    def register(cls, provider_id: str, provider_class: Type[NotificationProvider]) -> None:
        """
        Register a new provider.
        
        Args:
            provider_id: The provider identifier
            provider_class: The provider class
        """
        cls._providers[provider_id] = provider_class
    
    @classmethod
    def get_provider(cls, provider_id: str, config: Optional[Dict[str, Any]] = None) -> NotificationProvider:
        """
        Get a provider instance by ID.
        
        Args:
            provider_id: The provider identifier
            config: Configuration for the provider
            
        Returns:
            NotificationProvider: An instance of the provider
            
        Raises:
            ProviderNotFoundError: If the provider is not registered
        """
        if provider_id not in cls._providers:
            raise ProviderNotFoundError(provider_id)
        
        provider_class = cls._providers[provider_id]
        return provider_class(config or {})
    
    @classmethod
    def list_providers(cls) -> Dict[str, Type[NotificationProvider]]:
        """
        List all registered providers.
        
        Returns:
            Dict[str, Type[NotificationProvider]]: Dictionary of provider_id to provider_class
        """
        return cls._providers.copy()

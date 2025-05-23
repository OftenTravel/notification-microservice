from typing import Dict, Any, Optional
from app.models.messages import SMSMessage, EmailMessage, WhatsAppMessage
from app.models.responses import NotificationResponse
from app.providers.registry import ProviderRegistry

class NotificationService:
    """
    Service for sending notifications using registered providers.
    """
    
    def __init__(self, default_provider_id: Optional[str] = None, default_config: Dict[str, Any] = None):
        """
        Initialize the notification service.
        
        Args:
            default_provider_id: ID of the default provider to use
            default_config: Default configuration for providers
        """
        self.default_provider_id = default_provider_id
        self.default_config = default_config or {}
    
    async def send_sms(
        self, 
        message: SMSMessage, 
        provider_id: Optional[str] = None, 
        config: Optional[Dict[str, Any]] = None
    ) -> NotificationResponse:
        """
        Send an SMS message using the specified provider.
        
        Args:
            message: The SMS message to send
            provider_id: The provider to use (overrides the message's provider_id and default)
            config: Provider configuration (overrides default)
            
        Returns:
            NotificationResponse: The result of the operation
        """
        provider_id = provider_id or message.provider_id or self.default_provider_id
        if not provider_id:
            raise ValueError("No provider specified for sending SMS")

        # Merge configurations
        merged_config = {**self.default_config, **(config or {})}
        
        # Get the provider
        provider = ProviderRegistry.get_provider(provider_id, merged_config)
        
        # Send the message
        return await provider.send_sms(message)
    
    async def send_email(
        self, 
        message: EmailMessage, 
        provider_id: Optional[str] = None, 
        config: Optional[Dict[str, Any]] = None
    ) -> NotificationResponse:
        """
        Send an email message using the specified provider.
        
        Args:
            message: The email message to send
            provider_id: The provider to use (overrides the message's provider_id and default)
            config: Provider configuration (overrides default)
            
        Returns:
            NotificationResponse: The result of the operation
        """
        provider_id = provider_id or message.provider_id or self.default_provider_id
        if not provider_id:
            raise ValueError("No provider specified for sending email")

        # Merge configurations
        merged_config = {**self.default_config, **(config or {})}
        
        # Get the provider
        provider = ProviderRegistry.get_provider(provider_id, merged_config)
        
        # Send the message
        return await provider.send_email(message)
    
    async def send_whatsapp(
        self, 
        message: WhatsAppMessage, 
        provider_id: Optional[str] = None, 
        config: Optional[Dict[str, Any]] = None
    ) -> NotificationResponse:
        """
        Send a WhatsApp message using the specified provider.
        
        Args:
            message: The WhatsApp message to send
            provider_id: The provider to use (overrides the message's provider_id and default)
            config: Provider configuration (overrides default)
            
        Returns:
            NotificationResponse: The result of the operation
        """
        provider_id = provider_id or message.provider_id or self.default_provider_id
        if not provider_id:
            raise ValueError("No provider specified for sending WhatsApp message")

        # Merge configurations
        merged_config = {**self.default_config, **(config or {})}
        
        # Get the provider
        provider = ProviderRegistry.get_provider(provider_id, merged_config)
        
        # Send the message
        return await provider.send_whatsapp(message)

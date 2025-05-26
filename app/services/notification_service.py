from typing import Dict, Any, Optional, Union
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
import logging

from app.models.messages import SMSMessage, EmailMessage, WhatsAppMessage
from app.models.responses import NotificationResponse
from app.core.exceptions import ProviderNotFoundError, NotificationException
from app.repositories.provider_repository import ProviderRepository
from app.providers.msg91_provider import MSG91Provider
from app.providers.mock_provider import MockProvider

logger = logging.getLogger(__name__)

class NotificationService:
    """Service for sending notifications using database-managed providers."""
    
    def __init__(self, default_provider_name: Optional[str] = "mock"):
        self.default_provider_name = default_provider_name
    
    async def _get_provider_instance(self, provider_entity):
        """Create provider instance based on provider name."""
        if provider_entity.name == "msg91":
            return MSG91Provider(provider_entity.config)
        elif provider_entity.name == "mock":
            return MockProvider(provider_entity.config)
        else:
            raise ProviderNotFoundError(f"Unknown provider type: {provider_entity.name}")
    
    async def send_email(
        self, 
        message: EmailMessage, 
        provider_id: Optional[uuid.UUID] = None,
        service_id: Optional[uuid.UUID] = None,
        priority: Optional[str] = None,
        db: Optional[AsyncSession] = None
    ) -> NotificationResponse:
        """Send an email message."""
        if not db:
            raise ValueError("Database session is required")
            
        repo = ProviderRepository(db)
        
        # Get provider by UUID or fall back to default by name
        if provider_id:
            provider_entity = await repo.get_provider(provider_id)
        else:
            provider_entity = await repo.get_provider_by_name(self.default_provider_name)
        
        if not provider_entity:
            raise ProviderNotFoundError(f"Provider not found")
        
        if not provider_entity.is_active:
            raise ProviderNotFoundError(f"Provider '{provider_entity.name}' is not active")
            
        # Check if provider supports email
        if not provider_entity.supports_type('email'):
            raise ProviderNotFoundError(f"Provider '{provider_entity.name}' does not support email messages")
        
        # Create provider instance
        provider = await self._get_provider_instance(provider_entity)
        return await provider.send_email(message)
    
    async def send_sms(
        self, 
        message: SMSMessage, 
        provider_id: Optional[uuid.UUID] = None,
        service_id: Optional[uuid.UUID] = None,
        priority: Optional[str] = None,
        db: Optional[AsyncSession] = None
    ) -> NotificationResponse:
        """Send an SMS message."""
        if not db:
            raise ValueError("Database session is required")
            
        repo = ProviderRepository(db)
        
        # Get provider by UUID or fall back to default by name
        if provider_id:
            provider_entity = await repo.get_provider(provider_id)
        else:
            provider_entity = await repo.get_provider_by_name(self.default_provider_name)
        
        if not provider_entity:
            raise ProviderNotFoundError(f"Provider not found")
        
        if not provider_entity.is_active:
            raise ProviderNotFoundError(f"Provider '{provider_entity.name}' is not active")
            
        # Check if provider supports SMS
        if not provider_entity.supports_type('sms'):
            raise ProviderNotFoundError(f"Provider '{provider_entity.name}' does not support SMS messages")
        
        # Create provider instance
        provider = await self._get_provider_instance(provider_entity)
        return await provider.send_sms(message)
    
    async def send_whatsapp(
        self, 
        message: WhatsAppMessage, 
        provider_id: Optional[uuid.UUID] = None,
        service_id: Optional[uuid.UUID] = None,
        priority: Optional[str] = None,
        db: Optional[AsyncSession] = None
    ) -> NotificationResponse:
        """Send a WhatsApp message."""
        if not db:
            raise ValueError("Database session is required")
            
        repo = ProviderRepository(db)
        
        # Get provider by UUID or fall back to default by name
        if provider_id:
            provider_entity = await repo.get_provider(provider_id)
        else:
            provider_entity = await repo.get_provider_by_name(self.default_provider_name)
        
        if not provider_entity:
            raise ProviderNotFoundError(f"Provider not found")
        
        if not provider_entity.is_active:
            raise ProviderNotFoundError(f"Provider '{provider_entity.name}' is not active")
            
        # Check if provider supports WhatsApp
        if not provider_entity.supports_type('whatsapp'):
            raise ProviderNotFoundError(f"Provider '{provider_entity.name}' does not support WhatsApp messages")
        
        # Create provider instance
        provider = await self._get_provider_instance(provider_entity)
        return await provider.send_whatsapp(message)

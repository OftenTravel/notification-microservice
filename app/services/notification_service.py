from typing import Dict, Any, Optional, Union
from fastapi import BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
import logging

from app.providers.registry import ProviderRegistry
from app.models.messages import SMSMessage, EmailMessage, WhatsAppMessage
from app.models.responses import NotificationResponse
from app.core.exceptions import ProviderNotFoundError, NotificationException
from app.repositories.provider_repository import ProviderRepository
from app.models.notification import NotificationPriority

logger = logging.getLogger(__name__)

class NotificationService:
    """
    Service for sending notifications using registered providers.
    """
    
    def __init__(self, default_provider_id: Optional[str] = None):
        self.default_provider_id = default_provider_id or "msg91"
    
    async def _get_provider_config(self, db: AsyncSession, provider_id: str) -> Dict[str, Any]:
        """Get provider configuration from database."""
        repo = ProviderRepository(db)
        provider_entity = await repo.get_provider_by_name(provider_id)
        
        if not provider_entity or not provider_entity.config:
            return {}
            
        return provider_entity.config
    
    async def send_sms(
        self, 
        message: SMSMessage, 
        provider_id: Optional[str] = None,
        service_id: Optional[uuid.UUID] = None,
        priority: Optional[str] = None,
        db: Optional[AsyncSession] = None
    ) -> NotificationResponse:
        """Send an SMS message."""
        # Use provider from query param, message body, or default
        provider_id = provider_id or getattr(message, 'provider_id', None) or self.default_provider_id
        
        # Log diagnostic information
        logger.info(f"Sending SMS with provider: {provider_id}, priority: {priority}")
        
        # Get provider config from database if db session is provided
        config = {}
        if db:
            config = await self._get_provider_config(db, provider_id)
        
        provider = ProviderRegistry.get_provider(provider_id, config)
        if not provider:
            raise ProviderNotFoundError(f"Provider '{provider_id}' not found")
            
        return await provider.send_sms(message)
    
    async def send_email(
        self, 
        message: EmailMessage, 
        provider_id: Optional[str] = None,
        priority: Optional[str] = None,
        db: Optional[AsyncSession] = None
    ) -> NotificationResponse:
        """Send an email message."""
        # Use provider from query param, message body, or default
        provider_id = provider_id or getattr(message, 'provider_id', None) or self.default_provider_id
        
        # Log diagnostic information
        logger.info(f"Sending email with provider: {provider_id}, priority: {priority}")
        
        # Get provider config from database if db session is provided
        config = {}
        if db:
            config = await self._get_provider_config(db, provider_id)
        
        provider = ProviderRegistry.get_provider(provider_id, config)
        if not provider:
            raise ProviderNotFoundError(f"Provider '{provider_id}' not found")
            
        return await provider.send_email(message)
    
    async def send_whatsapp(
        self, 
        message: WhatsAppMessage, 
        provider_id: Optional[str] = None,
        service_id: Optional[uuid.UUID] = None,
        priority: Optional[str] = None,
        db: Optional[AsyncSession] = None
    ) -> NotificationResponse:
        """Send a WhatsApp message."""
        # Use provider from query param, message body, or default
        provider_id = provider_id or getattr(message, 'provider_id', None) or self.default_provider_id
        
        # Log diagnostic information
        logger.info(f"Sending WhatsApp with provider: {provider_id}, priority: {priority}")
        
        # Get provider config from database if db session is provided
        config = {}
        if db:
            config = await self._get_provider_config(db, provider_id)
        
        provider = ProviderRegistry.get_provider(provider_id, config)
        if not provider:
            raise ProviderNotFoundError(f"Provider '{provider_id}' not found")
            
        return await provider.send_whatsapp(message)

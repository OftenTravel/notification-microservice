from typing import List, Optional, Dict, Any
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
# import logging
import structlog

from app.models.provider import Provider

logger = structlog.get_logger(__name__)

class ProviderRepository:
    """Repository for provider database operations."""
    
    def __init__(self, db: AsyncSession):
        """
        Initialize with a database session.
        
        Args:
            db: SQLAlchemy async session
        """
        self.db = db
    
    async def create_provider(self, data: Dict[str, Any]) -> Provider:
        """
        Create a new provider.
        
        Args:
            data: Provider data
            
        Returns:
            Provider: The created provider
        """
        provider = Provider(**data)
        self.db.add(provider)
        await self.db.commit()
        await self.db.refresh(provider)
        return provider
    
    async def get_provider(self, provider_id: UUID) -> Optional[Provider]:
        """
        Get a provider by ID.
        
        Args:
            provider_id: Provider ID
            
        Returns:
            Optional[Provider]: The provider if found
        """
        print(f"Fetching provider with ID: {provider_id}")
        return await self.db.get(Provider, provider_id)
    
    async def get_provider_by_name(self, name: str) -> Optional[Provider]:
        """
        Get a provider by name.
        
        Args:
            name: Provider name
            
        Returns:
            Optional[Provider]: The provider if found
        """
        query = select(Provider).where(Provider.name == name)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def list_providers(
        self, 
        type: Optional[str] = None,
        active_only: bool = True
    ) -> List[Provider]:
        """
        List providers.
        
        Args:
            type: Optional provider type filter
            active_only: If True, only return active providers
            
        Returns:
            List[Provider]: List of providers
        """
        query = select(Provider)
        
        if type:
            query = query.where(Provider.type == type)
            
        if active_only:
            query = query.where(Provider.is_active == True)
            
        # Order by priority (lower number = higher priority)
        query = query.order_by(Provider.priority)
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def list_providers(self, active_only: bool = False) -> List[Provider]:
        """List all providers."""
        query = select(Provider)
        if active_only:
            query = query.where(Provider.is_active == True)
        query = query.order_by(Provider.priority, Provider.name)
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def seed_default_providers(self) -> List[Provider]:
        """Seed default providers if not exist."""
        logger.info("Seeding providers...")
        
        default_providers = [
            {
                "name": "mock",
                "supported_types": ["sms", "email", "whatsapp"],
                "is_active": True,
                "priority": 10,
                "config": {
                    "success_rate": 0.9,
                    "delay_ms": 500
                }
            }
        ]
        
        providers = []
        for p_data in default_providers:
            existing = await self.get_provider_by_name(p_data["name"])
            
            if not existing:
                provider = await self.create_provider(p_data)
                providers.append(provider)
            else:
                providers.append(existing)
                
        return providers
        
    async def get_active_providers(self, notification_type: str) -> List[Provider]:
        """
        Get active providers that support the given notification type.
        
        Args:
            notification_type: Type of notification (sms, email, whatsapp)
            
        Returns:
            List of active providers supporting the notification type, ordered by priority
        """
        query = (
            select(Provider)
            .where(Provider.is_active == True)
            .where(Provider.supported_types.contains([notification_type]))
            .order_by(Provider.priority.asc())
        )
        result = await self.db.execute(query)
        return result.scalars().all()

    async def update_provider(self, provider_id: UUID, data: Dict[str, Any]) -> Optional[Provider]:
        """
        Update a provider.
        """
        provider = await self.get_provider(provider_id)
        if not provider:
            return None
            
        for key, value in data.items():
            setattr(provider, key, value)
            
        await self.db.commit()
        await self.db.refresh(provider)
        return provider

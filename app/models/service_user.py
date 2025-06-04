import uuid
from sqlalchemy import Column, String, DateTime, Boolean, Text
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
from typing import Optional
from app.core.database import Base
from app.core.security import encrypt_api_key, verify_api_key


class ServiceUser(Base):
    """Model for registered services that can use the notification system."""
    __tablename__ = "service_users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), unique=True, nullable=False, index=True)
    api_key_hash = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @classmethod
    async def create_service(cls, db, name: str, description: Optional[str] = None):
        """Create a new service with a generated API key."""
        service_id = uuid.uuid4()
        raw_api_key = f"{service_id.hex}-{uuid.uuid4().hex}"
        hashed_key = encrypt_api_key(raw_api_key)
        
        service = cls(
            id=service_id,
            name=name,
            api_key_hash=hashed_key,
            description=description
        )
        db.add(service)
        await db.commit()
        await db.refresh(service)
        
        # Return both the service record and the raw API key
        # (raw key will only be shown once at creation)
        return service, raw_api_key

    @classmethod
    async def authenticate_service(cls, db, api_key: str):
        """Verify an API key and return the associated service if valid."""
        try:
            # Extract service ID from the API key format
            service_id_part = api_key.split('-')[0]
            service_id = uuid.UUID(service_id_part)
            
            service = await db.get(cls, service_id)
            if service and verify_api_key(api_key, service.api_key_hash):
                return service
        except (ValueError, IndexError, AttributeError):
            pass
        
        return None

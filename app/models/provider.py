import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Boolean, DateTime, JSON
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from typing import List

from app.core.database import Base


class Provider(Base):
    """Model for notification providers."""
    __tablename__ = "providers"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(50), unique=True, nullable=False, index=True)
    supported_types = Column(ARRAY(String), nullable=False)  # ['sms', 'email', 'whatsapp']
    is_active = Column(Boolean, default=True)
    priority = Column(Integer, default=1)
    config = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def supports_type(self, message_type: str) -> bool:
        """Check if provider supports a specific message type."""
        return message_type.lower() in [t.lower() for t in self.supported_types]

    def __repr__(self):
        return f"<Provider(id={self.id}, name={self.name}, types={self.supported_types})>"

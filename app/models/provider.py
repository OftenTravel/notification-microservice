import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Boolean, DateTime, JSON
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class Provider(Base):
    """Model for notification providers."""
    __tablename__ = "providers"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(50), unique=True, nullable=False, index=True)
    type = Column(String(20), nullable=False)  # 'sms', 'email', 'whatsapp', or 'all'
    is_active = Column(Boolean, default=True)
    priority = Column(Integer, default=1)
    config = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Provider(id={self.id}, name={self.name}, type={self.type})>"

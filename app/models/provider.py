import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, JSON, Enum
from sqlalchemy.dialects.postgresql import UUID
import enum

from app.core.database import Base


class ProviderType(str, enum.Enum):
    SMS = "sms"
    EMAIL = "email"
    PUSH = "push"
    WHATSAPP = "whatsapp"


class Provider(Base):
    __tablename__ = "providers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    type = Column(Enum(ProviderType), nullable=False)
    config = Column(JSON, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Provider(id={self.id}, name={self.name}, type={self.type})>"

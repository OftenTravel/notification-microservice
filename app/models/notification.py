import uuid
import enum
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Boolean, Integer, Text, ForeignKey, Enum as SQLAEnum, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.core.database import Base


class NotificationType(str, enum.Enum):
    """Types of notifications supported by the system."""
    SMS = "sms"
    EMAIL = "email"
    WHATSAPP = "whatsapp"


class NotificationStatus(str, enum.Enum):
    """Possible statuses for a notification."""
    PENDING = "pending"
    QUEUED = "queued"
    SENDING = "sending"
    DELIVERED = "delivered"
    FAILED = "failed"
    SEEN = "seen"
    CANCELLED = "CANCELLED"


class NotificationPriority(str, enum.Enum):
    """Priority levels for notifications."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    INSTANT = "instant"


class Notification(Base):
    """Model for tracking all notifications."""
    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Make service_id nullable for now to avoid the relationship error
    service_id = Column(UUID(as_uuid=True), nullable=True)  # Changed: removed ForeignKey
    type = Column(SQLAEnum(NotificationType), nullable=False)
    priority = Column(SQLAEnum(NotificationPriority), default=NotificationPriority.NORMAL)
    status = Column(SQLAEnum(NotificationStatus), default=NotificationStatus.PENDING)
    recipient = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    subject = Column(String(500), nullable=True)  # For emails
    meta_data = Column(JSONB, default={})  # Renamed from 'metadata' to avoid conflicts
    provider_id = Column(String(50), nullable=True)
    provider_response = Column(JSONB, nullable=True)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    is_instant = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    sent_at = Column(DateTime, nullable=True)
    scheduled_at = Column(DateTime, nullable=True)  # For scheduled notifications
    delivered_at = Column(DateTime, nullable=True)  # For delivery tracking
    failed_at = Column(DateTime, nullable=True)  # For failure tracking
    external_id = Column(String(255), nullable=True)  # Provider's reference ID

    # Remove the relationship that's causing the issue
    # service = relationship("ServiceUser")
    
    # Add index for common queries
    __table_args__ = (
        Index('idx_notifications_status', status),
        Index('idx_notifications_recipient', recipient),
        Index('idx_notifications_created_at', created_at),
        Index('idx_notifications_type', type),
    )

    @classmethod
    async def create_sms_notification(cls, db, service_id, recipient, content, priority=NotificationPriority.NORMAL, provider_id=None):
        """Factory method for creating an SMS notification."""
        notification = cls(
            service_id=service_id,
            type=NotificationType.SMS,
            recipient=recipient,
            content=content, 
            priority=priority,
            provider_id=provider_id,
            is_instant=(priority == NotificationPriority.INSTANT)
        )
        db.add(notification)
        await db.commit()
        await db.refresh(notification)
        return notification

    @classmethod
    async def create_email_notification(cls, db, service_id, recipient, subject, body, priority=NotificationPriority.NORMAL, provider_id=None):
        """Factory method for creating an email notification."""
        notification = cls(
            service_id=service_id,
            type=NotificationType.EMAIL,
            recipient=recipient,
            content=body,
            meta_data={"subject": subject},
            priority=priority,
            provider_id=provider_id,
            is_instant=(priority == NotificationPriority.INSTANT)
        )
        db.add(notification)
        await db.commit()
        await db.refresh(notification)
        return notification

    @classmethod
    async def create_whatsapp_notification(cls, db, service_id, recipient, content, priority=NotificationPriority.NORMAL, provider_id=None):
        """Factory method for creating a WhatsApp notification."""
        notification = cls(
            service_id=service_id,
            type=NotificationType.WHATSAPP,
            recipient=recipient,
            content=content,
            priority=priority,
            provider_id=provider_id,
            is_instant=(priority == NotificationPriority.INSTANT)
        )
        db.add(notification)
        await db.commit()
        await db.refresh(notification)
        return notification


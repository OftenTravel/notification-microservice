import uuid
import enum
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Boolean, Integer, Text, ForeignKey, Enum as SQLAEnum, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.core.database import Base


class WebhookStatus(str, enum.Enum):
    """Status of webhook delivery attempts."""
    PENDING = "pending"
    ACKNOWLEDGED = "acknowledged"
    FAILED = "failed"
    RETRYING = "retrying"


class Webhook(Base):
    """Model for storing webhook endpoints for services."""
    __tablename__ = "webhooks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    service_id = Column(UUID(as_uuid=True), ForeignKey("service_users.id"), nullable=False)
    url = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    service = relationship("ServiceUser", backref="webhooks")
    deliveries = relationship("WebhookDelivery", back_populates="webhook", cascade="all, delete-orphan")

    __table_args__ = (
        Index('idx_webhooks_service_id', service_id),
        Index('idx_webhooks_is_active', is_active),
    )


class WebhookDelivery(Base):
    """Model for tracking webhook delivery attempts."""
    __tablename__ = "webhook_deliveries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    webhook_id = Column(UUID(as_uuid=True), ForeignKey("webhooks.id"), nullable=False)
    notification_id = Column(UUID(as_uuid=True), ForeignKey("notifications.id"), nullable=False)
    status = Column(SQLAEnum(WebhookStatus), default=WebhookStatus.PENDING)
    attempt_count = Column(Integer, default=0)
    immediate_attempts = Column(Integer, default=0)  # Track the 5-6 immediate attempts
    last_attempt_at = Column(DateTime, nullable=True)
    next_retry_at = Column(DateTime, nullable=True)
    acknowledged_at = Column(DateTime, nullable=True)
    response_status_code = Column(Integer, nullable=True)
    response_body = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    task_id = Column(String(255), nullable=True)  # Celery task ID for revocation
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    webhook = relationship("Webhook", back_populates="deliveries")
    notification = relationship("Notification", backref="webhook_deliveries")

    __table_args__ = (
        Index('idx_webhook_deliveries_status', status),
        Index('idx_webhook_deliveries_notification_id', notification_id),
        Index('idx_webhook_deliveries_next_retry_at', next_retry_at),
    )
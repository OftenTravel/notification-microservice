import uuid
from sqlalchemy import Column, String, DateTime, Text, ForeignKey, Enum as SQLAEnum, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base
from app.models.notification import NotificationStatus

class DeliveryAttempt(Base):
    """Model for tracking notification delivery attempts."""
    __tablename__ = "delivery_attempts"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    notification_id = Column(UUID(as_uuid=True), ForeignKey("notifications.id"), nullable=False)
    provider_id = Column(String(50), nullable=True)
    status = Column(SQLAEnum(NotificationStatus), nullable=False)
    error_message = Column(Text, nullable=True)
    attempted_at = Column(DateTime, default=datetime.utcnow)
    response_data = Column(JSONB, default={})
    
    # Relationship
    notification = relationship("Notification")
    
    # Index for efficient lookups
    __table_args__ = (
        Index('idx_delivery_attempts_notification_id', notification_id),
        Index('idx_delivery_attempts_attempted_at', attempted_at),
    )

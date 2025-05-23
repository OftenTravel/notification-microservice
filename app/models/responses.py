from pydantic import BaseModel
from enum import Enum
from typing import Optional, Any, Dict

class NotificationStatus(str, Enum):
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    QUEUED = "queued"
    SCHEDULED = "scheduled"
    UNKNOWN = "unknown"

class NotificationResponse(BaseModel):
    """Standard response for all notification operations."""
    success: bool
    status: NotificationStatus = NotificationStatus.UNKNOWN
    provider_name: str
    message_id: Optional[str] = None
    error_message: Optional[str] = None
    provider_response: Optional[Dict[str, Any]] = None

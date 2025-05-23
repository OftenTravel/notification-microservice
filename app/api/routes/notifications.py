from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, List
import uuid

from app.core.database import get_db
from app.models.notification import NotificationType
from pydantic import BaseModel

router = APIRouter()


class NotificationCreate(BaseModel):
    type: NotificationType
    recipient: str
    content: str
    send_immediately: bool = True


class NotificationResponse(BaseModel):
    id: str
    status: str
    recipient: str
    message: str


@router.get("/", response_model=List[Dict[str, Any]])
async def get_notifications(db: AsyncSession = Depends(get_db)):
    """List all notifications (placeholder)"""
    return [{"id": "test-id", "type": "sms", "status": "pending", "recipient": "test-recipient"}]


@router.post("/", response_model=NotificationResponse, status_code=status.HTTP_201_CREATED)
async def create_notification(
    notification: NotificationCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new notification (placeholder)"""
    # This is a placeholder implementation
    return {
        "id": str(uuid.uuid4()),
        "status": "pending",
        "recipient": notification.recipient,
        "message": "Notification created successfully"
    }

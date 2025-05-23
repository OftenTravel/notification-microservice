from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, List
import uuid

from app.core.database import get_db
from app.models.notification import NotificationType
from app.services.notification import NotificationService
from pydantic import BaseModel, Field

router = APIRouter()


class NotificationCreate(BaseModel):
    type: NotificationType
    recipient: str
    content: str
    send_immediately: bool = True


class NotificationResponse(BaseModel):
    id: str
    status: str
    type: str
    recipient: str
    created_at: str


@router.post("/notifications", response_model=NotificationResponse, status_code=status.HTTP_201_CREATED)
async def create_notification(
    notification: NotificationCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new notification"""
    notification_service = NotificationService(db)
    
    try:
        result = await notification_service.create_notification(
            notification_type=notification.type,
            recipient=notification.recipient,
            content=notification.content,
            send_immediately=notification.send_immediately
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create notification: {str(e)}"
        )


@router.get("/notifications/{notification_id}")
async def get_notification(
    notification_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    """Get notification status"""
    notification_service = NotificationService(db)
    
    try:
        result = await notification_service.get_notification_status(notification_id)
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get notification: {str(e)}"
        )


@router.post("/notifications/{notification_id}/send")
async def send_notification(
    notification_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    """Send a pending notification"""
    notification_service = NotificationService(db)
    
    try:
        result = await notification_service.send_notification(notification_id)
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send notification: {str(e)}"
        )

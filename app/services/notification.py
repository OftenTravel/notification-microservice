from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, Optional, List
import uuid

from app.models.notification import NotificationType, NotificationStatus
from app.repositories.notification import NotificationRepository
from app.providers.msg91_provider import MSG91Provider
from app.tasks.notification_tasks import send_notification_task


class NotificationService:
    """Service for notification handling"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.notification_repo = NotificationRepository(db)
        # Initialize providers
        self.providers = {
            NotificationType.SMS: MSG91Provider()
        }
    
    async def create_notification(
        self,
        notification_type: NotificationType,
        recipient: str,
        content: str,
        provider_id: Optional[uuid.UUID] = None,
        send_immediately: bool = True,
        **extra_data
    ) -> Dict[str, Any]:
        """Create and optionally send a notification"""
        
        # Create notification record
        notification = await self.notification_repo.create({
            "type": notification_type,
            "recipient": recipient,
            "content": content,
            "provider_id": provider_id,
            "status": NotificationStatus.PENDING
        })
        
        # Send immediately if requested (now using Celery)
        if send_immediately:
            # Queue the task in Celery
            send_notification_task.delay(str(notification.id))
        
        # Return response
        return {
            "id": str(notification.id),
            "type": notification.type.value,
            "status": notification.status.value,
            "recipient": notification.recipient,
            "created_at": notification.created_at.isoformat(),
            "message": "Notification queued for delivery" if send_immediately else "Notification created"
        }
    
    async def send_notification(self, notification_id: uuid.UUID) -> Dict[str, Any]:
        """Queue a specific notification for sending"""
        # Get notification
        notification = await self.notification_repo.get_by_id(notification_id)
        
        if not notification:
            raise ValueError(f"Notification {notification_id} not found")
        
        # Queue the task in Celery
        task = send_notification_task.delay(str(notification_id))
        
        return {
            "id": str(notification.id),
            "status": notification.status.value,
            "task_id": task.id,
            "message": "Notification queued for delivery"
        }
    
    async def get_notification_status(self, notification_id: uuid.UUID) -> Dict[str, Any]:
        """Get current status of a notification"""
        notification = await self.notification_repo.get_by_id(notification_id)
        
        if not notification:
            raise ValueError(f"Notification {notification_id} not found")
            
        return {
            "id": str(notification.id),
            "type": notification.type.value,
            "status": notification.status.value,
            "recipient": notification.recipient,
            "external_id": notification.external_id,
            "created_at": notification.created_at.isoformat(),
            "sent_at": notification.sent_at.isoformat() if notification.sent_at else None,
            "delivered_at": notification.delivered_at.isoformat() if notification.delivered_at else None
        }

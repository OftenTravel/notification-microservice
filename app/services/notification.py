from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, Optional, List
import uuid

from app.models.notification import NotificationType, NotificationStatus
from app.repositories.notification import NotificationRepository
from app.providers.msg91 import MSG91Provider


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
        
        # Send immediately if requested
        if send_immediately:
            await self.send_notification(notification.id)
            # Refresh notification to get updated status
            notification = await self.notification_repo.get_by_id(notification.id)
        
        # Return response
        return {
            "id": str(notification.id),
            "type": notification.type.value,
            "status": notification.status.value,
            "recipient": notification.recipient,
            "created_at": notification.created_at.isoformat()
        }
    
    async def send_notification(self, notification_id: uuid.UUID) -> Dict[str, Any]:
        """Send a specific notification"""
        # Get notification
        notification = await self.notification_repo.get_by_id(notification_id)
        
        if not notification:
            raise ValueError(f"Notification {notification_id} not found")
            
        if notification.status != NotificationStatus.PENDING:
            return {
                "id": str(notification.id),
                "status": notification.status.value,
                "message": f"Notification already in state: {notification.status.value}"
            }
            
        # Get appropriate provider
        provider = self.providers.get(notification.type)
        
        if not provider:
            await self.notification_repo.update_status(
                notification.id, 
                NotificationStatus.FAILED
            )
            raise ValueError(f"No provider configured for {notification.type.value}")
        
        try:
            # Send notification via provider
            provider_response = await provider.send(
                notification.recipient,
                notification.content
            )
            
            # Update notification status based on provider response
            new_status = NotificationStatus.SENT
            if provider_response.get("status") == "failed":
                new_status = NotificationStatus.FAILED
                
            # Update notification with provider's external ID and status
            notification = await self.notification_repo.update_status(
                notification.id,
                new_status,
                external_id=provider_response.get("external_id")
            )
            
            return {
                "id": str(notification.id),
                "status": notification.status.value,
                "external_id": notification.external_id,
                "sent_at": notification.sent_at.isoformat() if notification.sent_at else None,
                "provider_response": provider_response.get("response", {})
            }
            
        except Exception as e:
            # Update notification status to failed
            await self.notification_repo.update_status(
                notification.id, 
                NotificationStatus.FAILED
            )
            raise Exception(f"Failed to send notification: {str(e)}")
    
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

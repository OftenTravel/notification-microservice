from typing import Dict, List, Optional, Any, Union
from uuid import UUID
from sqlalchemy import select, update, desc
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
import logging

from app.models.notification import Notification, NotificationStatus, NotificationType, NotificationPriority

logger = logging.getLogger(__name__)

class NotificationRepository:
    """Repository for notification database operations."""
    
    def __init__(self, db: AsyncSession):
        """Initialize with database session."""
        self.db = db
    
    async def create(self, data: Dict[str, Any]) -> Notification:
        """Create a new notification."""
        notification = Notification(**data)
        self.db.add(notification)
        await self.db.commit()
        await self.db.refresh(notification)
        return notification
    
    async def get_by_id(self, notification_id: UUID) -> Optional[Notification]:
        """Get notification by ID."""
        return await self.db.get(Notification, notification_id)
    
    async def update_status(
        self, 
        notification_id: UUID, 
        status: NotificationStatus,
        error_message: Optional[str] = None,
        external_id: Optional[str] = None,
        provider_response: Optional[Dict] = None
    ) -> Optional[Notification]:
        """Update notification status and related fields."""
        notification = await self.get_by_id(notification_id)
        if not notification:
            return None
            
        # Update status and timestamps
        notification.status = status  # type: ignore
        notification.updated_at = datetime.utcnow()  # type: ignore
        
        # Set status-specific fields
        if status == NotificationStatus.DELIVERED:
            notification.delivered_at = datetime.utcnow()  # type: ignore
        elif status == NotificationStatus.FAILED:
            notification.failed_at = datetime.utcnow()  # type: ignore
            if error_message:
                notification.error_message = error_message  # type: ignore
        elif status == NotificationStatus.SENDING:
            notification.sent_at = datetime.utcnow()  # type: ignore
            
        # Set other fields if provided
        if external_id:
            notification.external_id = external_id  # type: ignore
        if provider_response:
            notification.provider_response = provider_response  # type: ignore
            
        await self.db.commit()
        await self.db.refresh(notification)
        return notification
    
    async def increment_retry_count(self, notification_id: UUID) -> Optional[Notification]:
        """Increment the retry count for a notification."""
        notification = await self.get_by_id(notification_id)
        if not notification:
            return None
            
        notification.retry_count += 1  # type: ignore
        await self.db.commit()
        await self.db.refresh(notification)
        return notification
    
    async def list_pending_notifications(
        self, 
        limit: int = 100, 
        notification_type: Optional[NotificationType] = None
    ) -> List[Notification]:
        """List pending notifications for processing."""
        query = select(Notification).where(Notification.status == NotificationStatus.PENDING)
        
        if notification_type:
            query = query.where(Notification.type == notification_type)
            
        query = query.order_by(
            # Process instant notifications first
            desc(Notification.is_instant),
            # Then by priority (higher priority first - using string comparison)
            desc(Notification.priority),
            # Then by creation date (oldest first)
            Notification.created_at
        ).limit(limit)
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def list_by_recipient(self, recipient: str, limit: int = 20) -> List[Notification]:
        """List notifications for a specific recipient."""
        query = select(Notification).where(Notification.recipient == recipient)
        query = query.order_by(desc(Notification.created_at)).limit(limit)
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def list_by_status(
        self, 
        status: NotificationStatus,
        limit: int = 100
    ) -> List[Notification]:
        """List notifications by status."""
        query = select(Notification).where(Notification.status == status)
        query = query.order_by(desc(Notification.updated_at)).limit(limit)
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def create_sms_notification(
        self, 
        recipient: str, 
        content: str,
        service_id: Optional[UUID] = None,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        provider_id: Optional[str] = None,
        meta_data: Optional[Dict[str, Any]] = None
    ) -> Notification:
        """Factory method for creating an SMS notification."""
        notification_data = {
            "service_id": service_id,
            "type": NotificationType.SMS,
            "recipient": recipient,
            "content": content, 
            "priority": priority,
            "provider_id": provider_id,
            "is_instant": (priority == NotificationPriority.INSTANT),
            "meta_data": meta_data or {}
        }
        return await self.create(notification_data)

    async def create_email_notification(
        self, 
        recipient: str, 
        subject: str, 
        body: str,
        service_id: Optional[UUID] = None,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        provider_id: Optional[str] = None,
        meta_data: Optional[Dict[str, Any]] = None
    ) -> Notification:
        """Factory method for creating an email notification."""
        notification_data = {
            "service_id": service_id,
            "type": NotificationType.EMAIL,
            "recipient": recipient,
            "subject": subject,
            "content": body,
            "priority": priority,
            "provider_id": provider_id,
            "is_instant": (priority == NotificationPriority.INSTANT),
            "meta_data": meta_data or {"subject": subject}
        }
        return await self.create(notification_data)

    async def create_whatsapp_notification(
        self, 
        recipient: str, 
        content: str,
        service_id: Optional[UUID] = None,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        provider_id: Optional[str] = None,
        meta_data: Optional[Dict[str, Any]] = None
    ) -> Notification:
        """Factory method for creating a WhatsApp notification."""
        notification_data = {
            "service_id": service_id,
            "type": NotificationType.WHATSAPP,
            "recipient": recipient,
            "content": content,
            "priority": priority,
            "provider_id": provider_id,
            "is_instant": (priority == NotificationPriority.INSTANT),
            "meta_data": meta_data or {}
        }
        return await self.create(notification_data)

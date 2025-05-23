from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, desc, and_, or_
from sqlalchemy.future import select

from app.models.notification import Notification, NotificationType, NotificationStatus
from app.models.delivery_attempt import DeliveryAttempt

class NotificationRepository:
    """Repository for notification database operations."""
    
    def __init__(self, db: AsyncSession):
        """
        Initialize with a database session.
        
        Args:
            db: SQLAlchemy async session
        """
        self.db = db
    
    async def create_notification(self, data: Dict[str, Any]) -> Notification:
        """
        Create a new notification record.
        
        Args:
            data: Notification data
            
        Returns:
            Notification: The created notification
        """
        notification = Notification(**data)
        self.db.add(notification)
        await self.db.commit()
        await self.db.refresh(notification)
        return notification
    
    async def get_notification(self, notification_id: UUID) -> Optional[Notification]:
        """
        Get a notification by ID.
        
        Args:
            notification_id: The notification ID
            
        Returns:
            Optional[Notification]: The notification if found
        """
        return await self.db.get(Notification, notification_id)
    
    async def update_notification(
        self, 
        notification_id: UUID, 
        data: Dict[str, Any]
    ) -> Optional[Notification]:
        """
        Update a notification.
        
        Args:
            notification_id: The notification ID
            data: Fields to update
            
        Returns:
            Optional[Notification]: The updated notification
        """
        notification = await self.get_notification(notification_id)
        if not notification:
            return None
            
        for key, value in data.items():
            setattr(notification, key, value)
            
        await self.db.commit()
        await self.db.refresh(notification)
        return notification
    
    async def update_notification_status(
        self,
        notification_id: UUID,
        status: NotificationStatus,
        provider_response: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None
    ) -> Optional[Notification]:
        """
        Update a notification's status.
        
        Args:
            notification_id: The notification ID
            status: The new status
            provider_response: Optional provider response data
            error_message: Optional error message
            
        Returns:
            Optional[Notification]: The updated notification
        """
        notification = await self.get_notification(notification_id)
        if not notification:
            return None
            
        # Update based on status
        update_data = {"status": status}
        
        if status == NotificationStatus.DELIVERED:
            update_data["delivered_at"] = datetime.utcnow()
        elif status == NotificationStatus.SENT:
            update_data["sent_at"] = datetime.utcnow()
        elif status == NotificationStatus.FAILED:
            update_data["failed_at"] = datetime.utcnow()
            update_data["error_message"] = error_message
            
        if provider_response:
            update_data["provider_response"] = provider_response
            
        # Extract provider message ID if available
        if provider_response and "message_id" in provider_response:
            update_data["external_id"] = provider_response["message_id"]
            
        return await self.update_notification(notification_id, update_data)
    
    async def list_pending_notifications(
        self, 
        limit: int = 100,
        notification_type: Optional[NotificationType] = None
    ) -> List[Notification]:
        """
        Get pending notifications for processing.
        
        Args:
            limit: Maximum number of records to return
            notification_type: Optional filter by type
            
        Returns:
            List[Notification]: Pending notifications
        """
        query = select(Notification).where(
            Notification.status == NotificationStatus.PENDING
        )
        
        if notification_type:
            query = query.where(Notification.type == notification_type)
            
        # Get scheduled notifications that are due or notifications without scheduling
        query = query.where(
            or_(
                Notification.scheduled_at <= datetime.utcnow(),
                Notification.scheduled_at == None
            )
        )
        
        # Order by priority and creation date
        query = query.order_by(
            desc(Notification.priority),
            Notification.created_at
        ).limit(limit)
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def record_delivery_attempt(
        self,
        notification_id: UUID,
        provider_id: str,
        status: NotificationStatus,
        response_data: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None
    ) -> DeliveryAttempt:
        """
        Record a delivery attempt.
        
        Args:
            notification_id: The notification ID
            provider_id: The provider ID
            status: The attempt status
            response_data: Optional response data
            error_message: Optional error message
            
        Returns:
            DeliveryAttempt: The created attempt record
        """
        attempt = DeliveryAttempt(
            notification_id=notification_id,
            provider_id=provider_id,
            status=status,
            response_data=response_data or {},
            error_message=error_message
        )
        
        self.db.add(attempt)
        await self.db.commit()
        await self.db.refresh(attempt)
        return attempt
    
    async def get_delivery_attempts(
        self, 
        notification_id: UUID
    ) -> List[DeliveryAttempt]:
        """
        Get delivery attempts for a notification.
        
        Args:
            notification_id: The notification ID
            
        Returns:
            List[DeliveryAttempt]: List of delivery attempts
        """
        query = select(DeliveryAttempt).where(
            DeliveryAttempt.notification_id == notification_id
        ).order_by(DeliveryAttempt.attempted_at)
        
        result = await self.db.execute(query)
        return result.scalars().all()

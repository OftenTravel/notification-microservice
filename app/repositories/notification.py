from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_
from datetime import datetime
from typing import List, Optional, Dict, Any
import uuid

from app.models.notification import Notification, NotificationStatus, NotificationType


class NotificationRepository:
    """Repository for notification operations"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create(self, notification_data: Dict[str, Any]) -> Notification:
        """Create a new notification"""
        notification = Notification(**notification_data)
        self.db.add(notification)
        await self.db.commit()
        await self.db.refresh(notification)
        return notification
    
    async def get_by_id(self, notification_id: uuid.UUID) -> Optional[Notification]:
        """Get notification by ID"""
        result = await self.db.execute(
            select(Notification).where(Notification.id == notification_id)
        )
        return result.scalars().first()
    
    async def get_pending_notifications(
        self, notification_type: Optional[NotificationType] = None, 
        limit: int = 50
    ) -> List[Notification]:
        """Get pending notifications"""
        query = select(Notification).where(
            Notification.status == NotificationStatus.PENDING
        )
        
        if notification_type:
            query = query.where(Notification.type == notification_type)
            
        query = query.order_by(Notification.created_at).limit(limit)
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def update_status(
        self, 
        notification_id: uuid.UUID,
        status: NotificationStatus,
        external_id: Optional[str] = None,
        additional_data: Optional[Dict[str, Any]] = None
    ) -> Optional[Notification]:
        """Update notification status"""
        update_data = {"status": status}
        
        if status == NotificationStatus.SENT:
            update_data["sent_at"] = datetime.utcnow()
            
        if status == NotificationStatus.DELIVERED:
            update_data["delivered_at"] = datetime.utcnow()
            
        if external_id:
            update_data["external_id"] = external_id
            
        await self.db.execute(
            update(Notification)
            .where(Notification.id == notification_id)
            .values(update_data)
        )
        await self.db.commit()
        
        return await self.get_by_id(notification_id)

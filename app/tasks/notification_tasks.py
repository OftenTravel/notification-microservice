import uuid
from app.core.celery import celery_app
from app.core.database import AsyncSessionLocal
from app.repositories.notification import NotificationRepository
from app.models.notification import NotificationStatus
from app.providers.msg91 import MSG91Provider
import structlog
import asyncio

logger = structlog.get_logger(__name__)


@celery_app.task(name="send_notification", bind=True, max_retries=3)
def send_notification_task(self, notification_id: str):
    """Celery task to send a notification"""
    try:
        # Run the async function in a new event loop
        return asyncio.run(_send_notification(notification_id))
    except Exception as exc:
        logger.error("Failed to send notification", 
                     notification_id=notification_id, 
                     error=str(exc),
                     retry_count=self.request.retries)
        # Retry with exponential backoff
        self.retry(exc=exc, countdown=2 ** self.request.retries * 60)


async def _send_notification(notification_id: str):
    """Async function to handle notification sending"""
    # Get DB session
    async with AsyncSessionLocal() as session:
        notification_repo = NotificationRepository(session)
        
        # Get notification
        notification = await notification_repo.get_by_id(uuid.UUID(notification_id))
        
        if not notification:
            logger.error("Notification not found", notification_id=notification_id)
            return {"status": "error", "message": f"Notification {notification_id} not found"}
            
        if notification.status != NotificationStatus.PENDING:
            logger.info("Notification already processed", 
                       notification_id=notification_id, 
                       status=notification.status.value)
            return {
                "id": str(notification.id),
                "status": notification.status.value,
                "message": f"Notification already in state: {notification.status.value}"
            }
        
        # Select appropriate provider based on notification type
        if notification.type.value == "sms":
            provider = MSG91Provider()
        else:
            await notification_repo.update_status(
                notification.id, 
                NotificationStatus.FAILED
            )
            return {"status": "failed", "message": f"No provider for {notification.type.value}"}
        
        try:
            # Send notification via provider
            provider_response = await provider.send(
                notification.recipient,
                notification.content
            )
            
            # Update status based on provider response
            new_status = NotificationStatus.SENT
            if provider_response.get("status") == "failed":
                new_status = NotificationStatus.FAILED
                
            # Update notification with provider's external ID and status
            notification = await notification_repo.update_status(
                notification.id,
                new_status,
                external_id=provider_response.get("external_id")
            )
            
            return {
                "id": str(notification.id),
                "status": notification.status.value,
                "external_id": notification.external_id,
                "provider_response": provider_response.get("response", {})
            }
            
        except Exception as e:
            # Update notification status to failed
            await notification_repo.update_status(
                notification.id, 
                NotificationStatus.FAILED
            )
            raise Exception(f"Failed to send notification: {str(e)}")

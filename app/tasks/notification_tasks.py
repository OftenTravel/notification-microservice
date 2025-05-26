import uuid
from app.core.celery_app import celery_app
from app.core.celery_database import create_celery_session
from app.repositories.notification_repository import NotificationRepository
from app.repositories.provider_repository import ProviderRepository
from app.models.notification import NotificationStatus
from app.providers.msg91_provider import MSG91Provider
from app.models.delivery_attempt import DeliveryAttempt
import structlog
import asyncio
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

# Only use structlog - remove the standard logger completely
logger = structlog.get_logger(__name__)

# Maximum number of retries for a notification
MAX_RETRIES = 3

# Retry delay in minutes: 5min, 15min, 30min
RETRY_DELAYS = [5, 15, 30]


@celery_app.task(name="send_notification_task", bind=True)
def send_notification_task(self, notification_id: str):
    """Celery task to send a notification"""
    print(f"Processing notification: {notification_id}")
    try:
        # Run the async function in a new event loop
        return asyncio.run(_send_notification(notification_id, retry_count=self.request.retries))
    except Exception as exc:
        logger.error("Failed to send notification", 
                    notification_id=notification_id, 
                    error=str(exc), 
                    retry=self.request.retries)
        
        # Only retry if we haven't exceeded the max retries
        if self.request.retries < MAX_RETRIES:
            # Calculate delay using exponential backoff with defined delays
            retry_idx = min(self.request.retries, len(RETRY_DELAYS) - 1)
            countdown = RETRY_DELAYS[retry_idx] * 60  # Convert minutes to seconds
            
            logger.info("Scheduling retry", 
                       retry_number=self.request.retries + 1, 
                       countdown=countdown, 
                       notification_id=notification_id)
            
            # Retry with calculated delay
            self.retry(exc=exc, countdown=countdown)
        else:
            logger.warning("Max retries exceeded", notification_id=notification_id)
            # Mark as permanently failed in a separate task
            mark_notification_failed.delay(notification_id, str(exc))


async def _send_notification(notification_id: str, retry_count: int = 0):
    """Async function to handle notification sending"""
    # Fix: Create a new session and engine for each task execution to avoid event loop conflicts
    CelerySessionLocal = create_celery_session()
    async with CelerySessionLocal() as session:
        try:
            notification_repo = NotificationRepository(session)
            provider_repo = ProviderRepository(session)
            
            # Get notification
            notification = await notification_repo.get_by_id(uuid.UUID(notification_id))
            
            if not notification:
                logger.error("Notification not found", notification_id=notification_id)
                return {"status": "error", "message": f"Notification {notification_id} not found"}
                
            if notification.status not in [NotificationStatus.PENDING, NotificationStatus.QUEUED]:
                logger.info("Notification already processed", 
                           notification_id=notification_id, 
                           status=notification.status.value)
                return {
                    "id": str(notification.id),
                    "status": notification.status.value,
                    "message": f"Notification already in state: {notification.status.value}"
                }
            
            # Check if notification was cancelled
            if notification.status == NotificationStatus.CANCELLED:
                logger.info("Notification was cancelled", notification_id=notification_id)
                return {
                    "id": str(notification.id),
                    "status": notification.status.value,
                    "message": "Notification was cancelled"
                }
            
            # Update to SENDING status
            await notification_repo.update_status(
                notification.id, 
                NotificationStatus.SENDING
            )
            
            # Create delivery attempt record
            delivery_attempt = DeliveryAttempt(
                notification_id=notification.id,
                status=NotificationStatus.SENDING,
                attempted_at=datetime.utcnow()
            )
            session.add(delivery_attempt)
            await session.commit()
            await session.refresh(delivery_attempt)
            
            # Get provider from database
            provider_entity = None
            if notification.provider_id:
                try:
                    provider_entity = await provider_repo.get_provider(uuid.UUID(notification.provider_id))
                except (ValueError, TypeError):
                    # If provider_id is not a valid UUID, try getting by name
                    provider_entity = await provider_repo.get_provider_by_name(notification.provider_id)
            
            if not provider_entity:
                # Fall back to default provider by notification type
                if notification.type.value == "sms" or notification.type.value == "whatsapp":
                    provider_entity = await provider_repo.get_provider_by_name("msg91")
                else:  # email
                    provider_entity = await provider_repo.get_provider_by_name("mock")
            
            if not provider_entity:
                # Update notification and delivery attempt status to failed
                await notification_repo.update_status(
                    notification.id, 
                    NotificationStatus.FAILED,
                    error_message="No suitable provider found"
                )
                
                delivery_attempt.status = NotificationStatus.FAILED
                delivery_attempt.error_message = "No suitable provider found"
                await session.commit()
                
                return {"status": "failed", "message": f"No provider found for {notification.type.value}"}
            
            try:
                # Initialize provider with config from database
                if provider_entity.name == "msg91":
                    provider = MSG91Provider(provider_entity.config)
                    provider.initialize_provider()
                else:
                    # For mock or other providers, implement as needed
                    from app.providers.mock_provider import MockProvider
                    provider = MockProvider(provider_entity.config)
                
                # Prepare the message based on notification type
                if notification.type.value == "sms":
                    from app.models.messages import SMSMessage
                    message = SMSMessage(
                        recipient=notification.recipient,
                        content=notification.content,
                        sender_id=provider_entity.config.get("sender_id"),
                        meta_data=notification.meta_data
                    )
                    response = await provider.send_sms(message)
                
                elif notification.type.value == "email":
                    from app.models.messages import EmailMessage
                    subject = notification.subject or notification.meta_data.get("subject", "Notification")
                    message = EmailMessage(
                        to=[notification.recipient],
                        subject=subject,
                        body=notification.content,
                        meta_data=notification.meta_data
                    )
                    response = await provider.send_email(message)
                    
                elif notification.type.value == "whatsapp":
                    from app.models.messages import WhatsAppMessage
                    message = WhatsAppMessage(
                        recipient=notification.recipient,
                        content=notification.content,
                        meta_data=notification.meta_data
                    )
                    response = await provider.send_whatsapp(message)
                
                # Update status based on provider response
                new_status = NotificationStatus.DELIVERED if response.success else NotificationStatus.FAILED
                
                # Update notification with provider's response
                notification = await notification_repo.update_status(
                    notification.id,
                    new_status,
                    error_message=response.error_message if not response.success else None,
                    external_id=response.message_id,
                    provider_response=response.provider_response
                )
                
                # Update delivery attempt
                delivery_attempt.status = new_status
                delivery_attempt.provider_id = provider_entity.name
                delivery_attempt.response_data = response.provider_response
                delivery_attempt.error_message = response.error_message if not response.success else None
                await session.commit()
                
                # If the provider failed, raise an exception to trigger retry
                if not response.success:
                    raise Exception(f"Provider failed: {response.error_message}")
                
                return {
                    "id": str(notification.id),
                    "status": notification.status.value,
                    "external_id": notification.external_id,
                    "provider_response": response.provider_response
                }
                
            except Exception as e:
                # Fix: Use proper structlog logging style
                logger.exception("Error sending notification", error=str(e))
                
                # Update notification and delivery attempt status to failed
                await notification_repo.update_status(
                    notification.id, 
                    NotificationStatus.FAILED,
                    error_message=str(e)
                )
                
                delivery_attempt.status = NotificationStatus.FAILED
                delivery_attempt.error_message = str(e)
                await session.commit()
                
                # Re-raise for retry mechanism
                raise Exception(f"Failed to send notification: {str(e)}")
        except Exception as e:
            # Add a catch-all exception handler to prevent database connection issues from propagating
            logger.exception("Unhandled exception in _send_notification", error=str(e))
            raise
        finally:
            # Clean up the engine to prevent connection pool issues
            if session.bind:
                await session.bind.dispose()


@celery_app.task(name="mark_notification_failed")
def mark_notification_failed(notification_id: str, error_message: str):
    """Mark a notification as permanently failed after all retries have been exhausted."""
    try:
        return asyncio.run(_mark_notification_failed(notification_id, error_message))
    except Exception as e:
        logger.error("Error marking notification as failed", error=str(e))


async def _mark_notification_failed(notification_id: str, error_message: str):
    """Mark a notification as permanently failed."""
    # Fix: Use a fresh session and engine for each task
    CelerySessionLocal = create_celery_session()
    async with CelerySessionLocal() as session:
        try:
            notification_repo = NotificationRepository(session)
            
            # Get notification
            notification = await notification_repo.get_by_id(uuid.UUID(notification_id))
            
            if not notification:
                logger.error("Notification not found", notification_id=notification_id)
                return
                
            # Update notification status to failed
            await notification_repo.update_status(
                notification.id,
                NotificationStatus.FAILED,
                error_message=f"Max retries exceeded: {error_message}"
            )
            
            # Create a final delivery attempt record
            delivery_attempt = DeliveryAttempt(
                notification_id=notification.id,
                status=NotificationStatus.FAILED,
                error_message=f"Max retries exceeded: {error_message}",
                attempted_at=datetime.utcnow()
            )
            session.add(delivery_attempt)
            await session.commit()
            
            logger.info("Notification marked as permanently failed", 
                       notification_id=notification_id,
                       error=error_message)
        except Exception as e:
            logger.exception("Error in _mark_notification_failed", error=str(e))
            raise
        finally:
            # Clean up the engine to prevent connection pool issues
            if session.bind:
                await session.bind.dispose()


@celery_app.task(name="send_instant_notification")
def send_instant_notification(notification_id: str):
    """Process an instant notification with high priority."""
    print(f"Processing INSTANT notification: {notification_id}")
    return send_notification_task(notification_id)

import uuid
from uuid import UUID
from app.core.celery_app import celery_app
from app.core.database import AsyncSessionLocal
from app.repositories.notification_repository import NotificationRepository
from app.repositories.provider_repository import ProviderRepository
from app.models.notification import NotificationStatus
from app.providers.msg91_provider import MSG91Provider
from app.models.delivery_attempt import DeliveryAttempt
from app.models.webhook import Webhook
import structlog
import asyncio
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy import select
import httpx

# Use only structlog for logging
logger = structlog.get_logger(__name__)

# Maximum number of retries for a notification
MAX_RETRIES = 3

# Retry delay in minutes: 5min, 15min, 30min
RETRY_DELAYS = [5, 15, 30]


async def send_webhook_immediately(
    session,
    notification,
    event_type: str,
    attempt_number: int,
    next_retry_at: Optional[datetime] = None,
    provider_response: Optional[Dict[str, Any]] = None,
    error_details: Optional[str] = None
):
    """Send webhook notifications immediately without queuing."""
    try:
        # Get active webhooks for the service
        webhooks_query = select(Webhook).where(
            Webhook.service_id == notification.service_id,
            Webhook.is_active == True
        )
        result = await session.execute(webhooks_query)
        webhooks = result.scalars().all()
        
        if not webhooks:
            logger.info(f"No active webhooks for service {notification.service_id}")
            return
        
        # Prepare webhook payload
        payload = {
            "notification_id": str(notification.id),
            "event_type": event_type,
            "status": notification.status.value,
            "timestamp": datetime.utcnow().isoformat(),
            "attempt_number": attempt_number,
            "max_attempts": MAX_RETRIES,
            "attempts_remaining": max(0, MAX_RETRIES - attempt_number),
            "notification_type": notification.type.value,
            "recipient": notification.recipient
        }
        
        if next_retry_at:
            payload["next_retry_at"] = next_retry_at.isoformat()
        
        if provider_response:
            payload["provider_response"] = provider_response
        
        if error_details:
            payload["error_details"] = error_details
        
        # Send to each webhook
        async with httpx.AsyncClient(timeout=10.0) as client:
            for webhook in webhooks:
                try:
                    response = await client.post(
                        webhook.url,
                        json=payload,
                        headers={
                            "Content-Type": "application/json",
                            "X-Webhook-Event": f"notification.{event_type}",
                            "X-Notification-Id": str(notification.id)
                        }
                    )
                    
                    if response.status_code != 200:
                        # Queue for retry
                        from app.tasks.webhook_tasks import retry_webhook
                        retry_webhook.apply_async(
                            args=[str(webhook.id), str(notification.id), event_type, payload],
                            queue='webhooks',
                            countdown=60  # 1 min delay
                        )
                        logger.warning(f"Webhook failed, queued for retry: {response.status_code}")
                except Exception as e:
                    # Network error - queue for retry
                    from app.tasks.webhook_tasks import retry_webhook
                    retry_webhook.apply_async(
                        args=[str(webhook.id), str(notification.id), event_type, payload],
                        queue='webhooks',
                        countdown=60
                    )
                    logger.error(f"Webhook error, queued for retry: {str(e)}")
                    
    except Exception as e:
        logger.error(f"Error sending webhooks: {str(e)}")


@celery_app.task(name="send_notification_task", bind=True)
def send_notification_task(self, notification_id: str):
    """Celery task to send a notification"""
    print(f"Processing notification: {notification_id}")
    
    # Store task ID for revocation
    task_id = self.request.id
    
    try:
        # Set event loop policy to prevent "Future attached to a different loop" errors
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy() if hasattr(asyncio, 'WindowsProactorEventLoopPolicy') else asyncio.DefaultEventLoopPolicy())
        
        # Create a new event loop for this task
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Run the async task in the new event loop
            return loop.run_until_complete(_send_notification(notification_id, retry_count=self.request.retries, task_id=task_id))
        finally:
            # Clean up the event loop
            loop.close()
    except Exception as exc:
        # Use string formatting instead of keyword arguments
        logger.error(f"Failed to send notification {notification_id}: {str(exc)}, retry count: {self.request.retries}")
        
        # Only retry if we haven't exceeded the max retries
        if self.request.retries < MAX_RETRIES:
            # Calculate delay using exponential backoff with defined delays
            retry_idx = min(self.request.retries, len(RETRY_DELAYS) - 1)
            countdown = RETRY_DELAYS[retry_idx] * 60  # Convert minutes to seconds
            
            # Use string formatting for logs
            logger.info(f"Scheduling retry #{self.request.retries + 1} in {countdown} seconds for notification {notification_id}")
            
            # Send retry scheduled webhook
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(_send_retry_scheduled_webhook(notification_id, self.request.retries + 1, countdown, str(exc)))
            finally:
                loop.close()
            
            # Retry with calculated delay
            self.retry(exc=exc, countdown=countdown)
        else:
            # Use string formatting for logs
            logger.warning(f"Max retries exceeded for notification {notification_id}")
            # Mark as permanently failed in a separate task
            mark_notification_failed.delay(notification_id, str(exc))


async def _send_retry_scheduled_webhook(notification_id: str, retry_number: int, countdown_seconds: int, error_message: str):
    """Send webhook for retry scheduled event."""
    async with AsyncSessionLocal() as session:
        try:
            notification_repo = NotificationRepository(session)
            notification = await notification_repo.get_by_id(uuid.UUID(notification_id))
            
            if notification:
                next_retry_at = datetime.utcnow() + timedelta(seconds=countdown_seconds)
                await send_webhook_immediately(
                    session,
                    notification,
                    "retry_scheduled",
                    retry_number,
                    next_retry_at=next_retry_at,
                    error_details=error_message
                )
        except Exception as e:
            logger.error(f"Error sending retry scheduled webhook: {str(e)}")


async def _send_notification(notification_id: str, retry_count: int = 0, task_id: Optional[str] = None):
    """Async function to handle notification sending"""
    # Fix: Create a new session for each task execution to avoid concurrent access issues
    async with AsyncSessionLocal() as session:
        try:
            notification_repo = NotificationRepository(session)
            provider_repo = ProviderRepository(session)
            
            # Get notification
            notification = await notification_repo.get_by_id(uuid.UUID(notification_id))
            
            if not notification:
                # Use string formatting for logs
                logger.error(f"Notification not found: {notification_id}")
                return {"status": "error", "message": f"Notification {notification_id} not found"}
                
            if notification.status not in [NotificationStatus.PENDING, NotificationStatus.QUEUED]:
                # Use string formatting for logs
                logger.info(f"Notification {notification_id} already processed with status {notification.status.value}")
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
            
            # Store task ID for revocation
            if task_id:
                notification.task_id = task_id
                await session.commit()
            
            # Send webhook for retry attempt (if this is a retry)
            if retry_count > 0:
                await send_webhook_immediately(
                    session,
                    notification,
                    "retry_attempted",
                    retry_count + 1
                )
            
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
            
            try:
                # Get provider
                provider_entity = None
                if notification.provider_id:
                    provider_entity = await provider_repo.get_provider(UUID(notification.provider_id))
                else:
                    # Get active provider for notification type
                    providers = await provider_repo.get_active_providers(notification.type.value)
                    if providers:
                        provider_entity = providers[0]  # Get highest priority provider
                
                if not provider_entity:
                    raise Exception(f"No active provider found for {notification.type.value}")
                
                # Log provider selection with retry count
                logger.info("Selected provider for notification", 
                          provider=provider_entity.name,
                          notification_id=notification_id,
                          retry_attempt=retry_count)
                
                # Initialize provider based on type
                if provider_entity.name == "msg91":
                    provider = MSG91Provider(provider_entity.config)
                    # Provider is already initialized in __init__
                elif provider_entity.name == "mock":
                    from app.providers.mock_provider import MockProvider
                    provider = MockProvider(provider_entity.config)
                    # Ensure mock provider is initialized if needed
                    if not hasattr(provider, 'http_client'):
                        provider.initialize_provider()
                else:
                    raise Exception(f"Unknown provider type: {provider_entity.name}")
                
                # Send notification based on type
                if notification.type.value == "sms":
                    from app.models.messages import SMSMessage
                    sms_message = SMSMessage(
                        recipient=notification.recipient,
                        content=notification.content,
                        provider_id=str(notification.provider_id) if notification.provider_id else None,
                        meta_data=notification.meta_data or {}
                    )
                    response = await provider.send_sms(sms_message)
                elif notification.type.value == "email":
                    from app.models.messages import EmailMessage
                    # Reconstruct the full EmailMessage from stored metadata
                    meta_data = notification.meta_data or {}
                    email_message = EmailMessage(
                        to=meta_data.get("to", [notification.recipient]),
                        subject=notification.subject or "Notification",
                        body=meta_data.get("body", notification.content),
                        html_body=meta_data.get("html_body", notification.content),
                        from_email=meta_data.get("from_email"),
                        from_name=meta_data.get("from_name"),
                        cc=meta_data.get("cc", []),
                        bcc=meta_data.get("bcc", []),
                        reply_to=meta_data.get("reply_to"),
                        attachments=meta_data.get("attachments"),
                        template_id=meta_data.get("template_id"),
                        domain=meta_data.get("domain"),
                        recipients=meta_data.get("recipients"),
                        provider_id=str(notification.provider_id) if notification.provider_id else None,
                        meta_data=meta_data
                    )
                    response = await provider.send_email(email_message)
                elif notification.type.value == "whatsapp":
                    from app.models.messages import WhatsAppMessage
                    whatsapp_message = WhatsAppMessage(
                        recipient=notification.recipient,
                        content=notification.content,
                        provider_id=str(notification.provider_id) if notification.provider_id else None,
                        meta_data=notification.meta_data or {}
                    )
                    response = await provider.send_whatsapp(whatsapp_message)
                else:
                    raise Exception(f"Unsupported notification type: {notification.type}")
                
                # Clean up provider
                await provider.close()
                
                # Determine new status
                new_status = NotificationStatus.DELIVERED if response.success else NotificationStatus.FAILED
                
                # Update notification with result
                await notification_repo.update_status(
                    notification.id,
                    status=new_status,
                    external_id=response.message_id,
                    error_message=response.error_message if not response.success else None
                )
                
                # Update delivery attempt
                delivery_attempt.external_id = response.message_id
                delivery_attempt.status = new_status
                delivery_attempt.provider_id = provider_entity.name
                delivery_attempt.response_data = response.provider_response
                delivery_attempt.error_message = response.error_message if not response.success else None
                await session.commit()
                
                # Send appropriate webhook based on status
                if response.success:
                    # Send delivered webhook
                    await send_webhook_immediately(
                        session,
                        notification,
                        "delivered",
                        retry_count + 1,
                        provider_response={
                            "status": "success",
                            "message": "Message delivered successfully",
                            "provider_message_id": response.message_id
                        }
                    )
                    logger.info("Notification delivered successfully", notification_id=str(notification.id))
                else:
                    # If the provider failed, raise an exception to trigger retry
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
            # Clean up the session and engine to prevent connection pool issues
            try:
                if session.bind:
                    await session.close()
                    await session.bind.dispose()
            except Exception as cleanup_e:
                logger.warning(f"Error during session cleanup: {str(cleanup_e)}")


@celery_app.task(name="mark_notification_failed")
def mark_notification_failed(notification_id: str, error_message: str):
    """Mark a notification as permanently failed after all retries have been exhausted."""
    try:
        # Create a new event loop for this task
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            return loop.run_until_complete(_mark_notification_failed(notification_id, error_message))
        finally:
            loop.close()
    except Exception as e:
        logger.error("Error marking notification as failed", error=str(e))


async def _mark_notification_failed(notification_id: str, error_message: str):
    """Mark a notification as permanently failed."""
    # Fix: Use a fresh session and engine for each task
    async with AsyncSessionLocal() as session:
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
            
            # Send failed webhook
            await send_webhook_immediately(
                session,
                notification,
                "failed",
                MAX_RETRIES + 1,
                error_details=f"Max retries exceeded: {error_message}"
            )
            
            logger.info("Notification marked as permanently failed", 
                       notification_id=notification_id,
                       error=error_message)
        except Exception as e:
            logger.exception("Error in _mark_notification_failed", error=str(e))
            raise
        finally:
            # Clean up the session and engine to prevent connection pool issues
            try:
                if session.bind:
                    await session.close()
                    await session.bind.dispose()
            except Exception as cleanup_e:
                logger.warning(f"Error during session cleanup: {str(cleanup_e)}")
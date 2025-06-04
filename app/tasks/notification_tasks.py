import uuid
from uuid import UUID
from app.core.celery_app import celery_app
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.core.config import settings
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
            print("\n" + "🔕 NO WEBHOOKS CONFIGURED")
            print("=" * 80)
            print(f"Service ID: {notification.service_id}")
            print(f"Notification ID: {notification.id}")
            print(f"Event: {event_type.upper()}")
            print("=" * 80)
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
        print("\n" + "📡 SENDING SERVICE WEBHOOKS")
        print("=" * 80)
        print(f"🎯 Event: {event_type.upper()}")
        print(f"📧 Notification ID: {str(notification.id)}")
        print(f"🏢 Service ID: {notification.service_id}")
        print(f"👤 Recipient: {notification.recipient}")
        print(f"📊 Attempt: {attempt_number}")
        print(f"🔗 Webhook Count: {len(webhooks)}")
        print("-" * 80)
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            for i, webhook in enumerate(webhooks, 1):
                print(f"📞 Webhook {i}/{len(webhooks)}: {webhook.url}")
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
                    
                    if response.status_code == 200:
                        print(f"   ✅ SUCCESS - Status: {response.status_code}")
                    else:
                        print(f"   ❌ FAILED - Status: {response.status_code}")
                        print(f"   🔄 QUEUING FOR RETRY in 60 seconds")
                        # Queue for retry
                        from app.tasks.webhook_tasks import retry_webhook
                        retry_webhook.apply_async(  # type: ignore
                            args=[str(webhook.id), str(notification.id), event_type, payload],
                            queue='webhooks',
                            countdown=60  # 1 min delay
                        )
                        logger.warning(f"Webhook failed, queued for retry: {response.status_code}")
                except Exception as e:
                    print(f"   💥 NETWORK ERROR: {str(e)}")
                    print(f"   🔄 QUEUING FOR RETRY in 60 seconds")
                    # Network error - queue for retry
                    from app.tasks.webhook_tasks import retry_webhook
                    retry_webhook.apply_async(  # type: ignore
                        args=[str(webhook.id), str(notification.id), event_type, payload],
                        queue='webhooks',
                        countdown=60
                    )
                    logger.error(f"Webhook error, queued for retry: {str(e)}")
        
        print("=" * 80)
                    
    except Exception as e:
        logger.error(f"Error sending webhooks: {str(e)}")


@celery_app.task(name="send_notification_task", bind=True)
def send_notification_task(self, notification_id: str):
    """Celery task to send a notification"""
    print(f"Processing notification: {notification_id}")
    
    # Store task ID for revocation
    task_id = self.request.id
    
    try:
        # Create a new event loop for this task to avoid conflicts
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Run the async task in the new event loop
            return loop.run_until_complete(_send_notification(notification_id, retry_count=self.request.retries, task_id=task_id))
        finally:
            # Clean up the event loop
            try:
                # Cancel all pending tasks
                pending = asyncio.all_tasks(loop)
                for task in pending:
                    task.cancel()
                # Run the loop until all tasks are cancelled
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            except:
                pass
            finally:
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
            mark_notification_failed.delay(notification_id, str(exc))  # type: ignore


async def _send_retry_scheduled_webhook(notification_id: str, retry_number: int, countdown_seconds: int, error_message: str):
    """Send webhook for retry scheduled event."""
    # Create a new engine for this task
    task_engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        pool_pre_ping=False,
        pool_size=1,
        max_overflow=0
    )
    
    # Create a new session factory for this task
    SessionLocal = async_sessionmaker(task_engine, class_=AsyncSession, expire_on_commit=False)
    
    try:
        async with SessionLocal() as session:
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
    finally:
        await task_engine.dispose()


async def _send_notification(notification_id: str, retry_count: int = 0, task_id: Optional[str] = None):
    """Async function to handle notification sending"""
    # Create a new engine for this task to avoid event loop issues
    task_engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        pool_pre_ping=False,  # Disable pool pre-ping to avoid event loop issues
        pool_size=1,
        max_overflow=0,
        connect_args={
            "server_settings": {"jit": "off"},
            "command_timeout": 60,
        }
    )
    
    # Create a new session factory for this task
    SessionLocal = async_sessionmaker(task_engine, class_=AsyncSession, expire_on_commit=False)
    
    try:
        async with SessionLocal() as session:
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
            if notification.status == NotificationStatus.CANCELLED:  # type: ignore
                logger.info("Notification was cancelled", notification_id=notification_id)
                return {
                    "id": str(notification.id),
                    "status": notification.status.value,
                    "message": "Notification was cancelled"
                }
            
            # Store task ID for revocation
            if task_id:
                notification.task_id = task_id  # type: ignore
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
                UUID(str(notification.id)),  # type: ignore
                NotificationStatus.SENDING
            )
            
            # Create delivery attempt record
            delivery_attempt = DeliveryAttempt(
                notification_id=UUID(str(notification.id)),  # type: ignore
                status=NotificationStatus.SENDING,
                attempted_at=datetime.utcnow()
            )
            session.add(delivery_attempt)
            await session.commit()
            
            try:
                # Get provider
                provider_entity = None
                if notification.provider_id is not None:  # type: ignore
                    logger.info(f"Looking for specific provider: {notification.provider_id}")
                    provider_entity = await provider_repo.get_provider(UUID(str(notification.provider_id)))  # type: ignore
                    if not provider_entity:
                        logger.warning(f"Provider {notification.provider_id} not found, falling back to active providers")
                
                # If no specific provider was found or none was specified, get active providers
                if not provider_entity:
                    # Get active provider for notification type
                    notification_type_lower = notification.type.value.lower()
                    logger.info(f"Looking for providers for notification type: {notification_type_lower}")
                    providers = await provider_repo.get_active_providers(notification_type_lower)
                    if providers:
                        provider_entity = providers[0]  # Get highest priority provider
                
                if not provider_entity:
                    raise Exception(f"No active provider found for {notification.type.value.lower()}")
                
                # Log provider selection with retry count
                logger.info("Selected provider for notification", 
                          provider=provider_entity.name,
                          notification_id=notification_id,
                          retry_attempt=retry_count)
                
                # Initialize provider based on type
                if provider_entity.name == "msg91":  # type: ignore
                    provider = MSG91Provider(provider_entity.config)  # type: ignore
                    # Provider is already initialized in __init__
                elif provider_entity.name == "mock":  # type: ignore
                    from app.providers.mock_provider import MockProvider
                    provider = MockProvider(provider_entity.config)  # type: ignore
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
                        provider_id=str(notification.provider_id) if notification.provider_id is not None else None,  # type: ignore
                        meta_data=notification.meta_data or {}  # type: ignore
                    )
                    response = await provider.send_sms(sms_message)
                elif notification.type.value == "email":
                    from app.models.messages import EmailMessage
                    # Reconstruct the full EmailMessage from stored metadata
                    meta_data = notification.meta_data or {}  # type: ignore
                    email_message = EmailMessage(
                        to=meta_data.get("to", [notification.recipient]),
                        subject=str(notification.subject) if notification.subject is not None else "Notification",  # type: ignore
                        body=meta_data.get("body", notification.content),
                        html_body=meta_data.get("html_body", notification.content),
                        from_email=meta_data.get("from_email"),
                        from_name=meta_data.get("from_name"),
                        cc=meta_data.get("cc", []),
                        bcc=meta_data.get("bcc", []),
                        reply_to=meta_data.get("reply_to"),
                        attachments=meta_data.get("attachments", []),  # type: ignore
                        template_id=meta_data.get("template_id"),
                        domain=meta_data.get("domain"),
                        recipients=meta_data.get("recipients"),
                        provider_id=str(notification.provider_id) if notification.provider_id is not None else None,  # type: ignore
                        meta_data=meta_data  # type: ignore
                    )
                    response = await provider.send_email(email_message)
                elif notification.type.value == "whatsapp":
                    from app.models.messages import WhatsAppMessage
                    whatsapp_message = WhatsAppMessage(
                        recipient=notification.recipient,
                        content=notification.content,
                        provider_id=str(notification.provider_id) if notification.provider_id is not None else None,  # type: ignore
                        meta_data=notification.meta_data or {}  # type: ignore
                    )
                    response = await provider.send_whatsapp(whatsapp_message)
                else:
                    raise Exception(f"Unsupported notification type: {notification.type}")
                
                # Clean up provider
                await provider.close()
                
                # Determine new status based on MSG91's response
                # For MSG91, success means the message was accepted, not delivered
                # Actual delivery status comes through webhooks
                if response.success:
                    new_status = NotificationStatus.QUEUED  # MSG91 accepted, waiting for delivery
                else:
                    new_status = NotificationStatus.FAILED
                
                # Extract MSG91 response data
                external_id_data = {}
                if response.provider_response and 'raw_response' in response.provider_response:
                    raw_response = response.provider_response['raw_response']
                    if isinstance(raw_response, dict) and 'data' in raw_response:
                        data = raw_response['data']
                        # Store all IDs returned by MSG91
                        external_id_data = {
                            'message_id': data.get('message_id'),
                            'unique_id': data.get('unique_id'),
                            'thread_id': data.get('thread_id'),
                            'id': data.get('id')  # Some responses have just 'id'
                        }
                        # Remove None values
                        external_id_data = {k: v for k, v in external_id_data.items() if v is not None}
                
                # Convert to JSON string for storage
                import json
                external_id_json = json.dumps(external_id_data) if external_id_data else None
                
                # Update notification with result
                await notification_repo.update_status(
                    UUID(str(notification.id)),  # type: ignore
                    status=new_status,
                    external_id=external_id_json,
                    error_message=response.error_message if not response.success else None
                )
                
                # Store the full response in meta_data
                if notification.meta_data is None:  # type: ignore
                    notification.meta_data = {}  # type: ignore
                notification.meta_data['msg91_send_response'] = response.provider_response  # type: ignore
                notification.sent_at = datetime.utcnow()  # type: ignore
                await session.commit()
                
                # Update delivery attempt
                delivery_attempt.external_id = response.message_id
                delivery_attempt.status = new_status  # type: ignore
                delivery_attempt.provider_id = provider_entity.name
                delivery_attempt.response_data = response.provider_response  # type: ignore
                delivery_attempt.error_message = response.error_message if not response.success else None  # type: ignore
                await session.commit()
                
                # For MSG91, don't send webhooks immediately since MSG91 will send them
                # based on actual delivery status
                if response.success:
                    logger.info("Notification queued successfully", notification_id=str(notification.id))
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
                    UUID(str(notification.id)),  # type: ignore
                    NotificationStatus.FAILED,
                    error_message=str(e)
                )
                
                delivery_attempt.status = NotificationStatus.FAILED  # type: ignore
                delivery_attempt.error_message = str(e)  # type: ignore
                await session.commit()
                
                # Re-raise for retry mechanism
                raise Exception(f"Failed to send notification: {str(e)}")
    except Exception as e:
        # Add a catch-all exception handler to prevent database connection issues from propagating
        logger.exception("Unhandled exception in _send_notification", error=str(e))
        raise
    finally:
        # Dispose of the engine to properly clean up connections
        await task_engine.dispose()


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
    # Create a new engine for this task
    task_engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        pool_pre_ping=False,
        pool_size=1,
        max_overflow=0
    )
    
    # Create a new session factory for this task
    SessionLocal = async_sessionmaker(task_engine, class_=AsyncSession, expire_on_commit=False)
    
    try:
        async with SessionLocal() as session:
            try:
                notification_repo = NotificationRepository(session)
                
                # Get notification
                notification = await notification_repo.get_by_id(uuid.UUID(notification_id))
                
                if not notification:
                    logger.error("Notification not found", notification_id=notification_id)
                    return
                    
                # Update notification status to failed
                await notification_repo.update_status(
                    UUID(str(notification.id)),  # type: ignore
                    NotificationStatus.FAILED,
                    error_message=f"Max retries exceeded: {error_message}"
                )
                
                # Create a final delivery attempt record
                delivery_attempt = DeliveryAttempt(
                    notification_id=UUID(str(notification.id)),  # type: ignore
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
        await task_engine.dispose()
from celery import shared_task
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.celery_database import get_celery_db_session
from app.models.webhook import Webhook, WebhookDelivery, WebhookStatus
from app.models.notification import Notification
from datetime import datetime, timedelta
import httpx
import logging
from typing import Dict, Any, Optional
import asyncio
from app.core.celery_app import celery_app

logger = logging.getLogger(__name__)

# Webhook retry configuration
WEBHOOK_RETRY_DELAYS = [60, 300, 900]  # 1min, 5min, 15min
MAX_WEBHOOK_RETRIES = 3


def should_retry_webhook(response_code: Optional[int], attempt_number: int) -> bool:
    """Determine if webhook should be retried based on response code and attempt number."""
    if response_code == 200:
        return False
    
    # Client errors - don't retry
    if response_code and 400 <= response_code < 500:
        return False
    
    # Server errors or network issues - retry up to max attempts
    if attempt_number < MAX_WEBHOOK_RETRIES:
        return True
    
    return False


def get_webhook_retry_delay(attempt_number: int) -> int:
    """Get retry delay for webhook based on attempt number."""
    if attempt_number <= 0 or attempt_number > len(WEBHOOK_RETRY_DELAYS):
        return WEBHOOK_RETRY_DELAYS[-1]
    return WEBHOOK_RETRY_DELAYS[attempt_number - 1]


@celery_app.task(name="retry_webhook", bind=True, max_retries=MAX_WEBHOOK_RETRIES)
def retry_webhook(
    self,
    webhook_id: str,
    notification_id: str,
    event_type: str,
    payload: Dict[str, Any]
):
    """Retry a failed webhook delivery."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(
            _retry_webhook_async(
                self,
                webhook_id,
                notification_id,
                event_type,
                payload
            )
        )
    finally:
        loop.close()


async def _retry_webhook_async(
    task,
    webhook_id: str,
    notification_id: str,
    event_type: str,
    payload: Dict[str, Any]
):
    """Async implementation of webhook retry."""
    async for db in get_celery_db_session():
        try:
            # Get webhook
            webhook = await db.get(Webhook, webhook_id)
            if not webhook or not webhook.is_active:
                logger.info(f"Webhook {webhook_id} not found or inactive")
                return
            
            # Check if we already have a successful delivery
            existing_query = select(WebhookDelivery).where(
                WebhookDelivery.webhook_id == webhook_id,
                WebhookDelivery.notification_id == notification_id,
                WebhookDelivery.status == WebhookStatus.ACKNOWLEDGED
            )
            result = await db.execute(existing_query)
            if result.scalar_one_or_none():
                logger.info(f"Webhook already delivered for notification {notification_id}")
                return
            
            # Get or create webhook delivery record
            delivery_query = select(WebhookDelivery).where(
                WebhookDelivery.webhook_id == webhook_id,
                WebhookDelivery.notification_id == notification_id
            )
            delivery_result = await db.execute(delivery_query)
            delivery = delivery_result.scalar_one_or_none()
            
            if not delivery:
                delivery = WebhookDelivery(
                    webhook_id=webhook_id,
                    notification_id=notification_id,
                    status=WebhookStatus.PENDING,
                    attempt_count=0
                )
                db.add(delivery)
                await db.commit()
                await db.refresh(delivery)
            
            # Store task ID for revocation
            delivery.task_id = task.request.id
            
            # Update attempt count
            delivery.attempt_count += 1
            delivery.last_attempt_at = datetime.utcnow()
            
            # Send webhook request
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        webhook.url,
                        json=payload,
                        headers={
                            "Content-Type": "application/json",
                            "X-Webhook-Event": f"notification.{event_type}",
                            "X-Notification-Id": notification_id,
                            "X-Event-Type": event_type,
                            "X-Webhook-Retry": str(delivery.attempt_count)
                        }
                    )
                    
                    delivery.response_status_code = response.status_code
                    delivery.response_body = response.text[:1000]  # Store first 1000 chars
                    
                    if response.status_code == 200:
                        # Success
                        delivery.status = WebhookStatus.ACKNOWLEDGED
                        delivery.acknowledged_at = datetime.utcnow()
                        await db.commit()
                        logger.info(f"Webhook delivered successfully for {event_type}")
                        return
                    else:
                        delivery.error_message = f"HTTP {response.status_code}: {response.text[:200]}"
                        
            except httpx.TimeoutException:
                delivery.error_message = "Request timeout"
                delivery.response_status_code = 0
            except httpx.NetworkError as e:
                delivery.error_message = f"Network error: {str(e)}"
                delivery.response_status_code = 0
            except Exception as e:
                delivery.error_message = f"Unexpected error: {str(e)}"
                delivery.response_status_code = 0
            
            # Determine if we should retry
            if should_retry_webhook(delivery.response_status_code, delivery.attempt_count):
                delivery.status = WebhookStatus.RETRYING
                retry_delay = get_webhook_retry_delay(delivery.attempt_count)
                delivery.next_retry_at = datetime.utcnow() + timedelta(seconds=retry_delay)
                await db.commit()
                
                logger.info(f"Retrying webhook in {retry_delay} seconds (attempt {delivery.attempt_count})")
                raise task.retry(countdown=retry_delay)
            else:
                # Mark as failed
                if delivery.response_status_code and 400 <= delivery.response_status_code < 500:
                    delivery.status = WebhookStatus.FAILED
                    delivery.error_message = f"Client error (4xx): {delivery.error_message}"
                else:
                    delivery.status = WebhookStatus.FAILED
                    delivery.error_message = f"Max retries exceeded: {delivery.error_message}"
                
                await db.commit()
                logger.error(f"Webhook delivery failed: {delivery.error_message}")
                
        except Exception as e:
            if hasattr(e, '__class__') and e.__class__.__name__ == 'Retry':
                # This is a Celery retry exception, let it propagate
                raise
            logger.error(f"Error in webhook delivery: {str(e)}")
            await db.rollback()
            raise
        finally:
            await db.close()
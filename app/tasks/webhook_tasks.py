from celery import shared_task
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.celery_database import get_celery_db_session
from app.models.webhook import Webhook, WebhookDelivery, WebhookStatus
from app.models.notification import Notification, NotificationStatus
from datetime import datetime, timedelta, timezone
import httpx
import json
import logging
from typing import Optional, Dict, Any
import asyncio
from app.core.celery_app import celery_app

logger = logging.getLogger(__name__)

# Configuration for webhook retries
IMMEDIATE_ATTEMPTS = 6  # Number of immediate attempts without delay
INITIAL_RETRY_DELAY = 60  # 1 minute for first retry after immediate attempts
MAX_RETRY_DELAY = 10800  # 3 hours max delay
BACKOFF_MULTIPLIER = 2  # Exponential backoff multiplier


@celery_app.task(name="send_webhook_notification", bind=True, max_retries=20)
def send_webhook_notification(self, notification_id: str):
    """
    Send webhook notifications for a successful notification.
    This task handles the immediate retry logic and exponential backoff.
    """
    # Run async function in sync context
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_send_webhook_notification_async(self, notification_id))
    finally:
        loop.close()


async def _send_webhook_notification_async(task, notification_id: str):
    """Async implementation of webhook notification sending."""
    async for db in get_celery_db_session():
        try:
            # Get notification
            notification = await db.get(Notification, notification_id)
            if not notification:
                logger.error(f"Notification {notification_id} not found")
                return
            
            # Only send webhooks for delivered notifications
            if notification.status != NotificationStatus.DELIVERED:
                logger.info(f"Notification {notification_id} not in DELIVERED status, skipping webhooks")
                return
            
            # Get active webhooks for the service
            webhooks_query = select(Webhook).where(
                Webhook.service_id == notification.service_id,
                Webhook.is_active == True
            )
            result = await db.execute(webhooks_query)
            webhooks = result.scalars().all()
            
            if not webhooks:
                logger.info(f"No active webhooks found for service {notification.service_id}")
                return
            
            # Process each webhook
            for webhook in webhooks:
                # Check if delivery already exists and is acknowledged
                delivery_query = select(WebhookDelivery).where(
                    WebhookDelivery.webhook_id == webhook.id,
                    WebhookDelivery.notification_id == notification.id
                )
                delivery_result = await db.execute(delivery_query)
                existing_delivery = delivery_result.scalar_one_or_none()
                
                if existing_delivery and existing_delivery.status == WebhookStatus.ACKNOWLEDGED:
                    logger.info(f"Webhook {webhook.id} already acknowledged for notification {notification_id}")
                    continue
                
                # Create or update webhook delivery record
                if not existing_delivery:
                    delivery = WebhookDelivery(
                        webhook_id=webhook.id,
                        notification_id=notification.id,
                        status=WebhookStatus.PENDING
                    )
                    db.add(delivery)
                    await db.commit()
                    await db.refresh(delivery)
                else:
                    delivery = existing_delivery
                
                # Queue individual webhook delivery
                send_single_webhook.delay(str(delivery.id))
                
        except Exception as e:
            logger.error(f"Error processing webhook notification: {str(e)}")
            raise
        finally:
            await db.close()


@celery_app.task(name="send_single_webhook", bind=True, max_retries=None)
def send_single_webhook(self, delivery_id: str):
    """Send a single webhook delivery with retry logic."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_send_single_webhook_async(self, delivery_id))
    finally:
        loop.close()


async def _send_single_webhook_async(task, delivery_id: str):
    """Async implementation of single webhook delivery."""
    async for db in get_celery_db_session():
        try:
            # Get delivery record
            delivery = await db.get(WebhookDelivery, delivery_id)
            if not delivery:
                logger.error(f"Webhook delivery {delivery_id} not found")
                return
            
            # Check if already acknowledged
            if delivery.status == WebhookStatus.ACKNOWLEDGED:
                logger.info(f"Webhook delivery {delivery_id} already acknowledged")
                return
            
            # Get webhook and notification details
            webhook = await db.get(Webhook, delivery.webhook_id)
            notification = await db.get(Notification, delivery.notification_id)
            
            if not webhook or not notification:
                logger.error(f"Webhook or notification not found for delivery {delivery_id}")
                return
            
            # Prepare webhook payload
            payload = {
                "notification_id": str(notification.id),
                "type": notification.type.value,
                "status": notification.status.value,
                "recipient": notification.recipient,
                "content": notification.content,
                "subject": notification.subject,
                "external_id": notification.external_id,
                "delivered_at": notification.delivered_at.isoformat() if notification.delivered_at else None,
                "retry_count": notification.retry_count,
                "webhook_attempt": delivery.attempt_count + 1,
                "webhook_status": "retry" if delivery.attempt_count > 0 else "initial"
            }
            
            # Update attempt count
            delivery.attempt_count += 1
            delivery.last_attempt_at = datetime.now(timezone.utc)
            
            # Determine if this is an immediate attempt
            if delivery.immediate_attempts < IMMEDIATE_ATTEMPTS:
                delivery.immediate_attempts += 1
                is_immediate = True
            else:
                is_immediate = False
            
            # Send webhook request
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        webhook.url,
                        json=payload,
                        headers={
                            "Content-Type": "application/json",
                            "X-Webhook-Event": "notification.delivered",
                            "X-Notification-Id": str(notification.id)
                        }
                    )
                    
                    delivery.response_status_code = response.status_code
                    delivery.response_body = response.text[:1000]  # Store first 1000 chars
                    
                    if response.status_code == 200:
                        # Success - mark as acknowledged
                        delivery.status = WebhookStatus.ACKNOWLEDGED
                        delivery.acknowledged_at = datetime.now(timezone.utc)
                        await db.commit()
                        logger.info(f"Webhook delivery {delivery_id} acknowledged")
                        return
                    else:
                        # Non-200 response, will retry
                        delivery.error_message = f"HTTP {response.status_code}: {response.text[:200]}"
                        
            except httpx.RequestError as e:
                delivery.error_message = f"Request error: {str(e)}"
                logger.error(f"Webhook request error for delivery {delivery_id}: {str(e)}")
            except Exception as e:
                delivery.error_message = f"Unexpected error: {str(e)}"
                logger.error(f"Unexpected error for webhook delivery {delivery_id}: {str(e)}")
            
            # Update status to retrying or failed
            if is_immediate and delivery.immediate_attempts < IMMEDIATE_ATTEMPTS:
                # Still have immediate attempts left
                delivery.status = WebhookStatus.RETRYING
                await db.commit()
                # Retry immediately
                task.retry(countdown=0)
            elif delivery.immediate_attempts >= IMMEDIATE_ATTEMPTS:
                # Calculate exponential backoff
                retry_number = delivery.attempt_count - IMMEDIATE_ATTEMPTS
                if retry_number < 0:
                    retry_number = 0
                    
                delay = min(
                    INITIAL_RETRY_DELAY * (BACKOFF_MULTIPLIER ** retry_number),
                    MAX_RETRY_DELAY
                )
                
                # Check if we've exceeded 3 hours total
                first_attempt = delivery.created_at
                time_elapsed = (datetime.now(timezone.utc) - first_attempt).total_seconds()
                
                if time_elapsed + delay > MAX_RETRY_DELAY:
                    # Mark as failed
                    delivery.status = WebhookStatus.FAILED
                    delivery.error_message = f"Exceeded maximum retry time (3 hours). Last error: {delivery.error_message}"
                    await db.commit()
                    logger.error(f"Webhook delivery {delivery_id} failed after exceeding retry time")
                    return
                
                # Schedule retry
                delivery.status = WebhookStatus.RETRYING
                delivery.next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=delay)
                await db.commit()
                
                logger.info(f"Scheduling webhook delivery {delivery_id} retry in {delay} seconds")
                task.retry(countdown=delay)
                
        except Exception as e:
            logger.error(f"Error in webhook delivery: {str(e)}")
            # Don't retry on database errors
            await db.rollback()
            raise
        finally:
            await db.close()


@celery_app.task(name="check_webhook_deliveries")
def check_webhook_deliveries():
    """
    Periodic task to check for any webhook deliveries that might have been missed.
    This ensures reliability in case of task failures.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_check_webhook_deliveries_async())
    finally:
        loop.close()


async def _check_webhook_deliveries_async():
    """Check for pending webhook deliveries that need processing."""
    async for db in get_celery_db_session():
        try:
            # Find deliveries that are retrying and past their retry time
            query = select(WebhookDelivery).where(
                WebhookDelivery.status == WebhookStatus.RETRYING,
                WebhookDelivery.next_retry_at <= datetime.now(timezone.utc)
            )
            result = await db.execute(query)
            deliveries = result.scalars().all()
            
            for delivery in deliveries:
                # Re-queue for processing
                send_single_webhook.delay(str(delivery.id))
                logger.info(f"Re-queued webhook delivery {delivery.id}")
                
            # Also check for notifications that should have webhooks but don't
            cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=5)
            notifications_query = select(Notification).where(
                Notification.status == NotificationStatus.DELIVERED,
                Notification.delivered_at <= cutoff_time
            )
            notifications_result = await db.execute(notifications_query)
            notifications = notifications_result.scalars().all()
            
            for notification in notifications:
                # Check if webhooks exist for this notification
                webhook_check = select(WebhookDelivery).where(
                    WebhookDelivery.notification_id == notification.id
                )
                webhook_result = await db.execute(webhook_check)
                if not webhook_result.scalar_one_or_none():
                    # No webhook deliveries found, trigger webhook notification
                    send_webhook_notification.delay(str(notification.id))
                    logger.info(f"Triggered missing webhook for notification {notification.id}")
                    
        except Exception as e:
            logger.error(f"Error checking webhook deliveries: {str(e)}")
        finally:
            await db.close()
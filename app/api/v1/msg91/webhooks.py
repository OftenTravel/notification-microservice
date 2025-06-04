from fastapi import APIRouter, Depends, HTTPException, Header, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Dict, Any, Optional
from datetime import datetime
import hashlib
import hmac
import json
import structlog
import redis
import asyncio

from app.core.database import get_db
from app.core.config import settings
from app.models.notification import Notification, NotificationStatus
from app.models.delivery_attempt import DeliveryAttempt
from app.models.webhook import Webhook
from pydantic import BaseModel
import httpx

logger = structlog.get_logger(__name__)

router = APIRouter()

# Redis client for webhook deduplication
try:
    redis_client = redis.Redis.from_url("redis://redis:6379/0", decode_responses=True)
except Exception as e:
    logger.warning(f"Redis connection failed, webhook deduplication disabled: {e}")
    redis_client = None


class MSG91WebhookPayload(BaseModel):
    """MSG91 Webhook payload structure"""
    data: Dict[str, Any]
    
    class Config:
        extra = "allow"


def verify_msg91_webhook_signature(
    payload: str,
    signature: Optional[str] = None,
    webhook_secret: Optional[str] = None
) -> bool:
    """Verify MSG91 webhook signature using HMAC"""
    if not signature or not webhook_secret:
        return False
    
    # Calculate expected signature
    expected_signature = hmac.new(
        webhook_secret.encode('utf-8'),
        payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    # Compare signatures
    return hmac.compare_digest(signature, expected_signature)


def generate_webhook_key(unique_id: str, event_title: str, timestamp: str) -> str:
    """Generate a unique key for webhook deduplication"""
    key_data = f"{unique_id}:{event_title}:{timestamp}"
    return f"webhook:msg91:{hashlib.md5(key_data.encode()).hexdigest()}"


async def is_webhook_processed(webhook_key: str) -> bool:
    """Check if webhook was already processed using Redis"""
    if not redis_client:
        return False
    
    try:
        # Run Redis operation in thread to avoid blocking
        loop = asyncio.get_event_loop()
        exists = await loop.run_in_executor(None, redis_client.exists, webhook_key)
        return bool(exists)
    except Exception as e:
        logger.warning(f"Redis check failed: {e}")
        return False


async def mark_webhook_processed(webhook_key: str) -> None:
    """Mark webhook as processed in Redis with 3 hour TTL"""
    if not redis_client:
        return
    
    try:
        # Run Redis operation in thread to avoid blocking
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None, 
            lambda: redis_client.setex(webhook_key, 10800, "processed") if redis_client else None  # type: ignore
        )
    except Exception as e:
        logger.warning(f"Redis set failed: {e}")


async def send_service_webhooks(db: AsyncSession, notification, event_type: str, event_data: Dict[str, Any]):
    """Send webhooks to configured services when notification status changes"""
    try:
        # Get active webhooks for the service
        webhooks_query = select(Webhook).where(
            Webhook.service_id == notification.service_id,
            Webhook.is_active == True
        )
        result = await db.execute(webhooks_query)
        webhooks = result.scalars().all()
        
        if not webhooks:
            print("\n" + "🔕 NO SERVICE WEBHOOKS CONFIGURED")
            print("=" * 80)
            print(f"Service ID: {notification.service_id}")
            print(f"Notification ID: {notification.id}")
            print(f"Event: {event_type.upper()}")
            print("=" * 80)
            return
        
        # Prepare webhook payload
        payload = {
            "notification_id": str(notification.id),
            "event_type": f"msg91.{event_type}",
            "status": notification.status.value,
            "timestamp": datetime.utcnow().isoformat(),
            "notification_type": notification.type.value,
            "recipient": notification.recipient,
            "msg91_data": event_data
        }
        
        # Send to each webhook
        print("\n" + "📡 SENDING SERVICE WEBHOOKS (FROM MSG91 UPDATE)")
        print("=" * 80)
        print(f"🎯 Event: msg91.{event_type.upper()}")
        print(f"📧 Notification ID: {str(notification.id)}")
        print(f"🏢 Service ID: {notification.service_id}")
        print(f"👤 Recipient: {notification.recipient}")
        print(f"📊 Status: {notification.status.value}")
        print(f"🔗 Webhook Count: {len(webhooks)}")
        print("-" * 80)
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            for i, webhook in enumerate(webhooks, 1):
                print(f"📞 Webhook {i}/{len(webhooks)}: {webhook.url}")
                try:
                    response = await client.post(
                        str(webhook.url),  # type: ignore
                        json=payload,
                        headers={
                            "Content-Type": "application/json",
                            "X-Webhook-Event": f"notification.msg91.{event_type}",
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
                            args=[str(webhook.id), str(notification.id), f"msg91.{event_type}", payload],
                            queue='webhooks',
                            countdown=60  # 1 min delay
                        )
                        logger.warning(f"Service webhook failed for MSG91 event, queued for retry: {response.status_code}")
                except Exception as e:
                    print(f"   💥 NETWORK ERROR: {str(e)}")
                    print(f"   🔄 QUEUING FOR RETRY in 60 seconds")
                    # Network error - queue for retry
                    from app.tasks.webhook_tasks import retry_webhook
                    retry_webhook.apply_async(  # type: ignore
                        args=[str(webhook.id), str(notification.id), f"msg91.{event_type}", payload],
                        queue='webhooks',
                        countdown=60
                    )
                    logger.error(f"Service webhook error for MSG91 event, queued for retry: {str(e)}")
        
        print("=" * 80)
                    
    except Exception as e:
        logger.error(f"Error sending service webhooks for MSG91 event: {str(e)}")


@router.post("/webhook")
async def receive_msg91_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_msg91_signature: Optional[str] = Header(None, alias="X-MSG91-Signature")
):
    """
    Receive webhook from MSG91 for email delivery status updates.
    
    MSG91 sends webhooks for various email events:
    - Queued
    - Sent
    - Delivered
    - Bounced
    - Failed
    - Opened
    - Clicked
    """
    try:
        # Get raw body for signature verification
        body = await request.body()
        body_str = body.decode('utf-8')
        
        # Verify webhook signature if secret is configured
        webhook_secret = getattr(settings, 'MSG91_WEBHOOK_SECRET', None)
        if webhook_secret:
            if not verify_msg91_webhook_signature(body_str, x_msg91_signature, webhook_secret):
                logger.warning("Invalid MSG91 webhook signature")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid webhook signature"
                )
        
        # Parse the webhook payload
        payload = json.loads(body_str)
        webhook_data = MSG91WebhookPayload(**payload)
        
        # Extract relevant data from webhook
        data = webhook_data.data
        outbound_email = data.get('outbound_email', {})
        recipient_info = data.get('recipient', {})
        event_info = data.get('event', {})
        
        # Extract IDs from the webhook
        unique_id = outbound_email.get('unique_id')
        message_id = outbound_email.get('message_id')
        thread_id = outbound_email.get('id')  # MSG91 sends thread_id as 'id' in outbound_email
        template_id = outbound_email.get('template_id')
        event_title = event_info.get('title', '').lower()
        
        # Check for duplicate webhook using Redis
        webhook_timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M')  # Minute precision
        webhook_key = generate_webhook_key(unique_id or str(thread_id), event_title, webhook_timestamp)
        
        if await is_webhook_processed(webhook_key):
            print("\n" + "="*80)
            print(f"🔄 DUPLICATE MSG91 WEBHOOK IGNORED - {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
            print("="*80)
            print(f"Event: {event_title.upper()}")
            print(f"Unique ID: {unique_id}")
            print(f"Already processed within the last 3 hours")
            print("="*80)
            
            logger.info(
                "Duplicate MSG91 webhook ignored",
                unique_id=unique_id,
                message_id=message_id,
                thread_id=thread_id,
                event_title=event_title,
                webhook_key=webhook_key
            )
            
            return {
                "status": "success",
                "message": "Duplicate webhook ignored"
            }
        
        # Mark webhook as processed
        await mark_webhook_processed(webhook_key)
        
        # Log the webhook event with clear formatting
        print("\n" + "="*80)
        print(f"🔔 MSG91 WEBHOOK RECEIVED - {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
        print("="*80)
        print(f"Event: {event_title.upper()}")
        print(f"Unique ID: {unique_id}")
        print(f"Message ID: {message_id}")
        print(f"Thread ID: {thread_id}")
        print(f"Template ID: {template_id}")
        print(f"Recipient: {recipient_info.get('email')}")
        print("-"*80)
        
        logger.info(
            "Received MSG91 webhook",
            unique_id=unique_id,
            message_id=message_id,
            thread_id=thread_id,
            event_title=event_title,
            recipient=recipient_info.get('email')
        )
        
        # Find the notification by external_id (which should contain the unique_id)
        if unique_id or message_id or thread_id:
            # Query for notifications where external_id might contain our IDs
            # external_id is stored as JSON string, so we need to search for the ID values
            query = select(Notification).where(
                Notification.external_id.isnot(None)
            )
            result = await db.execute(query)
            notifications = result.scalars().all()
            
            # Search through notifications to find matching ID
            notification = None
            for notif in notifications:
                try:
                    if notif.external_id is not None:  # type: ignore
                        # Parse the JSON string
                        external_ids = json.loads(str(notif.external_id))  # type: ignore
                        if isinstance(external_ids, dict):
                            # Check if any of our IDs match
                            if (unique_id and external_ids.get('unique_id') == unique_id) or \
                               (message_id and external_ids.get('message_id') == message_id) or \
                               (thread_id and external_ids.get('thread_id') == thread_id) or \
                               (unique_id and external_ids.get('id') == unique_id):
                                notification = notif
                                break
                except json.JSONDecodeError:
                    # If it's not JSON, try direct string match for backward compatibility
                    if (unique_id and unique_id in str(notif.external_id)) or \
                       (message_id and message_id in str(notif.external_id)) or \
                       (thread_id and str(thread_id) in str(notif.external_id)):  # type: ignore
                        notification = notif
                        break
            
            if notification:
                # Update notification status based on event
                previous_status = notification.status
                
                # Map MSG91 events to our notification statuses
                status_mapping = {
                    'queued': NotificationStatus.QUEUED,
                    'sent': NotificationStatus.SENDING,
                    'delivered': NotificationStatus.DELIVERED,
                    'bounced': NotificationStatus.FAILED,
                    'failed': NotificationStatus.FAILED,
                    'opened': NotificationStatus.SEEN,
                    'clicked': NotificationStatus.SEEN
                }
                
                new_status = status_mapping.get(event_title)
                if new_status:
                    notification.status = new_status  # type: ignore
                    
                    # Update timestamps
                    if new_status == NotificationStatus.DELIVERED:
                        notification.delivered_at = datetime.utcnow()  # type: ignore
                    elif new_status == NotificationStatus.FAILED:
                        notification.failed_at = datetime.utcnow()  # type: ignore
                        # Extract error message from recipient meta
                        error_reason = recipient_info.get('meta', {}).get('reason')
                        if error_reason:
                            notification.error_message = str(error_reason)  # type: ignore
                    elif new_status == NotificationStatus.SEEN:
                        # For seen status, only update if not already delivered
                        if notification.status != NotificationStatus.DELIVERED:  # type: ignore
                            notification.delivered_at = datetime.utcnow()  # type: ignore
                
                # Update meta_data with webhook information
                if notification.meta_data is None:  # type: ignore
                    notification.meta_data = {}  # type: ignore
                
                # Store webhook data
                if 'webhook_events' not in notification.meta_data:  # type: ignore
                    notification.meta_data['webhook_events'] = []  # type: ignore
                
                notification.meta_data['webhook_events'].append({  # type: ignore
                    'event': event_title,
                    'timestamp': datetime.utcnow().isoformat(),
                    'data': {
                        'status_code': data.get('status_code'),
                        'enhanced_status_code': data.get('enhanced_status_code'),
                        'opened': data.get('opened'),
                        'clicked': data.get('clicked'),
                        'reason': data.get('reason'),
                        'recipient_meta': recipient_info.get('meta', {})
                    }
                })
                
                # Store the full webhook payload
                notification.meta_data['last_webhook_data'] = payload  # type: ignore
                
                # Update the notification
                notification.updated_at = datetime.utcnow()  # type: ignore
                await db.commit()
                
                # Create a delivery attempt record for this webhook event
                delivery_attempt = DeliveryAttempt(
                    notification_id=notification.id,
                    provider_id=str(notification.provider_id) if notification.provider_id is not None else 'msg91',  # type: ignore
                    status=new_status if new_status else notification.status,
                    error_message=notification.error_message if new_status == NotificationStatus.FAILED else None,  # type: ignore
                    response_data={
                        'webhook_event': event_title,
                        'webhook_data': data
                    }
                )
                db.add(delivery_attempt)
                await db.commit()
                
                print(f"\n✅ NOTIFICATION UPDATED")
                print(f"Notification ID: {str(notification.id)}")
                print(f"Previous Status: {previous_status.value}")
                print(f"New Status: {new_status.value if new_status else 'unchanged'}")
                print("="*80)
                
                # Send webhooks to services if status changed
                if new_status and new_status != previous_status:
                    await send_service_webhooks(
                        db, 
                        notification, 
                        event_title,
                        {
                            'previous_status': previous_status.value,
                            'new_status': new_status.value,
                            'msg91_event': event_title,
                            'msg91_data': data
                        }
                    )
                
                logger.info(
                    "Updated notification from MSG91 webhook",
                    notification_id=str(notification.id),
                    previous_status=previous_status.value,
                    new_status=new_status.value if new_status else "unchanged"
                )
                
                return {
                    "status": "success",
                    "message": "Webhook processed successfully",
                    "notification_id": str(notification.id)
                }
            else:
                print(f"\n⚠️  NOTIFICATION NOT FOUND")
                print(f"Searched for unique_id: {unique_id}")
                print(f"Searched for message_id: {message_id}")
                print(f"Searched for thread_id: {thread_id}")
                print("="*80)
                
                logger.warning(
                    "Notification not found for MSG91 webhook",
                    unique_id=unique_id,
                    message_id=message_id,
                    thread_id=thread_id
                )
                return {
                    "status": "warning",
                    "message": "Notification not found"
                }
        else:
            logger.warning("MSG91 webhook missing unique_id")
            return {
                "status": "error",
                "message": "Missing unique_id in webhook payload"
            }
            
    except json.JSONDecodeError:
        logger.error("Invalid JSON in MSG91 webhook")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid JSON payload"
        )
    except Exception as e:
        logger.exception("Error processing MSG91 webhook", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/webhook/test")
async def test_msg91_webhook():
    """Test endpoint to verify MSG91 webhook is accessible"""
    return {
        "status": "success",
        "message": "MSG91 webhook endpoint is active",
        "timestamp": datetime.utcnow().isoformat()
    }
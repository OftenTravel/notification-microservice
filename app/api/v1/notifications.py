from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Optional, Dict, Any
from uuid import UUID

from app.core.database import get_db
from app.models.messages import SMSMessage, EmailMessage, WhatsAppMessage
from app.models.responses import NotificationResponse
from app.models.delivery_attempt import DeliveryAttempt
from app.models.notification import NotificationStatus, NotificationType, Notification
from app.models.service_user import ServiceUser
from app.services.notification_service import NotificationService
from app.core.exceptions import NotificationException, ProviderNotFoundError
from app.repositories.provider_repository import ProviderRepository
from app.repositories.notification_repository import NotificationRepository
from app.tasks.notification_tasks import MAX_RETRIES
from app.core.auth import get_current_service

router = APIRouter()

# Initialize notification service
notification_service = NotificationService(default_provider_name="mock")



# SMS endpoint
@router.post("/sms", response_model=NotificationResponse)
async def send_sms(
    message: SMSMessage,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    service: ServiceUser = Depends(get_current_service),
    priority: Optional[str] = None,
):
    """
    Send an SMS notification.

    - **recipient**: Phone number of the recipient
    - **content**: SMS content to send
    - **provider_id** (optional): Override the default provider in request body
    - **sender_id** (optional): Sender ID to use if supported by the provider
    - **priority** (optional): Priority level (low, normal, high, instant)
    """
    try:
        response = await notification_service.send_sms(
            message=message,
            priority=priority,
            db=db,
            service_id=service.id
        )
        return response
    except ProviderNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except NotificationException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

# Email endpoint
@router.post("/email", response_model=NotificationResponse)
async def send_email(
    message: EmailMessage,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    service: ServiceUser = Depends(get_current_service),
    priority: Optional[str] = None,
):
    """
    Send an email notification.

    - **to**: List of recipient email addresses
    - **subject**: Email subject
    - **body**: Email body content (plain text)
    - **html_body** (optional): HTML version of the email body
    - **provider_id** (optional): Override the default provider in request body
    - **priority** (optional): Priority level (low, normal, high, instant)
    """
    try:
        # Extract provider_id from message if provided
        provider_id = None
        if message.provider_id:
            try:
                provider_id = UUID(message.provider_id)
            except (ValueError, TypeError):
                raise HTTPException(status_code=400, detail="Invalid provider_id format")
        
        response = await notification_service.send_email(
            message=message,
            provider_id=provider_id,
            priority=priority,
            db=db,
            service_id=service.id
        )
        return response
    except ProviderNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except NotificationException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

# WhatsApp endpoint
@router.post("/whatsapp", response_model=NotificationResponse)
async def send_whatsapp(
    message: WhatsAppMessage,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    service: ServiceUser = Depends(get_current_service),
    priority: Optional[str] = None,
):
    """
    Send a WhatsApp notification.

    - **recipient**: Phone number of the recipient (with country code)
    - **content**: Message content to send
    - **media_url** (optional): URL to media to include
    - **template_id** (optional): Template ID if using WhatsApp templates
    - **provider_id** (optional): Override the default provider in request body
    - **priority** (optional): Priority level (low, normal, high, instant)
    """
    try:
        response = await notification_service.send_whatsapp(
            message=message,
            priority=priority,
            db=db,
            service_id=service.id
        )
        return response
    except ProviderNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except NotificationException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

# Provider listing endpoint
@router.get("/providers")
async def list_providers(
    db: AsyncSession = Depends(get_db),
    service: ServiceUser = Depends(get_current_service)
):
    """List all available notification providers from database."""
    try:
        repo = ProviderRepository(db)
        providers = await repo.list_providers()
        return [
            {
                "id": str(provider.id),
                "name": provider.name,
                "supported_types": provider.supported_types,
                "is_active": provider.is_active,
                "priority": provider.priority
            }
            for provider in providers
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list providers: {str(e)}")


# Get notification details endpoint
@router.get("/notifications/{notification_id}")
async def get_notification_details(
    notification_id: UUID,
    db: AsyncSession = Depends(get_db),
    service: ServiceUser = Depends(get_current_service)
) -> Dict[str, Any]:
    """
    Get detailed information about a notification including:
    - Notification status and metadata
    - All delivery attempts
    - Retry information (retries left, next retry time)
    - Task status
    """
    try:
        # Get notification
        notification_repo = NotificationRepository(db)
        notification = await notification_repo.get_by_id(notification_id)
        
        if not notification:
            raise HTTPException(status_code=404, detail=f"Notification {notification_id} not found")
        
        # Verify notification belongs to the authenticated service
        if notification.service_id != service.id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Get delivery attempts
        query = (
            select(DeliveryAttempt)
            .where(DeliveryAttempt.notification_id == notification_id)
            .order_by(DeliveryAttempt.attempted_at)
        )
        result = await db.execute(query)
        delivery_attempts = result.scalars().all()
        
        # Calculate retries left
        retries_left = MAX_RETRIES - notification.retry_count
        
        # Get task status from Celery (if available)
        task_status = None
        task_eta = None
        
        # Try to find active task for this notification
        # Note: This requires task ID to be stored, which we don't have in current implementation
        # For now, we'll indicate if it's likely queued for retry based on status
        if notification.status == NotificationStatus.FAILED and retries_left > 0:
            task_status = "RETRY_PENDING"
        
        return {
            "notification": {
                "id": str(notification.id),
                "service_id": str(notification.service_id) if notification.service_id else None,
                "type": notification.type.value,
                "status": notification.status.value,
                "recipient": notification.recipient,
                "subject": notification.subject,
                "content": notification.content,
                "priority": notification.priority.value,
                "is_instant": notification.is_instant,
                "retry_count": notification.retry_count,
                "retries_left": retries_left,
                "error_message": notification.error_message,
                "external_id": notification.external_id,
                "provider_response": notification.provider_response,
                "created_at": notification.created_at.isoformat(),
                "updated_at": notification.updated_at.isoformat(),
                "sent_at": notification.sent_at.isoformat() if notification.sent_at else None,
                "delivered_at": notification.delivered_at.isoformat() if notification.delivered_at else None,
                "failed_at": notification.failed_at.isoformat() if notification.failed_at else None,
                "scheduled_at": notification.scheduled_at.isoformat() if notification.scheduled_at else None,
            },
            "delivery_attempts": [
                {
                    "id": str(attempt.id),
                    "status": attempt.status.value,
                    "provider_id": attempt.provider_id,
                    "error_message": attempt.error_message,
                    "attempted_at": attempt.attempted_at.isoformat(),
                    "response_data": attempt.response_data
                }
                for attempt in delivery_attempts
            ],
            "task_info": {
                "status": task_status,
                "eta": task_eta,
                "max_retries": MAX_RETRIES
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get notification details: {str(e)}")


# Revoke/Cancel notification endpoint
@router.post("/notifications/{notification_id}/revoke")
async def revoke_notification(
    notification_id: UUID,
    db: AsyncSession = Depends(get_db),
    service: ServiceUser = Depends(get_current_service)
) -> Dict[str, str]:
    """
    Revoke/cancel a notification. This will:
    - Update notification status to CANCELLED
    - Attempt to revoke any pending Celery tasks
    - Prevent further retries
    - Send cancellation webhook
    """
    try:
        from app.core.celery_app import celery_app
        from app.models.webhook import WebhookDelivery, WebhookStatus
        from datetime import datetime
        
        # Get notification
        notification_repo = NotificationRepository(db)
        notification = await notification_repo.get_by_id(notification_id)
        
        if not notification:
            raise HTTPException(status_code=404, detail=f"Notification {notification_id} not found")
        
        # Verify notification belongs to the authenticated service
        if notification.service_id != service.id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Check if notification can be cancelled
        if notification.status in [NotificationStatus.DELIVERED, NotificationStatus.FAILED, NotificationStatus.CANCELLED]:
            raise HTTPException(
                status_code=400, 
                detail=f"Cannot revoke notification in {notification.status.value} status"
            )
        
        # Revoke the notification task if it exists
        if notification.task_id:
            try:
                celery_app.control.revoke(notification.task_id, terminate=True)
            except Exception as e:
                # Log error but continue with cancellation
                print(f"Failed to revoke notification task {notification.task_id}: {e}")
        
        # Revoke any pending webhook tasks
        webhook_query = (
            select(WebhookDelivery)
            .where(WebhookDelivery.notification_id == notification_id)
            .where(WebhookDelivery.status.in_([WebhookStatus.PENDING, WebhookStatus.RETRYING]))
        )
        webhook_result = await db.execute(webhook_query)
        webhook_deliveries = webhook_result.scalars().all()
        
        for webhook_delivery in webhook_deliveries:
            if webhook_delivery.task_id:
                try:
                    celery_app.control.revoke(webhook_delivery.task_id, terminate=True)
                except Exception as e:
                    print(f"Failed to revoke webhook task {webhook_delivery.task_id}: {e}")
            
            # Update webhook delivery status
            webhook_delivery.status = WebhookStatus.FAILED
            webhook_delivery.error_message = "Notification cancelled"
            webhook_delivery.updated_at = datetime.utcnow()
        
        # Update notification status to CANCELLED
        await notification_repo.update_status(
            notification_id,
            NotificationStatus.CANCELLED,
            error_message="Revoked by user"
        )
        
        # Send cancellation webhook
        from app.tasks.notification_tasks import send_webhook_immediately
        from app.models.webhook import Webhook
        
        # Get active webhooks for the service
        webhook_query = (
            select(Webhook)
            .where(Webhook.service_id == service.id)
            .where(Webhook.is_active == True)
        )
        webhook_result = await db.execute(webhook_query)
        webhooks = webhook_result.scalars().all()
        
        # Send cancellation webhook to each endpoint
        for _ in webhooks:
            await send_webhook_immediately(
                session=db,
                notification=notification,
                event_type="cancelled",
                attempt_number=0,
                error_details="Notification cancelled by user"
            )
        
        await db.commit()
        
        return {
            "message": f"Notification {notification_id} has been revoked",
            "status": "CANCELLED"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to revoke notification: {str(e)}")


# Get all notifications for a service
@router.get("/notifications")
async def list_service_notifications(
    db: AsyncSession = Depends(get_db),
    service: ServiceUser = Depends(get_current_service),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status: Optional[NotificationStatus] = None,
    notification_type: Optional[NotificationType] = None
) -> Dict[str, Any]:
    """
    List all notifications for the authenticated service.
    
    - **skip**: Number of notifications to skip (for pagination)
    - **limit**: Maximum number of notifications to return (max: 1000)
    - **status**: Filter by notification status
    - **notification_type**: Filter by notification type (sms, email, whatsapp)
    """
    try:
        # Build query
        query = (
            select(Notification)
            .where(Notification.service_id == service.id)
            .order_by(Notification.created_at.desc())
        )
        
        # Apply filters
        if status:
            query = query.where(Notification.status == status)
        if notification_type:
            query = query.where(Notification.type == notification_type)
            
        # Get total count
        count_query = select(func.count()).select_from(Notification).where(Notification.service_id == service.id)
        if status:
            count_query = count_query.where(Notification.status == status)
        if notification_type:
            count_query = count_query.where(Notification.type == notification_type)
            
        total_result = await db.execute(count_query)
        total_count = total_result.scalar_one()
        
        # Apply pagination
        query = query.offset(skip).limit(limit)
        
        # Execute query
        result = await db.execute(query)
        notifications = result.scalars().all()
        
        return {
            "total": total_count,
            "skip": skip,
            "limit": limit,
            "notifications": [
                {
                    "id": str(notification.id),
                    "type": notification.type.value,
                    "status": notification.status.value,
                    "recipient": notification.recipient,
                    "subject": notification.subject,
                    "priority": notification.priority.value,
                    "retry_count": notification.retry_count,
                    "error_message": notification.error_message,
                    "created_at": notification.created_at.isoformat(),
                    "updated_at": notification.updated_at.isoformat(),
                    "sent_at": notification.sent_at.isoformat() if notification.sent_at else None,
                    "delivered_at": notification.delivered_at.isoformat() if notification.delivered_at else None
                }
                for notification in notifications
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list notifications: {str(e)}")

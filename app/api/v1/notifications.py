from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional, Dict, Any
from uuid import UUID
import uuid

from app.core.database import get_db
from app.models.messages import SMSMessage, EmailMessage, WhatsAppMessage
from app.models.responses import NotificationResponse
from app.models.delivery_attempt import DeliveryAttempt
from app.models.notification import NotificationStatus
from app.services.notification_service import NotificationService
from app.core.exceptions import NotificationException, ProviderNotFoundError
from app.repositories.provider_repository import ProviderRepository
from app.repositories.notification_repository import NotificationRepository
from app.core.celery_app import celery_app
from app.tasks.notification_tasks import MAX_RETRIES

router = APIRouter()

# Initialize notification service
notification_service = NotificationService(default_provider_name="mock")

# SMS endpoint
@router.post("/sms", response_model=NotificationResponse)
async def send_sms(
    message: SMSMessage,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
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
            db=db
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
        response = await notification_service.send_email(
            message=message,
            priority=priority,
            db=db
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
            db=db
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
async def list_providers(db: AsyncSession = Depends(get_db)):
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
    db: AsyncSession = Depends(get_db)
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
    db: AsyncSession = Depends(get_db)
) -> Dict[str, str]:
    """
    Revoke/cancel a notification. This will:
    - Update notification status to CANCELLED
    - Attempt to revoke any pending Celery tasks
    - Prevent further retries
    """
    try:
        # Get notification
        notification_repo = NotificationRepository(db)
        notification = await notification_repo.get_by_id(notification_id)
        
        if not notification:
            raise HTTPException(status_code=404, detail=f"Notification {notification_id} not found")
        
        # Check if notification can be cancelled
        if notification.status in [NotificationStatus.DELIVERED, NotificationStatus.CANCELLED]:
            raise HTTPException(
                status_code=400, 
                detail=f"Cannot revoke notification in {notification.status.value} status"
            )
        
        # Update notification status to CANCELLED
        await notification_repo.update_status(
            notification_id,
            NotificationStatus.CANCELLED,
            error_message="Revoked by user"
        )
        
        # Note: We don't have the Celery task ID stored in the database
        # In a production system, you'd want to store the task_id when creating the notification
        # For now, we'll just update the status which will prevent processing if the task runs
        
        return {
            "message": f"Notification {notification_id} has been revoked",
            "status": "CANCELLED"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to revoke notification: {str(e)}")

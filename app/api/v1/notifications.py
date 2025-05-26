from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from uuid import UUID

from app.core.database import get_db
from app.models.messages import SMSMessage, EmailMessage, WhatsAppMessage
from app.models.responses import NotificationResponse
from app.services.notification_service import NotificationService
from app.core.exceptions import NotificationException, ProviderNotFoundError
from app.repositories.provider_repository import ProviderRepository

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

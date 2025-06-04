from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from uuid import UUID
from datetime import datetime

from app.core.database import get_db
from app.core.auth import get_current_service
from app.models.service_user import ServiceUser
from app.models.webhook import Webhook, WebhookDelivery, WebhookStatus
from pydantic import BaseModel, HttpUrl


router = APIRouter()


class WebhookCreate(BaseModel):
    url: HttpUrl
    description: str
    is_active: bool = True


class WebhookUpdate(BaseModel):
    url: Optional[HttpUrl] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None 


class WebhookResponse(BaseModel):
    id: UUID
    service_id: UUID
    url: str
    description: str 
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class WebhookDeliveryResponse(BaseModel):
    id: UUID
    webhook_id: UUID
    notification_id: UUID
    status: WebhookStatus
    attempt_count: int
    last_attempt_at: datetime 
    response_status_code: int 
    error_message: str 
    created_at: datetime

    class Config:
        from_attributes = True


@router.post("/", response_model=WebhookResponse, status_code=status.HTTP_201_CREATED)
async def create_webhook(
    webhook_data: WebhookCreate,
    db: AsyncSession = Depends(get_db),
    service: ServiceUser = Depends(get_current_service)
):
    """Create a new webhook for the authenticated service."""
    webhook = Webhook(
        service_id=service.id,
        url=str(webhook_data.url),
        description=webhook_data.description,
        is_active=webhook_data.is_active
    )
    db.add(webhook)
    await db.commit()
    await db.refresh(webhook)
    return webhook


@router.get("/", response_model=List[WebhookResponse])
async def list_webhooks(
    db: AsyncSession = Depends(get_db),
    service: ServiceUser = Depends(get_current_service),
    active_only: bool = False
):
    """List all webhooks for the authenticated service."""
    query = select(Webhook).where(Webhook.service_id == service.id)
    if active_only:
        query = query.where(Webhook.is_active == True)
    
    result = await db.execute(query.order_by(Webhook.created_at.desc()))
    webhooks = result.scalars().all()
    return webhooks


@router.get("/{webhook_id}", response_model=WebhookResponse)
async def get_webhook(
    webhook_id: UUID,
    db: AsyncSession = Depends(get_db),
    service: ServiceUser = Depends(get_current_service)
):
    """Get a specific webhook by ID."""
    result = await db.execute(
        select(Webhook).where(
            Webhook.id == webhook_id,
            Webhook.service_id == service.id
        )
    )
    webhook = result.scalar_one_or_none()
    
    if not webhook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Webhook not found"
        )
    
    return webhook


@router.patch("/{webhook_id}", response_model=WebhookResponse)
async def update_webhook(
    webhook_id: UUID,
    webhook_update: WebhookUpdate,
    db: AsyncSession = Depends(get_db),
    service: ServiceUser = Depends(get_current_service)
):
    """Update a webhook."""
    result = await db.execute(
        select(Webhook).where(
            Webhook.id == webhook_id,
            Webhook.service_id == service.id
        )
    )
    webhook = result.scalar_one_or_none()
    
    if not webhook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Webhook not found"
        )
    
    # Update webhook fields
    if webhook_update.url is not None:
        webhook.url = str(webhook_update.url)  # type: ignore
    if webhook_update.description is not None:
        webhook.description = webhook_update.description  # type: ignore
    if webhook_update.is_active is not None:
        webhook.is_active = webhook_update.is_active  # type: ignore
    
    webhook.updated_at = datetime.utcnow()  # type: ignore
    
    await db.commit()
    await db.refresh(webhook)
    return webhook


@router.delete("/{webhook_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_webhook(
    webhook_id: UUID,
    db: AsyncSession = Depends(get_db),
    service: ServiceUser = Depends(get_current_service)
):
    """Delete a webhook."""
    result = await db.execute(
        select(Webhook).where(
            Webhook.id == webhook_id,
            Webhook.service_id == service.id
        )
    )
    webhook = result.scalar_one_or_none()
    
    if not webhook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Webhook not found"
        )
    
    await db.delete(webhook)
    await db.commit()


@router.get("/{webhook_id}/deliveries", response_model=List[WebhookDeliveryResponse])
async def list_webhook_deliveries(
    webhook_id: UUID,
    db: AsyncSession = Depends(get_db),
    service: ServiceUser = Depends(get_current_service),
    limit: int = 100
):
    """List delivery attempts for a specific webhook."""
    # First verify the webhook belongs to the service
    webhook_result = await db.execute(
        select(Webhook).where(
            Webhook.id == webhook_id,
            Webhook.service_id == service.id
        )
    )
    webhook = webhook_result.scalar_one_or_none()
    
    if not webhook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Webhook not found"
        )
    
    # Get deliveries
    result = await db.execute(
        select(WebhookDelivery)
        .where(WebhookDelivery.webhook_id == webhook_id)
        .order_by(WebhookDelivery.created_at.desc())
        .limit(limit)
    )
    deliveries = result.scalars().all()
    return deliveries
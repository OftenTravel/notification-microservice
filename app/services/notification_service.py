from typing import Dict, Any, Optional, Union, List
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
import logging
import hashlib
from datetime import datetime, timedelta
from sqlalchemy import select, func

from app.models.messages import SMSMessage, EmailMessage, WhatsAppMessage, Recipient
from app.models.responses import NotificationResponse
from app.core.exceptions import ProviderNotFoundError, NotificationException, ValidationException
from app.repositories.provider_repository import ProviderRepository
from app.providers.msg91_provider import MSG91Provider
from app.providers.mock_provider import MockProvider
from app.repositories.notification_repository import NotificationRepository
from app.models.notification import NotificationType, NotificationStatus, NotificationPriority, Notification
from app.models.delivery_attempt import DeliveryAttempt
from app.tasks.notification_tasks import send_notification_task

logger = logging.getLogger(__name__)

class NotificationService:
    """Service for sending notifications using database-managed providers."""
    
    # Default deduplication window in minutes
    DEDUPLICATION_WINDOW_MINUTES = 30
    
    def __init__(self, default_provider_name: Optional[str] = "mock"):
        self.default_provider_name = default_provider_name
    
    async def _get_provider_instance(self, provider_entity):
        """Create provider instance based on provider name."""
        if provider_entity.name == "msg91":
            return MSG91Provider(provider_entity.config)
        elif provider_entity.name == "mock":
            return MockProvider(provider_entity.config)
        else:
            raise ProviderNotFoundError(f"Unknown provider type: {provider_entity.name}")
    
    def _generate_message_fingerprint(self, message_type: str, recipient: str, content: str, subject: Optional[str] = None) -> str:
        """Generate a fingerprint for a message to detect duplicates."""
        # Combine relevant fields into a single string
        fingerprint_base = f"{message_type}:{recipient}:{content}"
        if subject:
            fingerprint_base += f":{subject}"
            
        # Create a hash of the string
        return hashlib.md5(fingerprint_base.encode('utf-8')).hexdigest()
    
    async def _is_duplicate_notification(
        self,
        db: AsyncSession, 
        message_type: str,
        recipient: str,
        content: str,
        subject: Optional[str] = None,
        window_minutes: Optional[int] = None
    ) -> bool:
        """Check if a similar notification was sent recently."""
        if window_minutes is None:
            window_minutes = self.DEDUPLICATION_WINDOW_MINUTES
            
        # Generate fingerprint for this message
        fingerprint = self._generate_message_fingerprint(message_type, recipient, content, subject)
        
        # Calculate the time threshold
        time_threshold = datetime.utcnow() - timedelta(minutes=window_minutes)
        
        # Query for similar messages in the time window
        query = (
            select(func.count())
            .select_from(Notification)
            .where(
                Notification.recipient == recipient,
                Notification.type == message_type,
                Notification.content == content,
                Notification.created_at >= time_threshold,
                # Skip failed messages since they should be retried
                Notification.status != NotificationStatus.FAILED
            )
        )
        
        # Add subject check for emails
        if message_type == NotificationType.EMAIL and subject:
            query = query.where(Notification.subject == subject)
        
        result = await db.execute(query)
        count = result.scalar_one()
        
        return count > 0
    
    # Helper method to process old and new message formats
    def _process_message(self, message: Union[SMSMessage, EmailMessage, WhatsAppMessage]) -> Union[SMSMessage, EmailMessage, WhatsAppMessage]:
        """Process message to ensure it has the correct structure."""
        # Messages are already properly structured according to their models
        return message
    
    async def create_notification(
        self,
        notification_type: NotificationType,
        recipient: str,
        content: str,
        subject: Optional[str] = None,
        service_id: Optional[uuid.UUID] = None,
        provider_id: Optional[str] = None,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        meta_data: Optional[Dict[str, Any]] = None,
        check_duplicates: bool = True,
        deduplication_window: Optional[int] = None,
        db: Optional[AsyncSession] = None
    ) -> Dict[str, Any]:
        """Create a notification record in the database and queue it for delivery."""
        if not db:
            raise ValueError("Database session is required")
            
        # Create notification repository
        notification_repo = NotificationRepository(db)
        
        # Check for duplicates if enabled
        if check_duplicates and deduplication_window is not None:
            is_duplicate = await self._is_duplicate_notification(
                db=db,
                message_type=notification_type.value,
                recipient=recipient,
                content=content,
                subject=subject,
                window_minutes=deduplication_window
            )
            
            if is_duplicate:
                raise ValidationException(
                    f"Duplicate notification detected for {recipient} within deduplication window"
                )
        
        # Create notification based on type
        if notification_type == NotificationType.SMS:
            notification = await notification_repo.create_sms_notification(
                recipient=recipient,
                content=content,
                service_id=service_id,
                priority=priority,
                provider_id=provider_id,
                meta_data=meta_data
            )
        elif notification_type == NotificationType.EMAIL:
            if not subject:
                raise ValueError("Subject is required for email notifications")
                
            notification = await notification_repo.create_email_notification(
                recipient=recipient,
                subject=subject,
                body=content,
                service_id=service_id,
                priority=priority,
                provider_id=provider_id,
                meta_data=meta_data
            )
        elif notification_type == NotificationType.WHATSAPP:
            notification = await notification_repo.create_whatsapp_notification(
                recipient=recipient,
                content=content,
                service_id=service_id,
                priority=priority,
                provider_id=provider_id,
                meta_data=meta_data
            )
        else:
            raise ValueError(f"Unsupported notification type: {notification_type}")
        
        # Queue notification for delivery based on priority with SIMPLIFIED TASK NAMES
        # All notifications use the same task, but priority affects queue routing
        task = send_notification_task.delay(str(notification.id))  # type: ignore
        if priority == NotificationPriority.INSTANT:
            logger.info(f"Queued instant notification {notification.id}, task ID: {task.id}")
        else:
            logger.info(f"Queued standard notification {notification.id}, task ID: {task.id}")
            
        # Return response with task info
        return {
            "id": str(notification.id),
            "type": notification.type.value,
            "status": notification.status.value,
            "recipient": notification.recipient,
            "created_at": notification.created_at.isoformat(),
            "task_id": task.id if task else None
        }
    
    async def get_notification_history(
        self,
        notification_id: uuid.UUID,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Get detailed notification history including all delivery attempts."""
        # Get notification
        notification_repo = NotificationRepository(db)
        notification = await notification_repo.get_by_id(notification_id)
        
        if not notification:
            raise ProviderNotFoundError(f"Notification {notification_id} not found")
            
        # Get delivery attempts
        query = (
            select(DeliveryAttempt)
            .where(DeliveryAttempt.notification_id == notification_id)
            .order_by(DeliveryAttempt.attempted_at)
        )
        
        result = await db.execute(query)
        attempts = list(result.scalars().all())
        
        # Format response
        return {
            "notification": {
                "id": str(notification.id),
                "type": notification.type.value,
                "status": notification.status.value,
                "recipient": notification.recipient,
                "content": notification.content,
                "subject": notification.subject,
                "provider_id": notification.provider_id,
                "external_id": notification.external_id,
                "created_at": notification.created_at.isoformat(),
                "sent_at": notification.sent_at.isoformat() if notification.sent_at is not None else None,  # type: ignore
                "delivered_at": notification.delivered_at.isoformat() if notification.delivered_at is not None else None,  # type: ignore
                "failed_at": notification.failed_at.isoformat() if notification.failed_at is not None else None,  # type: ignore
                "retry_count": notification.retry_count,
                "error_message": notification.error_message
            },
            "delivery_attempts": [
                {
                    "id": str(attempt.id),
                    "status": attempt.status.value,
                    "provider_id": attempt.provider_id,
                    "attempted_at": attempt.attempted_at.isoformat(),
                    "error_message": attempt.error_message
                }
                for attempt in attempts
            ]
        }
    
    async def send_email(
        self, 
        message: EmailMessage,
        provider_id: Optional[uuid.UUID] = None,
        service_id: Optional[uuid.UUID] = None,
        priority: Optional[str] = None,
        db: Optional[AsyncSession] = None
    ) -> NotificationResponse:
        """
        Send an email message directly.
        Note: For production use, prefer create_notification method to benefit from queue system.
        """
        if not db:
            raise ValueError("Database session is required")
        
        # Process message to ensure proper structure    
        message = self._process_message(message)  # type: ignore
        
        # Store notification in database and queue for delivery
        notification_priority = NotificationPriority.NORMAL
        if priority == "instant":
            notification_priority = NotificationPriority.INSTANT
        elif priority == "high":
            notification_priority = NotificationPriority.HIGH
        elif priority == "low":
            notification_priority = NotificationPriority.LOW
        
        # If using direct sending for compatibility, create the notification and queue it
        subject = message.subject or ""
        content = message.html_body or message.body or ""
        recipient = message.to[0] if message.to else "" 
        
        # Prepare meta_data with all email fields
        meta_data = message.meta_data or {}
        # Only include serializable fields
        email_fields = {
            "from_email": message.from_email,
            "from_name": message.from_name,
            "template_id": message.template_id,
            "html_body": message.html_body,
            "body": message.body,
            "cc": message.cc,
            "bcc": message.bcc,
            "reply_to": message.reply_to,
            "attachments": message.attachments,
            "domain": message.domain,
            "to": message.to
        }
        # Handle recipients specially - convert to dict format if present
        if message.recipients:
            email_fields["recipients"] = []
            for r in message.recipients:
                if isinstance(r, dict):
                    # Already in dict format from the request
                    email_fields["recipients"].append(r)
                else:
                    # Convert Recipient object to dict
                    email_fields["recipients"].append({
                        "to": [{"email": getattr(r, 'email', ''), "name": getattr(r, 'name', '')}],
                        "variables": {}
                    })
        meta_data.update(email_fields)
        
        notification_result = await self.create_notification(
            notification_type=NotificationType.EMAIL,
            recipient=recipient,
            content=content,
            subject=subject,
            service_id=service_id,
            provider_id=str(message.provider_id) if message.provider_id else str(provider_id) if provider_id else None,
            priority=notification_priority,
            meta_data=meta_data,
            db=db
        )
            
        # Look up the actual provider name for the response
        provider_name = self.default_provider_name or "unknown"
        if provider_id:
            provider_repo = ProviderRepository(db)
            provider_entity = await provider_repo.get_provider(provider_id)
            if provider_entity:
                provider_name = str(provider_entity.name)  # type: ignore
        
        # For API backwards compatibility, return a notification response with notification ID
        return NotificationResponse(
            success=True,
            status=NotificationStatus.QUEUED.value,  # type: ignore
            provider_name=provider_name,
            message_id=None,  # Will be assigned by the worker
            provider_response={
                "message": "Notification queued for processing",
                "notification_id": notification_result["id"]
            }
        )
    
    async def send_sms(
        self, 
        message: SMSMessage, 
        provider_id: Optional[uuid.UUID] = None,
        service_id: Optional[uuid.UUID] = None,
        priority: Optional[str] = None,
        db: Optional[AsyncSession] = None
    ) -> NotificationResponse:
        """Send an SMS message."""
        if not db:
            raise ValueError("Database session is required")
            
        # Process message to ensure proper structure    
        message = self._process_message(message)  # type: ignore
        
        # Store notification in database and queue for delivery
        notification_priority = NotificationPriority.NORMAL
        if priority == "instant":
            notification_priority = NotificationPriority.INSTANT
        elif priority == "high":
            notification_priority = NotificationPriority.HIGH
        elif priority == "low":
            notification_priority = NotificationPriority.LOW
        
        # Create the notification and queue it
        recipient = message.recipient if hasattr(message, 'recipient') else ""  # type: ignore
        
        notification_result = await self.create_notification(
            notification_type=NotificationType.SMS,
            recipient=recipient,
            content=message.content,
            subject=None,
            service_id=service_id,
            provider_id=str(provider_id) if provider_id else message.provider_id,
            priority=notification_priority,
            meta_data=message.meta_data or {},
            db=db
        )
            
        # Return notification response with notification ID
        return NotificationResponse(
            success=True,
            status=NotificationStatus.QUEUED.value,  # type: ignore
            provider_name=self.default_provider_name or "unknown",
            message_id=None,  # Will be assigned by the worker
            provider_response={
                "message": "Notification queued for processing",
                "notification_id": notification_result["id"]
            }
        )
    
    async def send_whatsapp(
        self, 
        message: WhatsAppMessage, 
        provider_id: Optional[uuid.UUID] = None,
        service_id: Optional[uuid.UUID] = None,
        priority: Optional[str] = None,
        db: Optional[AsyncSession] = None
    ) -> NotificationResponse:
        """Send a WhatsApp message."""
        if not db:
            raise ValueError("Database session is required")
            
        # Process message to ensure proper structure    
        message = self._process_message(message)  # type: ignore
        
        # Store notification in database and queue for delivery
        notification_priority = NotificationPriority.NORMAL
        if priority == "instant":
            notification_priority = NotificationPriority.INSTANT
        elif priority == "high":
            notification_priority = NotificationPriority.HIGH
        elif priority == "low":
            notification_priority = NotificationPriority.LOW
        
        # Create the notification and queue it
        recipient = message.recipient if hasattr(message, 'recipient') else ""  # type: ignore
        
        notification_result = await self.create_notification(
            notification_type=NotificationType.WHATSAPP,
            recipient=recipient,
            content=message.content,
            subject=None,
            service_id=service_id,
            provider_id=str(provider_id) if provider_id else message.provider_id,
            priority=notification_priority,
            meta_data=message.meta_data or {},
            db=db
        )
            
        # Return notification response with notification ID
        return NotificationResponse(
            success=True,
            status=NotificationStatus.QUEUED.value,  # type: ignore
            provider_name=self.default_provider_name or "unknown",
            message_id=None,  # Will be assigned by the worker
            provider_response={
                "message": "Notification queued for processing",
                "notification_id": notification_result["id"]
            }
        )

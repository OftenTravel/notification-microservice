from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict, Any

class BaseMessage(BaseModel):
    """Base class for all message types."""
    provider_id: Optional[str] = None
    meta_data: Dict[str, Any] = {}  # For template variables and other provider-specific data

class SMSMessage(BaseMessage):
    """Model for SMS messages."""
    recipient: str  # Phone number
    content: str
    sender_id: Optional[str] = None

class EmailMessage(BaseMessage):
    """Model for email messages."""
    to: List[str]  # Using str instead of EmailStr for simplicity in testing
    subject: str
    body: str
    from_email: Optional[str] = None
    cc: List[str] = []
    bcc: List[str] = []
    reply_to: Optional[str] = None
    html_body: Optional[str] = None
    attachments: List[Dict[str, Any]] = []

class WhatsAppMessage(BaseMessage):
    """Model for WhatsApp messages."""
    recipient: str  # Phone number with country code
    content: str
    media_url: Optional[str] = None
    template_id: Optional[str] = None
    template_params: Dict[str, str] = {}

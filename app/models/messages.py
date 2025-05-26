from pydantic import BaseModel, Field, EmailStr, field_validator
from typing import Optional, List, Dict, Any

class BaseMessage(BaseModel):
    """Base class for all message types."""
    provider_id: Optional[str] = Field(
        None, 
        description="UUID of the provider to use for sending this message"
    )
    meta_data: Dict[str, Any] = Field(
        {}, 
        description="Additional metadata for template variables and provider-specific options"
    )

class SMSMessage(BaseMessage):
    """Model for SMS messages."""
    recipient: str = Field(..., description="Phone number of the recipient")
    content: str = Field(..., description="SMS content to send") 
    sender_id: Optional[str] = Field(None, description="Sender ID to use if supported by the provider")

class Recipient(BaseModel):
    """Recipient data model with name and variables."""
    name: str = Field("", description="Recipient's display name")
    email: Optional[str] = Field(None, description="Recipient's email address")
    variables: Dict[str, Any] = Field({}, description="Template variables specific to this recipient")

class EmailMessage(BaseMessage):
    """
    Model for email messages. Supports two formats for recipients:
    
    1. Simple format using 'to' field - List of email addresses
    2. Advanced format using 'recipients' field - Rich data with names and per-recipient variables
    """
    to: Optional[List[str]] = Field(
        None, 
        description="Simple recipient format: List of email addresses",
        examples=[["user1@example.com", "user2@example.com"]]
    )
    recipients: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="""
        Advanced recipient format with names and per-recipient variables.
        This matches MSG91's native API format.
        Takes precedence over 'to' field when both are provided.
        """,
        examples=[[{
            "to": [{"email": "user1@example.com", "name": "John Doe"}],
            "variables": {"name": "John", "order_id": "12345"}
        }]]
    )
    subject: str = Field(..., description="Email subject line")
    body: str = Field("", description="Plain text email body")
    html_body: Optional[str] = Field(None, description="HTML version of the email body")
    from_email: Optional[str] = Field(None, description="Sender email address (defaults to provider's default)")
    cc: List[str] = Field([], description="Carbon copy recipients")
    bcc: List[str] = Field([], description="Blind carbon copy recipients")
    reply_to: Optional[List[Dict[str, str]]] = Field(
        None, 
        description="Reply-to addresses",
        examples=[[{"email": "support@example.com"}]]
    )
    attachments: List[Dict[str, Any]] = Field(
        [], 
        description="""
        File attachments. Two formats supported:
        1. Public URL: {"filePath": "https://example.com/file.pdf", "fileName": "document.pdf"}
        2. Base64: {"file": "data:application/pdf;base64,JVBERi0...", "fileName": "document.pdf"}
        """,
        examples=[[
            {"filePath": "https://example.com/files/document.pdf", "fileName": "Document.pdf"},
            {"file": "data:application/pdf;base64,JVBERi0xLjQKJcOkw7zDt...", "fileName": "Encoded.pdf"}
        ]]
    )
    template_id: Optional[str] = Field(None, description="MSG91 template ID to use")
    domain: Optional[str] = Field(None, description="Domain for DKIM signing")
    
    class Config:
        schema_extra = {
            "example": {
                "provider_id": "f907e4ac-8415-418d-8a40-b6ff789a25de",
                "to": ["user@example.com"],
                "subject": "Your order confirmation",
                "body": "Thank you for your order",
                "html_body": "<h1>Thank you for your order</h1>",
                "reply_to": [{"email": "support@example.com"}],
                "meta_data": {"order_id": "12345"}
            }
        }

class WhatsAppMessage(BaseMessage):
    """Model for WhatsApp messages."""
    recipient: str = Field(..., description="Phone number of the recipient with country code")
    content: str = Field(..., description="Message content to send")
    media_url: Optional[str] = Field(None, description="URL to media to include")
    template_id: Optional[str] = Field(None, description="Template ID if using WhatsApp templates")
    template_params: Dict[str, str] = Field({}, description="Parameters to populate WhatsApp template")

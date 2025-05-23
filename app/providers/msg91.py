import httpx
from typing import Dict, Any, Optional
import json

from app.providers.base import NotificationProvider
from app.core.config import settings


class MSG91Provider(NotificationProvider):
    """MSG91 SMS provider implementation."""
    
    BASE_URL = "https://api.msg91.com/api/v5"
    
    def __init__(self, api_key: Optional[str] = None, sender_id: Optional[str] = None):
        self.api_key = api_key or settings.MSG91_API_KEY
        self.sender_id = sender_id or settings.MSG91_SENDER_ID
        
        if not self.api_key:
            raise ValueError("MSG91 API key is required")
            
        if not self.sender_id:
            raise ValueError("MSG91 Sender ID is required")
    
    async def send(self, recipient: str, content: str, **kwargs) -> Dict[str, Any]:
        """Send SMS via MSG91"""
        template_id = kwargs.get("template_id")
        variables = kwargs.get("variables", {})
        
        # Clean phone number (remove + if present)
        if recipient.startswith('+'):
            recipient = recipient[1:]
            
        async with httpx.AsyncClient() as client:
            headers = {
                "authkey": self.api_key,
                "content-type": "application/json"
            }
            
            payload = {
                "sender": self.sender_id,
                "route": "4",  # Transactional route
                "country": "91",  # Country code
                "sms": [{
                    "message": content,
                    "to": [recipient]
                }]
            }
            
            # If using a template
            if template_id:
                endpoint = f"{self.BASE_URL}/flow/"
                payload = {
                    "flow_id": template_id,
                    "sender": self.sender_id,
                    "recipients": [{
                        "mobiles": recipient,
                        "VAR": variables
                    }]
                }
            else:
                endpoint = f"{self.BASE_URL}/sms/send"
                
            response = await client.post(
                endpoint, 
                headers=headers,
                json=payload
            )
            
            response_data = response.json()
            
            return {
                "provider": "msg91",
                "status": "sent" if response_data.get("type") == "success" else "failed",
                "external_id": response_data.get("request_id", ""),
                "response": response_data
            }
    
    async def check_status(self, external_id: str) -> Dict[str, Any]:
        """Check SMS delivery status via MSG91"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/sms/status",
                params={
                    "authkey": self.api_key,
                    "request_id": external_id
                }
            )
            
            response_data = response.json()
            
            # Map MSG91 status to our status
            status_mapping = {
                "delivered": "delivered",
                "sent": "sent",
                "failed": "failed",
                "pending": "pending"
            }
            
            status = "unknown"
            if response_data.get("status") in status_mapping:
                status = status_mapping[response_data.get("status")]
                
            return {
                "provider": "msg91",
                "status": status,
                "external_id": external_id,
                "response": response_data
            }

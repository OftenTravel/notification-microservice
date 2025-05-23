import asyncio
import uuid
import random
from typing import Dict, Any

from app.providers.base import NotificationProvider
from app.models.messages import SMSMessage, EmailMessage, WhatsAppMessage
from app.models.responses import NotificationResponse, NotificationStatus

class MockProvider(NotificationProvider):
    """
    A mock provider for testing that simulates sending notifications.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the mock provider with configuration.
        
        Args:
            config: A dictionary with configuration options:
                - success_rate: float between 0 and 1 (default 0.9)
                - delay_ms: Average delay in milliseconds (default 500)
        """
        super().__init__(config)
        self.success_rate = config.get('success_rate', 0.9)
        self.delay_ms = config.get('delay_ms', 500)
    
    async def _simulate_sending(self) -> bool:
        """
        Simulate the sending process with random delay and success rate.
        
        Returns:
            bool: True if the send was successful
        """
        # Simulate network delay
        delay = self.delay_ms * (0.5 + random.random())  # +/- 50%
        await asyncio.sleep(delay / 1000)  # Convert ms to seconds
        
        # Determine if the send is successful based on success rate
        return random.random() < self.success_rate
    
    async def _create_response(self, success: bool, message_type: str) -> NotificationResponse:
        """
        Create a standardized response.
        
        Args:
            success: Whether the operation was successful
            message_type: Type of message sent
            
        Returns:
            NotificationResponse: The standardized response
        """
        if success:
            return NotificationResponse(
                success=True,
                status=NotificationStatus.SENT,
                provider_name=self.provider_name,
                message_id=str(uuid.uuid4()),
                provider_response={"mock": True, "message_type": message_type}
            )
        else:
            return NotificationResponse(
                success=False,
                status=NotificationStatus.FAILED,
                provider_name=self.provider_name,
                error_message=f"Mock delivery of {message_type} failed",
                provider_response={"mock": True, "message_type": message_type, "error": "simulated_failure"}
            )
    
    async def send_sms(self, message: SMSMessage) -> NotificationResponse:
        """
        Simulate sending an SMS message.
        
        Args:
            message: The SMS message to send
            
        Returns:
            NotificationResponse: The result of the operation
        """
        success = await self._simulate_sending()
        return await self._create_response(success, "sms")
    
    async def send_email(self, message: EmailMessage) -> NotificationResponse:
        """
        Simulate sending an email message.
        
        Args:
            message: The email message to send
            
        Returns:
            NotificationResponse: The result of the operation
        """
        success = await self._simulate_sending()
        return await self._create_response(success, "email")
    
    async def send_whatsapp(self, message: WhatsAppMessage) -> NotificationResponse:
        """
        Simulate sending a WhatsApp message.
        
        Args:
            message: The WhatsApp message to send
            
        Returns:
            NotificationResponse: The result of the operation
        """
        success = await self._simulate_sending()
        return await self._create_response(success, "whatsapp")

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class NotificationProvider(ABC):
    """Base abstract class for notification providers."""

    @abstractmethod
    async def send(self, recipient: str, content: str, **kwargs) -> Dict[str, Any]:
        """
        Send notification to recipient
        
        Args:
            recipient: The recipient of the notification
            content: The notification content
            **kwargs: Additional provider-specific parameters
            
        Returns:
            Dict containing status and provider-specific response
        """
        pass

    @abstractmethod
    async def check_status(self, external_id: str) -> Dict[str, Any]:
        """
        Check the delivery status of a notification
        
        Args:
            external_id: Provider's reference ID for the notification
            
        Returns:
            Dict containing current status information
        """
        pass

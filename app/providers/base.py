from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

from app.models.messages import SMSMessage, EmailMessage, WhatsAppMessage
from app.models.responses import NotificationResponse


class NotificationProvider(ABC):
    """
    Abstract base class for all notification providers.
    Any concrete provider must implement these methods.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the provider with configuration.

        Args:
            config: Provider-specific configuration
        """
        self.config = config
        self.provider_name = self.__class__.__name__
        self.initialize_provider()

    def initialize_provider(self) -> None:
        """
        Initialize any connections or resources needed by the provider.
        Override this method if needed in concrete providers.
        """
        pass

    @abstractmethod
    async def send_sms(self, message: SMSMessage) -> NotificationResponse:
        """
        Send an SMS message.

        Args:
            message: The SMS message to send

        Returns:
            NotificationResponse: The result of the operation
        """
        pass

    @abstractmethod
    async def send_email(self, message: EmailMessage) -> NotificationResponse:
        """
        Send an email message.

        Args:
            message: The email message to send

        Returns:
            NotificationResponse: The result of the operation
        """
        pass

    @abstractmethod
    async def send_whatsapp(self, message: WhatsAppMessage) -> NotificationResponse:
        """
        Send a WhatsApp message.

        Args:
            message: The WhatsApp message to send

        Returns:
            NotificationResponse: The result of the operation
        """
        pass

    async def validate_message(self, message: Any) -> bool:
        """
        Validate a message before sending.

        Args:
            message: The message to validate

        Returns:
            bool: True if valid, False otherwise
        """
        return True

    async def close(self) -> None:
        """
        Close any connections or resources.
        Override this method if needed in concrete providers.
        """
        pass

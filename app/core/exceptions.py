class NotificationException(Exception):
    """Base exception for all notification related errors."""
    pass

class ProviderException(NotificationException):
    """Exception raised for errors in the provider."""
    def __init__(self, provider_name: str, message: str):
        self.provider_name = provider_name
        self.message = message
        super().__init__(f"Provider {provider_name}: {message}")

class ConfigurationException(NotificationException):
    """Exception raised for configuration errors."""
    pass

class ValidationException(NotificationException):
    """Exception raised for message validation errors."""
    pass

class ProviderNotFoundError(NotificationException):
    """Exception raised when a provider is not found."""
    def __init__(self, provider_id: str):
        self.provider_id = provider_id
        super().__init__(f"Provider '{provider_id}' not found")

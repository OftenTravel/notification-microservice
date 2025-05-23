import httpx
import logging
import asyncio
from typing import Dict, Any, Optional, List

from app.providers.base import NotificationProvider
from app.models.messages import SMSMessage, EmailMessage, WhatsAppMessage
from app.models.responses import NotificationResponse, NotificationStatus
from app.core.exceptions import ProviderException, ConfigurationException
from app.core.config import settings

# Configure logging
logger = logging.getLogger(__name__)

class MSG91Provider(NotificationProvider):
    """Implementation of MSG91 provider for sending notifications."""
    
    # Base API URL
    BASE_URL = "https://control.msg91.com/api/v5"
    
    # API endpoints
    SMS_API_URL = f"{BASE_URL}/flow/"
    EMAIL_API_URL = f"{BASE_URL}/email/send"
    WHATSAPP_API_URL = f"{BASE_URL}/whatsapp/flow"
    
    # Default template ID for MSG91
    DEFAULT_DOMAIN = "ikmqaf.mailer91.com"
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the MSG91 provider with configuration.
        
        Args:
            config: Dictionary with configuration options:
                - api_key: MSG91 API key (required)
                - sender_id: Sender ID for SMS messages
                - email_from: Default sender email address
                - email_from_name: Default sender name
                - email_domain: Domain for DKIM signing
                - max_retries: Maximum number of retries on failure (default: 3)
                - base_retry_delay: Base delay for retry backoff in seconds (default: 1.0)
        """
        super().__init__(config)
        self.max_retries = config.get('max_retries', 3)
        self.base_retry_delay = config.get('base_retry_delay', 1.0)
        
    def initialize_provider(self) -> None:
        """
        Initialize and validate the provider configuration.
        """
        # Check for required configuration
        if 'api_key' not in self.config:
            raise ConfigurationException("MSG91Provider requires 'api_key' in configuration")
            
        self.api_key = self.config.get('api_key') or settings.MSG91_API_KEY
        if not self.api_key:
            raise ConfigurationException("MSG91 API key not provided")
        
        # Print the API key for debugging
        print(f"DEBUG - USING MSG91 API KEY: '{self.api_key}'")
            
        self.sender_id = self.config.get('sender_id') or settings.MSG91_SENDER_ID
        if not self.sender_id:
            logger.warning("MSG91 sender ID not provided, using default")
            
        # Email-specific configurations
        self.email_domain = self.config.get('email_domain', self.DEFAULT_DOMAIN)
        self.email_from = self.config.get('email_from', f"no-reply@{self.email_domain}")
        self.email_from_name = self.config.get('email_from_name', 'Notification Service')
            
        # Initialize HTTP client with proper headers
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "authkey": self.api_key  # MSG91 uses "authkey" header
        }
        
        print(f"DEBUG - MSG91 HEADERS: {headers}")
        
        self.http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0),
            headers=headers,
            verify=False  # Temporarily disable SSL verification
        )
        
        logger.warning("SSL verification disabled for troubleshooting")
    
    async def send_sms(self, message: SMSMessage) -> NotificationResponse:
        """
        Send an SMS message via MSG91 API.
        
        Args:
            message: The SMS message to send
            
        Returns:
            NotificationResponse: The result of the operation
        """
        # Validate sender ID
        sender_id = message.sender_id or self.sender_id
        if not sender_id:
            raise ConfigurationException("Sender ID is required for sending SMS")
        
        # Prepare request payload
        payload = {
            "flow_id": self.config.get('sms_flow_id', ''),
            "sender": sender_id,
            "mobiles": message.recipient,
            "VAR1": message.content,  # Assuming template with VAR1 for content
        }
        
        if message.meta_data:
            # Add any additional template variables
            for key, value in message.meta_data.items():
                if key.startswith('VAR'):
                    payload[key] = value
        
        # Send request with retry logic
        try:
            response = await self._make_request_with_retry(
                url=self.SMS_API_URL,
                method="POST",
                json_data=payload
            )
            
            # Parse response
            success = response.get('status') == "success"
            response_data = {
                "provider_id": "msg91",
                "message_type": "sms",
                "raw_response": response
            }
            
            if success:
                message_id = response.get('data', {}).get('id')
                return NotificationResponse(
                    success=True,
                    status=NotificationStatus.SENT,
                    provider_name=self.provider_name,
                    message_id=message_id,
                    provider_response=response_data
                )
            else:
                error_msg = response.get('message') or "Unknown MSG91 error"
                return NotificationResponse(
                    success=False,
                    status=NotificationStatus.FAILED,
                    provider_name=self.provider_name,
                    error_message=error_msg,
                    provider_response=response_data
                )
                
        except Exception as e:
            logger.error(f"Error sending SMS via MSG91: {str(e)}")
            return NotificationResponse(
                success=False,
                status=NotificationStatus.FAILED,
                provider_name=self.provider_name,
                error_message=str(e),
                provider_response={"error": str(e)}
            )
    
    async def send_email(self, message: EmailMessage) -> NotificationResponse:
        """Send an email message via MSG91 API."""
        # Make sure provider is initialized
        if not hasattr(self, 'email_from_name'):
            self.initialize_provider()
        
        # Validate from email - use message from_email or default no-reply
        from_email = message.from_email or self.email_from
        
        # Format recipients exactly as in the curl example
        recipients = []
        for email in message.to:
            recipient = {
                "to": [
                    {
                        "email": email,
                        "name": email.split('@')[0]  # Use part before @ as name
                    }
                ]
            }
            
            # Add template variables if available
            if message.meta_data:
                recipient["variables"] = message.meta_data
            
            recipients.append(recipient)
        
        # Add CC and BCC if provided
        if message.cc and recipients:
            recipients[0]["cc"] = [{"email": email, "name": ""} for email in message.cc]
        if message.bcc and recipients:
            recipients[0]["bcc"] = [{"email": email, "name": ""} for email in message.bcc]
        
        # Basic payload structure
        payload = {
            "recipients": recipients,
            "from": {
                "email": from_email,
                "name": self.email_from_name
            },
            "domain": self.email_domain
        }
        
        # Get template_id from message or config
        template_id = message.meta_data.get('template_id') if message.meta_data else None
        template_id = template_id or self.config.get('email_template_id')
        
        if template_id:
            # Using template - add template_id
            payload["template_id"] = template_id
        else:
            # Using direct content - add properly formatted body fields
            # According to the error message, we need body.type and body.data
            html_content = message.html_body or message.body
            
            payload["body"] = {
                "type": "text/html",  # As requested in the prompt
                "data": html_content
            }
            
            # Add subject directly
            payload["subject"] = message.subject
        
        # Debug output
        print(f"DEBUG - EMAIL PAYLOAD: {payload}")
        
        # Send request with retry logic
        try:
            response = await self._make_request_with_retry(
                url=self.EMAIL_API_URL,
                method="POST",
                json_data=payload
            )
            
            # Parse response
            success = response.get('status') == "success"
            response_data = {
                "provider_id": "msg91",
                "message_type": "email",
                "raw_response": response
            }
            
            if success:
                message_id = response.get('data', {}).get('id')
                return NotificationResponse(
                    success=True,
                    status=NotificationStatus.SENT,
                    provider_name=self.provider_name,
                    message_id=message_id,
                    provider_response=response_data
                )
            else:
                error_msg = response.get('message') or "Unknown MSG91 error"
                return NotificationResponse(
                    success=False,
                    status=NotificationStatus.FAILED,
                    provider_name=self.provider_name,
                    error_message=error_msg,
                    provider_response=response_data
                )
                
        except Exception as e:
            logger.error(f"Error sending email via MSG91: {str(e)}")
            return NotificationResponse(
                success=False,
                status=NotificationStatus.FAILED,
                provider_name=self.provider_name,
                error_message=str(e),
                provider_response={"error": str(e)}
            )

    async def send_whatsapp(self, message: WhatsAppMessage) -> NotificationResponse:
        """
        Send a WhatsApp message via MSG91 API.
        
        Args:
            message: The WhatsApp message to send
            
        Returns:
            NotificationResponse: The result of the operation
        """
        # Check for required template
        template_id = message.template_id or self.config.get('whatsapp_template_id')
        if not template_id:
            raise ConfigurationException("Template ID is required for WhatsApp messages")
        
        # Prepare request payload
        payload = {
            "flow_id": template_id,
            "mobile": message.recipient,
            "media": {
                "url": message.media_url
            } if message.media_url else {},
            "VAR1": message.content  # Assuming template with VAR1 for content
        }
        
        # Add template parameters if available
        if message.template_params:
            for key, value in message.template_params.items():
                if key.startswith('VAR'):
                    payload[key] = value
                    
        # Add any additional metadata
        if message.meta_data:
            for key, value in message.meta_data.items():
                if key not in payload and key.startswith('VAR'):
                    payload[key] = value
        
        # Send request with retry logic
        try:
            response = await self._make_request_with_retry(
                url=self.WHATSAPP_API_URL,
                method="POST",
                json_data=payload
            )
            
            # Parse response
            success = response.get('status') == "success"
            response_data = {
                "provider_id": "msg91",
                "message_type": "whatsapp",
                "raw_response": response
            }
            
            if success:
                message_id = response.get('data', {}).get('id')
                return NotificationResponse(
                    success=True,
                    status=NotificationStatus.SENT,
                    provider_name=self.provider_name,
                    message_id=message_id,
                    provider_response=response_data
                )
            else:
                error_msg = response.get('message') or "Unknown MSG91 error"
                return NotificationResponse(
                    success=False,
                    status=NotificationStatus.FAILED,
                    provider_name=self.provider_name,
                    error_message=error_msg,
                    provider_response=response_data
                )
                
        except Exception as e:
            logger.error(f"Error sending WhatsApp message via MSG91: {str(e)}")
            return NotificationResponse(
                success=False,
                status=NotificationStatus.FAILED,
                provider_name=self.provider_name,
                error_message=str(e),
                provider_response={"error": str(e)}
            )
    
    async def create_email_template(self, name: str, slug: str, subject: str, body: str) -> Dict[str, Any]:
        """
        Create an email template in MSG91.
        
        Args:
            name: Template name
            slug: Unique template identifier
            subject: Email subject
            body: HTML body with variables like ##name##
            
        Returns:
            Dict[str, Any]: The API response
        """
        payload = {
            "name": name,
            "slug": slug,
            "subject": subject,
            "body": body
        }
        
        response = await self._make_request_with_retry(
            url=self.EMAIL_TEMPLATE_API_URL,
            method="POST",
            json_data=payload
        )
        
        return response
    
    async def get_email_templates(
        self, 
        page: int = 1, 
        per_page: int = 25, 
        status_id: int = 2,
        keyword: str = "",
        search_in: str = "name"
    ) -> Dict[str, Any]:
        """
        Get list of email templates.
        """
        # Ensure provider is initialized
        if not hasattr(self, 'http_client'):
            self.initialize_provider()
            
        params = {
            "with": "versions",
            "per_page": per_page,
            "page": page,
            "status_id": status_id,
            "keyword": keyword,
            "search_in": search_in
        }
        
        # Convert params to query string
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        
        response = await self._make_request_with_retry(
            url=f"{self.EMAIL_TEMPLATE_API_URL}?{query_string}",
            method="GET",
            json_data=None
        )
        
        return response
    
    async def get_template_version_details(self, version_id: str) -> Dict[str, Any]:
        """
        Get details of a specific template version.
        
        Args:
            version_id: Template version ID
            
        Returns:
            Dict[str, Any]: The API response with template details
        """
        response = await self._make_request_with_retry(
            url=f"{self.EMAIL_TEMPLATE_VERSION_API_URL}/{version_id}?with=template",
            method="GET",
            json_data=None
        )
        
        return response
    
    async def inline_email_css(self, html: str) -> str:
        """
        Use MSG91's CSS inliner service to inline CSS in HTML.
        
        Args:
            html: HTML content with CSS
            
        Returns:
            str: HTML with inlined CSS
        """
        payload = {
            "html": html
        }
        
        response = await self._make_request_with_retry(
            url=self.EMAIL_CSS_INLINE_API_URL,
            method="POST",
            json_data=payload
        )
        
        if response.get('status') == "success":
            return response.get('data', {}).get('html', html)
        else:
            # If inlining fails, return original HTML
            logger.warning(f"CSS inlining failed: {response.get('message')}")
            return html
    
    async def _make_request_with_retry(
        self,
        url: str,
        method: str,
        json_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Make HTTP request with exponential backoff retry strategy.
        """
        attempt = 0
        last_exception = None
        
        while attempt < self.max_retries:
            try:
                if attempt > 0:
                    # Calculate backoff delay with exponential increase
                    delay = self.base_retry_delay * (2 ** (attempt - 1))
                    await asyncio.sleep(delay)
                    logger.info(f"Retrying MSG91 request attempt {attempt+1}/{self.max_retries}")
                
                attempt += 1
                
                # Print exact request details for debugging
                print(f"DEBUG - REQUEST URL: {url}")
                print(f"DEBUG - REQUEST METHOD: {method}")
                print(f"DEBUG - REQUEST HEADERS: {dict(self.http_client.headers)}")
                print(f"DEBUG - REQUEST BODY: {json_data}")
                
                # Make the request
                if method.upper() == "POST":
                    response = await self.http_client.post(url, json=json_data)
                elif method.upper() == "GET":
                    response = await self.http_client.get(url)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")
                
                # Print response details for debugging
                print(f"DEBUG - RESPONSE STATUS: {response.status_code}")
                print(f"DEBUG - RESPONSE HEADERS: {dict(response.headers)}")
                print(f"DEBUG - RESPONSE BODY: {response.text[:500]}...")  # First 500 chars
                
                # Check for HTTP errors
                response.raise_for_status()
                
                # Parse and return the JSON response
                result = response.json()
                return result
                
            except httpx.HTTPStatusError as e:
                last_exception = e
                logger.warning(f"MSG91 API HTTP error: {e.response.status_code} - {e.response.text}")
                
                # Don't retry on client errors (except 429 Too Many Requests)
                if e.response.status_code < 500 and e.response.status_code != 429:
                    break
                    
            except (httpx.RequestError, httpx.TimeoutException) as e:
                last_exception = e
                logger.warning(f"MSG91 API request failed: {str(e)}")
                
            except Exception as e:
                last_exception = e
                logger.exception(f"Unexpected error calling MSG91 API: {str(e)}")
        
        # All retries failed
        error_msg = f"Failed to connect to MSG91 API after {attempt} attempts: {str(last_exception)}"
        logger.error(error_msg)
        raise ProviderException("MSG91", error_msg)
    
    def _sanitize_log_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Remove sensitive information before logging.
        """
        if not data:
            return {}
            
        # Create a copy to avoid modifying the original
        sanitized = data.copy()
        
        # Hide sensitive fields but show partial values for debugging
        if "authkey" in sanitized:
            key = sanitized["authkey"]
            if len(key) > 8:
                sanitized["authkey"] = key[:4] + "****" + key[-4:]
            else:
                sanitized["authkey"] = "********"
                
        return sanitized
        
    async def close(self) -> None:
        """
        Close any resources like HTTP connections.
        """
        await self.http_client.aclose()

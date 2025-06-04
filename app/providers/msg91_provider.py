import httpx
import structlog
import asyncio
from typing import Dict, Any, Optional, List

from app.providers.base import NotificationProvider
from app.models.messages import SMSMessage, EmailMessage, WhatsAppMessage
from app.models.responses import NotificationResponse, NotificationStatus
from app.core.exceptions import ProviderException, ConfigurationException
from app.core.config import settings

# Configure logging
logger = structlog.get_logger(__name__)

class MSG91Provider(NotificationProvider):
    """Implementation of MSG91 provider for sending notifications."""
    
    # Base API URL
    BASE_URL = "https://control.msg91.com/api/v5"
    
    # API endpoints
    SMS_API_URL = f"{BASE_URL}/flow/"
    EMAIL_API_URL = f"{BASE_URL}/email/send"
    WHATSAPP_API_URL = f"{BASE_URL}/whatsapp/flow"
    
    # Template API endpoints - Updated with correct paths from curl examples
    EMAIL_TEMPLATE_API_URL = f"{BASE_URL}/email/templates"  # Correct
    EMAIL_TEMPLATE_VERSION_API_URL = f"{BASE_URL}/email/template-versions"  # May need verification
    EMAIL_CSS_INLINE_API_URL = f"{BASE_URL}/email/services/inline-css"  # Fixed: Correct path from curl example
    EMAIL_VALIDATE_API_URL = f"{BASE_URL}/email/validate"  # Added: New endpoint for email validation
    
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
        # Initialize http_client to None BEFORE calling super().__init__
        self.http_client = None
        super().__init__(config)
        self.max_retries = config.get('max_retries', 3)
        self.base_retry_delay = config.get('base_retry_delay', 1.0)
        # Now initialize the provider
        self.initialize_provider()
        
    def initialize_provider(self) -> None:
        """
        Initialize and validate the provider configuration.
        """
        # Check for required configuration
        if not self.config:
            raise ConfigurationException("MSG91Provider requires configuration")
            
        # Get auth key from config (using 'authkey' as per DB model)
        self.api_key = self.config.get('authkey')
        if not self.api_key:
            raise ConfigurationException("MSG91 auth key not provided in config")
        
        # Print the API key for debugging
        print(f"DEBUG - USING MSG91 AUTH KEY: '{self.api_key}'")
            
        # Get sender ID
        self.sender_id = self.config.get('sender_id')
        if not self.sender_id:
            logger.warning("MSG91 sender ID not provided, using default")
            self.sender_id = "NOTIFY"
            
        # Email-specific configurations using exact keys from DB model
        self.email_domain = self.config.get('email_domain', self.DEFAULT_DOMAIN)
        self.email_from = self.config.get('from_default', f"no-reply@{self.email_domain}")
        self.email_from_name = self.config.get('from_default_name', 'Notification Service')
            
        # Initialize HTTP client with proper headers - ONLY if not already initialized
        if self.http_client is None:
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "authkey": self.api_key  # MSG91 uses "authkey" header
            }
            
            print(f"DEBUG - MSG91 HEADERS: {headers}")
            
            # Use current event loop instead of creating a new one
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                # If no loop exists in this thread, create a new one
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
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
        
        # Validate from email - use message from_email or config's from_default
        from_email = message.from_email or self.email_from
        from_name = message.from_name or self.email_from_name
        
        # Format recipients - check if native format is provided
        if message.recipients:
            # Use native MSG91 format if provided - ensure variables are preserved
            recipients = []
            for recipient in message.recipients:
                if isinstance(recipient, dict):
                    # Already in dict format - use as is
                    recipients.append(recipient)
                else:
                    # Convert to dict format and preserve variables
                    recipient_dict = {
                        "to": recipient.get("to", []) if isinstance(recipient, dict) else [],
                        "variables": recipient.get("variables", {}) if isinstance(recipient, dict) else {}
                    }
                    recipients.append(recipient_dict)
        else:
            # Format recipients from simple 'to' field
            recipients = []
            if message.to:
                for email in message.to:
                    recipient = {
                        "to": [
                            {
                                "email": email,
                                "name": email.split('@')[0]  # Use part before @ as name
                            }
                        ]
                    }
                    
                    # Add template variables if available in meta_data
                    if message.meta_data:
                        recipient["variables"] = message.meta_data  # type: ignore
                    
                    recipients.append(recipient)
        
        # Add CC and BCC if provided (add to first recipient for now)
        if message.cc and recipients:
            recipients[0]["cc"] = [{"email": email, "name": email.split('@')[0]} for email in message.cc]  # type: ignore
        if message.bcc and recipients:
            recipients[0]["bcc"] = [{"email": email, "name": email.split('@')[0]} for email in message.bcc]  # type: ignore
        
        # Basic payload structure following MSG91 API specification
        payload = {
            "recipients": recipients,
            "from": {
                "name": from_name,
                "email": from_email
            },
            "domain": message.domain or self.email_domain  # Use message domain or config domain
        }
        
        # Add reply_to if provided
        if message.reply_to:
            payload["reply_to"] = [{"email": email} for email in message.reply_to]
        
        # Add attachments if provided
        if message.attachments:
            payload["attachments"] = message.attachments
        
        # Get template_id from message, meta_data, or config
        template_id = message.template_id
        if not template_id and message.meta_data:
            template_id = message.meta_data.get('template_id')
        if not template_id:
            template_id = self.config.get('email_template_id')
        
        if template_id:
            # Using template - add template_id as string
            payload["template_id"] = str(template_id)
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
        # Use the correct URL format based on the documentation
        url = f"{self.EMAIL_TEMPLATE_VERSION_API_URL}/{version_id}?with=template"
        
        response = await self._make_request_with_retry(
            url=url,
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
        # Fixed payload format to match curl example
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
            
    async def validate_email(self, email: str) -> Dict[str, Any]:
        """
        Validate an email address using MSG91's validation service.
        
        Args:
            email: Email address to validate
            
        Returns:
            Dict[str, Any]: Validation response
        """
        payload = {
            "email": email
        }
        
        response = await self._make_request_with_retry(
            url=self.EMAIL_VALIDATE_API_URL,
            method="POST",
            json_data=payload
        )
        
        return response
    
    async def _make_request_with_retry(
        self,
        url: str,
        method: str,
        json_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Make HTTP request with exponential backoff retry strategy.
        """
        # Make sure we have a client
        if self.http_client is None:
            self.initialize_provider()
            
        # Ensure http_client is not None before using it
        assert self.http_client is not None, "HTTP client not initialized"
            
        # Ensure we're using the current event loop
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            # No running event loop, create a new one for this request
            current_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(current_loop)
            
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
                error_text = e.response.text if hasattr(e.response, 'text') else str(e)
                logger.warning(f"MSG91 API HTTP error: {e.response.status_code} - {error_text}")
                
                # For debugging: print the full error response
                print(f"DEBUG - ERROR RESPONSE STATUS: {e.response.status_code}")
                print(f"DEBUG - ERROR RESPONSE BODY: {error_text}")
                
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
    
    async def close(self) -> None:
        """
        Close any resources like HTTP connections.
        """
        if self.http_client:
            try:
                await self.http_client.aclose()
            except Exception as e:
                logger.warning(f"Error closing HTTP client: {str(e)}")
            finally:
                self.http_client = None
                
    # Ensure resources are properly released when the object is garbage collected
    def __del__(self):
        """Ensure HTTP client is closed when the object is garbage collected."""
        if hasattr(self, 'http_client') and self.http_client:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self.close())
                else:
                    loop.run_until_complete(self.close())
            except Exception:
                # Can't do much in a destructor
                pass

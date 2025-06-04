import asyncio
import os
import sys

# Add the parent directory to sys.path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app.models.messages import SMSMessage, EmailMessage, WhatsAppMessage
from app.services.notification_service import NotificationService

async def test_mock_provider():
    print("Testing MockProvider...")
    
    # Create messages with required and optional parameters
    sms = SMSMessage(
        recipient="+1234567890", 
        content="Test SMS message",
        provider_id=None,
        meta_data={},
        sender_id=None
    )
    
    email = EmailMessage(
        to=["test@example.com"],
        subject="Test Email", 
        body="This is a test email",
        provider_id=None,
        meta_data={},
        recipients=None,
        html_body=None,
        from_email=None,
        from_name=None,
        cc=[],
        bcc=[],
        reply_to=None,
        attachments=[],
        template_id=None,
        domain=None
    )
    
    whatsapp = WhatsAppMessage(
        recipient="+1234567890", 
        content="Test WhatsApp message",
        provider_id=None,
        meta_data={},
        media_url=None,
        template_id=None,
        template_params={}
    )
    
    # Create service with mock provider - FIXED: using proper parameter name
    service = NotificationService(default_provider_name="mock")  # NOT default_provider_id
    
    # Send messages
    print("\nSending SMS...")
    # Note: In actual testing with DB, you'd need to provide a database session
    # We would normally mock this, but this is a simplified example
    sms_response = await service.send_sms(sms)
    print(f"SMS Response: {sms_response}")
    
    print("\nSending Email...")
    email_response = await service.send_email(email)
    print(f"Email Response: {email_response}")
    
    print("\nSending WhatsApp...")
    whatsapp_response = await service.send_whatsapp(whatsapp)
    print(f"WhatsApp Response: {whatsapp_response}")
    
    print("\nRunning 5 SMS tests to show success/failure rates...")
    for i in range(5):
        response = await service.send_sms(sms)
        status = "SUCCESS" if response.success else "FAILED"
        print(f"  Test {i+1}: {status} - Message ID: {response.message_id}")

if __name__ == "__main__":
    asyncio.run(test_mock_provider())

import asyncio
import os
import sys

# Add the parent directory to sys.path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app.models.messages import SMSMessage, EmailMessage, WhatsAppMessage
from app.providers.registry import ProviderRegistry
from app.services.notification_service import NotificationService

async def test_mock_provider():
    print("Testing MockProvider...")
    
    # Create messages
    sms = SMSMessage(recipient="+1234567890", content="Test SMS message")
    email = EmailMessage(
        to=["test@example.com"],
        subject="Test Email",
        body="This is a test email"
    )
    whatsapp = WhatsAppMessage(recipient="+1234567890", content="Test WhatsApp message")
    
    # Create service with mock provider
    service = NotificationService(default_provider_id="mock")
    
    # Send messages
    print("\nSending SMS...")
    sms_response = await service.send_sms(sms)
    print(f"SMS Response: {sms_response.dict()}")
    
    print("\nSending Email...")
    email_response = await service.send_email(email)
    print(f"Email Response: {email_response.dict()}")
    
    print("\nSending WhatsApp...")
    whatsapp_response = await service.send_whatsapp(whatsapp)
    print(f"WhatsApp Response: {whatsapp_response.dict()}")
    
    print("\nRunning 5 SMS tests to show success/failure rates...")
    for i in range(5):
        response = await service.send_sms(sms)
        status = "SUCCESS" if response.success else "FAILED"
        print(f"  Test {i+1}: {status} - Message ID: {response.message_id}")

if __name__ == "__main__":
    asyncio.run(test_mock_provider())

#!/usr/bin/env python3
"""
Quick script to send a test email through MSG91
"""

import httpx
import asyncio
import json
from datetime import datetime
import uuid


async def send_test_email():
    """Send a test email through the API"""
    
    base_url = "http://localhost:8000/api/v1"
    
    # Authentication headers
    headers = {
        "X-Service-Id": "6dddbf0e-d6ab-4539-a0a0-9f5c26f81c2b",
        "X-API-Key": "6dddbf0ed6ab4539a0a09f5c26f81c2b-ad61a34f6b1a4e01bf3ee5fc4bf0de07",
        "Content-Type": "application/json"
    }
    
    # Email payload with unique subject
    unique_id = str(uuid.uuid4())[:8]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    payload = {
        "provider_id": "d0c1aaea-9abd-4fec-80e8-cb19ccd2d816",
        "meta_data": {},
        "to": ["sarvesh@mcp.travel"],
        "recipients": [
            {
                "to": [
                    {
                        "email": "sarvesh@mcp.travel",
                        "name": "Sarvesh"
                    }
                ],
                "variables": {
                    "VAR1": "Travel Often",
                    "VAR2": "Sarvesh"
                }
            }
        ],
        "subject": f"Welcomojin - {timestamp} - {unique_id}",  # Made unique to avoid duplication
        "body": "",
        "html_body": "string",
        "from_email": "contact@84nhii.mailer91.com",
        "from_name": "Often",
        "cc": [],
        "bcc": [],
        "template_id": "often_onboarding",
        "domain": "84nhii.mailer91.com"
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        print("\n" + "="*80)
        print(f"📧 SENDING TEST EMAIL - {timestamp}")
        print("="*80)
        print(f"Subject: {payload['subject']}")
        print(f"To: {payload['to']}")
        print(f"Template: {payload['template_id']}")
        print("-"*80)
        
        try:
            response = await client.post(
                f"{base_url}/notifications/email",
                json=payload,
                headers=headers
            )
            
            print(f"\nResponse Status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print("\n✅ EMAIL SENT SUCCESSFULLY")
                print(json.dumps(result, indent=2))
                
                # Extract notification ID
                notification_id = result.get('provider_response', {}).get('notification_id')
                if notification_id:
                    print(f"\n📧 NOTIFICATION ID: {notification_id}")
                    print("\n🔔 WEBHOOK URL CONFIGURED:")
                    print("https://d5df-2401-4900-a018-36a9-5086-c65e-6d11-4c52.ngrok-free.app/api/v1/msg91/webhook")
                    print("\n👀 CHECK YOUR API LOGS FOR WEBHOOK EVENTS!")
                    print("="*80)
                else:
                    print("\n⚠️  No notification ID in response")
                    
            else:
                print(f"\n❌ FAILED TO SEND EMAIL")
                print(f"Response: {response.text}")
                
        except Exception as e:
            print(f"\n❌ ERROR: {e}")


if __name__ == "__main__":
    print("\n🚀 MSG91 EMAIL TEST")
    print("="*80)
    asyncio.run(send_test_email())
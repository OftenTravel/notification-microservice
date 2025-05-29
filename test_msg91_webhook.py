#!/usr/bin/env python3
"""
Test script for MSG91 webhook integration.
This simulates MSG91 sending webhook notifications to our endpoint.
"""

import httpx
import json
import asyncio
import hmac
import hashlib
from datetime import datetime
import uuid


def generate_webhook_signature(payload: str, secret: str) -> str:
    """Generate HMAC SHA256 signature for webhook payload"""
    return hmac.new(
        secret.encode('utf-8'),
        payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()


async def test_msg91_webhook():
    """Test MSG91 webhook endpoint with sample payloads"""
    
    # Base URL for the API
    base_url = "http://localhost:8000/api/v1"
    webhook_url = f"{base_url}/msg91/webhook"
    
    # Webhook secret (set this in your .env file as MSG91_WEBHOOK_SECRET)
    webhook_secret = "your-webhook-secret-here"
    
    # Test payloads for different events
    test_payloads = [
        {
            "name": "Queued Event",
            "payload": {
                "data": {
                    "user_id": 9,
                    "domain_id": 70,
                    "recipient_id": 2907018,
                    "outbound_email_id": 52928425,
                    "event_id": 1,
                    "mail_type_id": 1,
                    "template_id": "after_autosave_stripo_mailer",
                    "status_code": None,
                    "enhanced_status_code": None,
                    "opened": 0,
                    "clicked": 0,
                    "reason": None,
                    "is_smtp": 0,
                    "meta": {
                        "code": None,
                        "state": None,
                        "reason": None,
                        "enhanced": None
                    },
                    "created_at": "2023-11-07 09:14:59",
                    "updated_at": "2023-11-07 09:14:59",
                    "deleted_at": None,
                    "outbound_email": {
                        "id": 52928425,
                        "user_id": 9,
                        "domain_id": 70,
                        "unique_id": "9a8e0a5d-981c-479d-a0ce-4309575c8992",
                        "template_id": "after_autosave_stripo_mailer",
                        "template_version_id": 9396,
                        "mail_type_id": 1,
                        "bulk_outbound_email_id": 353687,
                        "is_smtp": 0,
                        "to": [
                            {
                                "email": "person@msg91.com"
                            }
                        ],
                        "cc": [],
                        "bcc": [],
                        "from": {
                            "name": "Mailer",
                            "email": "mailer@example.com"
                        },
                        "subject": "Hey, This is to test after autosave mailer team some-test",
                        "variables": {
                            "otp": "696969",
                            "VAR1": "some-test",
                            "company_name": "Walkover"
                        },
                        "reply_to": None,
                        "in_reply_to": None,
                        "message_id": "<1699348501-9a8e0a5d-981c-479d-a0ce-4309575c8992-0@example.com>",
                        "campaign_id": None,
                        "pluginsource": None,
                        "references": None,
                        "attachments": []
                    },
                    "recipient": {
                        "id": 2907018,
                        "email": "person@msg91.com",
                        "meta": {
                            "code": 250,
                            "state": "EOD",
                            "reason": [
                                "OK ky4-20020a170902f98400b001c62e2ce6a7si2826545plb.445 - gsmtp"
                            ],
                            "enhanced": [
                                2,
                                0,
                                0
                            ]
                        },
                        "created_at": "2022-09-21T11:44:42.000000Z",
                        "updated_at": "2023-11-01T12:18:11.000000Z",
                        "deleted_at": None
                    },
                    "event": {
                        "id": 1,
                        "title": "Queued"
                    }
                }
            }
        },
        {
            "name": "Delivered Event",
            "payload": {
                "data": {
                    "outbound_email": {
                        "unique_id": "9a8e0a5d-981c-479d-a0ce-4309575c8992",
                        "message_id": "<1699348501-9a8e0a5d-981c-479d-a0ce-4309575c8992-0@example.com>"
                    },
                    "recipient": {
                        "email": "person@msg91.com",
                        "meta": {
                            "code": 250,
                            "state": "DELIVERED"
                        }
                    },
                    "event": {
                        "id": 2,
                        "title": "Delivered"
                    }
                }
            }
        },
        {
            "name": "Failed Event",
            "payload": {
                "data": {
                    "outbound_email": {
                        "unique_id": "9a8e0a5d-981c-479d-a0ce-4309575c8992",
                        "message_id": "<1699348501-9a8e0a5d-981c-479d-a0ce-4309575c8992-0@example.com>"
                    },
                    "recipient": {
                        "email": "person@msg91.com",
                        "meta": {
                            "code": 550,
                            "state": "FAILED",
                            "reason": ["5.1.1 The email account that you tried to reach does not exist"]
                        }
                    },
                    "event": {
                        "id": 5,
                        "title": "Failed"
                    }
                }
            }
        },
        {
            "name": "Opened Event",
            "payload": {
                "data": {
                    "outbound_email": {
                        "unique_id": "9a8e0a5d-981c-479d-a0ce-4309575c8992",
                        "message_id": "<1699348501-9a8e0a5d-981c-479d-a0ce-4309575c8992-0@example.com>"
                    },
                    "recipient": {
                        "email": "person@msg91.com"
                    },
                    "event": {
                        "id": 6,
                        "title": "Opened"
                    },
                    "opened": 1
                }
            }
        }
    ]
    
    async with httpx.AsyncClient() as client:
        # First, test the webhook test endpoint
        print("Testing MSG91 webhook test endpoint...")
        try:
            response = await client.get(f"{webhook_url}/test")
            print(f"Test endpoint response: {response.status_code}")
            print(f"Response: {response.json()}\n")
        except Exception as e:
            print(f"Error testing webhook endpoint: {e}\n")
        
        # Test each webhook payload
        for test_case in test_payloads:
            print(f"Testing: {test_case['name']}")
            print("-" * 50)
            
            # Convert payload to JSON string
            payload_str = json.dumps(test_case['payload'])
            
            # Generate signature if secret is set
            headers = {
                "Content-Type": "application/json"
            }
            
            if webhook_secret != "your-webhook-secret-here":
                signature = generate_webhook_signature(payload_str, webhook_secret)
                headers["X-MSG91-Signature"] = signature
            
            try:
                # Send webhook request
                response = await client.post(
                    webhook_url,
                    content=payload_str,
                    headers=headers
                )
                
                print(f"Status Code: {response.status_code}")
                print(f"Response: {response.json()}")
                
            except Exception as e:
                print(f"Error: {e}")
            
            print("\n")
            
            # Wait a bit between requests
            await asyncio.sleep(1)


async def test_notification_flow():
    """Test the complete notification flow: send email and check status"""
    base_url = "http://localhost:8000/api/v1"
    
    # Your service API key (get this from the database or create_service.py output)
    api_key = "your-service-api-key-here"
    
    headers = {
        "X-API-Key": api_key,
        "Content-Type": "application/json"
    }
    
    # Send a test email
    email_payload = {
        "to": ["test@example.com"],
        "subject": "MSG91 Webhook Test",
        "body": "This is a test email to verify MSG91 webhook integration",
        "html_body": "<h1>Test Email</h1><p>This is a test email to verify MSG91 webhook integration</p>",
        "provider_id": "msg91"  # Make sure you have MSG91 provider configured
    }
    
    async with httpx.AsyncClient() as client:
        print("Sending test email...")
        try:
            response = await client.post(
                f"{base_url}/notifications/email",
                json=email_payload,
                headers=headers
            )
            
            if response.status_code == 200:
                result = response.json()
                notification_id = result.get('provider_response', {}).get('notification_id')
                print(f"Email sent successfully!")
                print(f"Notification ID: {notification_id}")
                
                if notification_id:
                    # Check notification status
                    print("\nChecking notification status...")
                    await asyncio.sleep(2)  # Wait a bit
                    
                    status_response = await client.get(
                        f"{base_url}/notifications/{notification_id}",
                        headers=headers
                    )
                    
                    if status_response.status_code == 200:
                        status_data = status_response.json()
                        print(f"Notification Status: {json.dumps(status_data, indent=2)}")
                    else:
                        print(f"Failed to get status: {status_response.status_code}")
            else:
                print(f"Failed to send email: {response.status_code}")
                print(f"Error: {response.text}")
                
        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    print("MSG91 Webhook Integration Test")
    print("=" * 60)
    print()
    
    # Run webhook tests
    asyncio.run(test_msg91_webhook())
    
    print("\n" + "=" * 60)
    print("Testing Complete Notification Flow")
    print("=" * 60 + "\n")
    
    # Uncomment to test the complete flow
    # asyncio.run(test_notification_flow())
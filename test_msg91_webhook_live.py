#!/usr/bin/env python3
"""
Test MSG91 webhook integration with actual API calls
"""

import httpx
import asyncio
import json
from datetime import datetime
import uuid

async def send_test_email(subject_suffix="", use_ngrok=False):
    """Send a test email through the API"""
    
    # Use ngrok URL if specified, otherwise localhost
    if use_ngrok:
        base_url = "https://d5df-2401-4900-a018-36a9-5086-c65e-6d11-4c52.ngrok-free.app/api/v1"
    else:
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
        "provider_id": "7081cd11-eb45-4279-9f99-9e44190e41d6",
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
        "subject": f"Welcomojin - Test {timestamp} - {unique_id} {subject_suffix}",
        "body": "",
        "html_body": "<h1>Welcome to Often Travel</h1><p>This is a test email for webhook integration.</p>",
        "from_email": "contact@84nhii.mailer91.com",
        "from_name": "Often",
        "cc": [],
        "bcc": [],
        "template_id": "often_onbtoarding",
        "domain": "84nhii.mailer91.com"
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        print("\n" + "="*80)
        print(f"SENDING TEST EMAIL - {timestamp}")
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
            
            print(f"Response Status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print("\n✅ EMAIL SENT SUCCESSFULLY")
                print(json.dumps(result, indent=2))
                
                # Extract notification ID
                notification_id = result.get('provider_response', {}).get('notification_id')
                if notification_id:
                    print(f"\n📧 NOTIFICATION ID: {notification_id}")
                    return notification_id
                else:
                    print("\n⚠️  No notification ID in response")
                    
            else:
                print(f"\n❌ FAILED TO SEND EMAIL")
                print(f"Response: {response.text}")
                
        except Exception as e:
            print(f"\n❌ ERROR: {e}")
            
    return None


async def check_notification_status(notification_id, use_ngrok=False):
    """Check the status of a notification"""
    
    # Use ngrok URL if specified
    if use_ngrok:
        base_url = "https://d5df-2401-4900-a018-36a9-5086-c65e-6d11-4c52.ngrok-free.app/api/v1"
    else:
        base_url = "http://localhost:8000/api/v1"
    
    headers = {
        "X-Service-Id": "6dddbf0e-d6ab-4539-a0a0-9f5c26f81c2b",
        "X-API-Key": "6dddbf0ed6ab4539a0a09f5c26f81c2b-ad61a34f6b1a4e01bf3ee5fc4bf0de07"
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{base_url}/notifications/{notification_id}",
                headers=headers
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Failed to get notification status: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"Error checking status: {e}")
            return None


async def monitor_notification(notification_id, duration=60, use_ngrok=False):
    """Monitor a notification for status changes"""
    
    print(f"\n🔍 MONITORING NOTIFICATION: {notification_id}")
    print("="*80)
    
    start_time = asyncio.get_event_loop().time()
    last_status = None
    
    while (asyncio.get_event_loop().time() - start_time) < duration:
        status_data = await check_notification_status(notification_id, use_ngrok)
        
        if status_data:
            notification = status_data.get('notification', {})
            current_status = notification.get('status')
            
            if current_status != last_status:
                print(f"\n⏰ {datetime.now().strftime('%H:%M:%S')} - STATUS CHANGED")
                print("-"*80)
                print(f"Status: {current_status}")
                print(f"External ID: {notification.get('external_id')}")
                print(f"Sent At: {notification.get('sent_at')}")
                print(f"Delivered At: {notification.get('delivered_at')}")
                
                # Check meta_data for webhook events
                meta_data = notification.get('meta_data', {})
                webhook_events = meta_data.get('webhook_events', [])
                if webhook_events:
                    print(f"\n📨 WEBHOOK EVENTS RECEIVED: {len(webhook_events)}")
                    for i, event in enumerate(webhook_events):
                        print(f"\n  Event {i+1}:")
                        print(f"    - Type: {event.get('event')}")
                        print(f"    - Time: {event.get('timestamp')}")
                        print(f"    - Data: {json.dumps(event.get('data', {}), indent=6)}")
                
                last_status = current_status
                
                # If delivered or failed, we can stop monitoring
                if current_status in ['delivered', 'failed', 'seen']:
                    print(f"\n✅ FINAL STATUS REACHED: {current_status}")
                    break
        
        # Wait before checking again
        await asyncio.sleep(5)
    
    print("\n" + "="*80)
    print("MONITORING COMPLETE")
    print("="*80)


async def main():
    """Main test function"""
    
    print("\n" + "="*80)
    print("MSG91 WEBHOOK INTEGRATION TEST")
    print("="*80)
    print("\n📌 WEBHOOK ENDPOINT CONFIGURATION FOR MSG91:")
    print("-"*80)
    print("URL: https://d5df-2401-4900-a018-36a9-5086-c65e-6d11-4c52.ngrok-free.app/api/v1/msg91/webhook")
    print("Method: POST")
    print("Content-Type: application/json")
    print("\n✅ CORS is configured to allow all origins")
    print("✅ No authentication headers required for webhook")
    print("="*80)
    
    # Use localhost for sending (assuming API is running locally)
    # but ngrok URL will be used by MSG91 for webhooks
    notification_id = await send_test_email(use_ngrok=False)
    
    if notification_id:
        # Monitor for webhook updates (using localhost)
        await monitor_notification(notification_id, duration=120, use_ngrok=False)  # Monitor for 2 minutes
    
    print("\n🏁 TEST COMPLETE")


if __name__ == "__main__":
    asyncio.run(main())
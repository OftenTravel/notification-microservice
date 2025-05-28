#!/usr/bin/env python
"""
Interactive script to create a new service with webhooks.
Usage: python tools/create_service.py
"""

import asyncio
import sys
import os
from datetime import datetime, timezone
from typing import List, Optional

# Add the app directory to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from app.models.service_user import ServiceUser
from app.models.webhook import Webhook
from app.core.config import settings
import uuid


def print_header():
    """Print a nice header for the script."""
    print("\n" + "="*60)
    print("🚀 Notification Service - Interactive Service Creator")
    print("="*60 + "\n")


def get_input(prompt: str, required: bool = True, default: Optional[str] = None) -> str:
    """Get user input with optional default value."""
    if default:
        prompt = f"{prompt} [{default}]"
    
    while True:
        value = input(f"{prompt}: ").strip()
        
        if not value and default:
            return default
        
        if not value and required:
            print("❌ This field is required. Please try again.")
            continue
            
        return value


def get_yes_no(prompt: str, default: bool = True) -> bool:
    """Get yes/no input from user."""
    default_str = "Y/n" if default else "y/N"
    while True:
        value = input(f"{prompt} ({default_str}): ").strip().lower()
        
        if not value:
            return default
            
        if value in ['y', 'yes', '1', 'true']:
            return True
        elif value in ['n', 'no', '0', 'false']:
            return False
        else:
            print("❌ Please enter 'y' for yes or 'n' for no.")


def get_webhooks() -> List[dict]:
    """Interactively get webhook configurations from user."""
    webhooks = []
    
    print("\n📌 Webhook Configuration")
    print("-" * 40)
    print("Webhooks are used to notify your service about notification status updates.")
    print("You can add multiple webhook URLs.\n")
    
    add_webhook = get_yes_no("Do you want to add webhooks?", default=True)
    
    if not add_webhook:
        return webhooks
    
    while True:
        print(f"\n🔗 Webhook #{len(webhooks) + 1}")
        
        url = get_input("Webhook URL (e.g., https://api.example.com/webhook)")
        
        # Validate URL format
        if not url.startswith(('http://', 'https://')):
            print("⚠️  URL should start with http:// or https://")
            continue
            
        description = get_input(
            "Description", 
            required=False,
            default=f"Webhook endpoint #{len(webhooks) + 1}"
        )
        
        is_active = get_yes_no("Enable this webhook?", default=True)
        
        # Advanced webhook options
        show_advanced = get_yes_no("\nConfigure advanced options?", default=False)
        
        headers = {}
        events = ["notification.sent", "notification.delivered", "notification.failed", "notification.bounced"]
        max_retries = 3
        timeout_seconds = 30
        
        if show_advanced:
            # Custom headers
            add_headers = get_yes_no("Add custom headers?", default=False)
            if add_headers:
                print("\nEnter custom headers (format: key=value, empty line to finish):")
                while True:
                    header = input("> ").strip()
                    if not header:
                        break
                    if '=' in header:
                        key, value = header.split('=', 1)
                        headers[key.strip()] = value.strip()
                    else:
                        print("❌ Invalid format. Use: key=value")
            
            # Event filtering
            print(f"\nAvailable events: {', '.join(events)}")
            custom_events = get_input(
                "Events to subscribe (comma-separated, or 'all' for all events)",
                required=False,
                default="all"
            )
            if custom_events.lower() != "all":
                events = [e.strip() for e in custom_events.split(',') if e.strip()]
            
            # Retry configuration
            max_retries = int(get_input("Max retry attempts", default="3"))
            timeout_seconds = int(get_input("Timeout in seconds", default="30"))
        
        webhook = {
            "url": url,
            "description": description,
            "is_active": is_active,
            "headers": headers,
            "events": events,
            "max_retries": max_retries,
            "timeout_seconds": timeout_seconds
        }
        
        webhooks.append(webhook)
        
        # Ask if user wants to add more
        add_more = get_yes_no("\nAdd another webhook?", default=False)
        if not add_more:
            break
    
    return webhooks


async def create_service_interactive():
    """Create a new service with interactive prompts."""
    
    print_header()
    
    # Get service details
    print("📝 Service Details")
    print("-" * 40)
    
    name = get_input("Service name (unique identifier, no spaces)")
    # Replace spaces with underscores
    name = name.replace(' ', '_').lower()
    
    description = get_input("Service description", required=False)
    
    # Note: Rate limiting would be configured at the application level,
    # not stored in the service_users table
    
    # Get webhook configurations
    webhooks = get_webhooks()
    
    # Summary
    print("\n" + "="*60)
    print("📋 Service Configuration Summary")
    print("="*60)
    print(f"\n🏷️  Name: {name}")
    print(f"📝 Description: {description or 'N/A'}")
    
    
    if webhooks:
        print(f"\n📌 Webhooks ({len(webhooks)}):")
        for i, webhook in enumerate(webhooks):
            print(f"   {i+1}. {webhook['url']} {'✅' if webhook['is_active'] else '❌'}")
    
    print("\n" + "="*60)
    
    # Confirm creation
    confirm = get_yes_no("\nCreate this service?", default=True)
    
    if not confirm:
        print("\n❌ Service creation cancelled.")
        return
    
    # Create the service
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        try:
            # Check if service already exists
            query = select(ServiceUser).where(ServiceUser.name == name)
            result = await session.execute(query)
            existing_service = result.scalar_one_or_none()
            
            if existing_service:
                print(f"\n❌ Service '{name}' already exists!")
                return
            
            # Create new service
            service, api_key = await ServiceUser.create_service(
                db=session,
                name=name,
                description=description
            )
            
            print(f"\n✅ Service created successfully!")
            
            # Create webhooks
            for webhook_data in webhooks:
                webhook = Webhook(
                    id=uuid.uuid4(),
                    service_id=service.id,
                    url=webhook_data["url"],
                    description=webhook_data["description"],
                    is_active=webhook_data["is_active"],
                    headers=webhook_data["headers"],
                    events=webhook_data["events"],
                    max_retries=webhook_data["max_retries"],
                    timeout_seconds=webhook_data["timeout_seconds"],
                    created_at=datetime.now(datetime.timezone.utc),
                    updated_at=datetime.now(datetime.timezone.utc)
                )
                session.add(webhook)
            
            await session.commit()
            
            # Display credentials
            print("\n" + "="*60)
            print("🎉 Service Created Successfully!")
            print("="*60)
            print(f"\n🆔 Service ID: {service.id}")
            print(f"🔑 API Key: {api_key}")
            print("\n⚠️  IMPORTANT: Save these credentials! The API key won't be shown again.")
            
            print(f"\n🔐 Authentication Headers:")
            print(f"   X-Service-Id: {service.id}")
            print(f"   X-API-Key: {api_key}")
            
            # Example requests
            print(f"\n📝 Example API Requests:")
            print(f"\n1. Send SMS:")
            print(f'''curl -X POST http://localhost:8000/api/v1/notifications/send \\
  -H "Content-Type: application/json" \\
  -H "X-Service-Id: {service.id}" \\
  -H "X-API-Key: {api_key}" \\
  -d '{{"channel": "sms", "recipient": "+1234567890", "content": "Hello from {name}!"}}'
            ''')
            
            print(f"\n2. Send Email:")
            print(f'''curl -X POST http://localhost:8000/api/v1/notifications/send \\
  -H "Content-Type: application/json" \\
  -H "X-Service-Id: {service.id}" \\
  -H "X-API-Key: {api_key}" \\
  -d '{{
    "channel": "email",
    "recipient": "user@example.com",
    "subject": "Welcome!",
    "content": "Hello from {name}!",
    "content_type": "html"
  }}'
            ''')
            
            if webhooks:
                print(f"\n3. Test Webhook:")
                print(f"   Your webhooks will receive notifications at:")
                for webhook in webhooks:
                    if webhook['is_active']:
                        print(f"   - {webhook['url']}")
            
            print("\n" + "="*60)
            
        except Exception as e:
            print(f"\n❌ Error creating service: {str(e)}")
            await session.rollback()
            raise
        finally:
            await engine.dispose()


async def list_services():
    """List all existing services."""
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        try:
            query = select(ServiceUser).order_by(ServiceUser.created_at.desc())
            result = await session.execute(query)
            services = result.scalars().all()
            
            if not services:
                print("\n❌ No services found.")
                return
            
            print(f"\n📋 Existing Services ({len(services)}):")
            print("-" * 80)
            
            for service in services:
                print(f"\n🏷️  {service.name}")
                print(f"   ID: {service.id}")
                print(f"   Active: {'✅' if service.is_active else '❌'}")
                print(f"   Created: {service.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
                
                # Get webhook count
                webhook_query = select(Webhook).where(Webhook.service_id == service.id)
                webhook_result = await session.execute(webhook_query)
                webhooks = webhook_result.scalars().all()
                active_webhooks = [w for w in webhooks if w.is_active]
                
                print(f"   Webhooks: {len(active_webhooks)} active / {len(webhooks)} total")
                
                if service.description:
                    print(f"   Description: {service.description}")
            
            print("\n" + "-" * 80)
            
        finally:
            await engine.dispose()


async def reset_api_key():
    """Reset API key for an existing service."""
    print_header()
    print("🔑 Reset Service API Key")
    print("-" * 40)
    
    # List existing services first
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        try:
            query = select(ServiceUser).order_by(ServiceUser.name)
            result = await session.execute(query)
            services = result.scalars().all()
            
            if not services:
                print("\n❌ No services found.")
                return
            
            print("\n📋 Available Services:")
            for i, service in enumerate(services):
                print(f"{i+1}. {service.name} (ID: {service.id})")
            
            # Get service selection
            while True:
                choice = get_input("\nSelect service number (or 'q' to quit)")
                
                if choice.lower() == 'q':
                    print("\n❌ Operation cancelled.")
                    return
                
                try:
                    index = int(choice) - 1
                    if 0 <= index < len(services):
                        selected_service = services[index]
                        break
                    else:
                        print("❌ Invalid selection. Please try again.")
                except ValueError:
                    print("❌ Please enter a number.")
            
            # Confirm reset
            print(f"\n⚠️  You are about to reset the API key for: {selected_service.name}")
            print("   This will invalidate the current API key!")
            
            confirm = get_yes_no("\nAre you sure you want to continue?", default=False)
            
            if not confirm:
                print("\n❌ API key reset cancelled.")
                return
            
            # Generate new API key
            new_api_key = f"{selected_service.id.hex}-{uuid.uuid4().hex}"
            
            # Import the encryption function
            from app.core.security import encrypt_api_key
            selected_service.api_key_hash = encrypt_api_key(new_api_key)
            selected_service.updated_at = datetime.now(timezone.utc)
            
            await session.commit()
            
            # Display new credentials
            print("\n" + "="*60)
            print("✅ API Key Reset Successfully!")
            print("="*60)
            print(f"\n🏷️  Service: {selected_service.name}")
            print(f"🆔 Service ID: {selected_service.id}")
            print(f"🔑 New API Key: {new_api_key}")
            print("\n⚠️  IMPORTANT: Save this API key! It won't be shown again.")
            
            print(f"\n🔐 New Authentication Headers:")
            print(f"   X-Service-Id: {selected_service.id}")
            print(f"   X-API-Key: {new_api_key}")
            
            print("\n" + "="*60)
            
        except Exception as e:
            print(f"\n❌ Error resetting API key: {str(e)}")
            await session.rollback()
            raise
        finally:
            await engine.dispose()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "--list":
            asyncio.run(list_services())
        elif sys.argv[1] == "--reset-key":
            asyncio.run(reset_api_key())
        else:
            print("\nUsage:")
            print("  python tools/create_service.py           # Create new service")
            print("  python tools/create_service.py --list    # List all services")
            print("  python tools/create_service.py --reset-key  # Reset API key")
    else:
        asyncio.run(create_service_interactive())
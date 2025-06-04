#!/usr/bin/env python
"""
Seed script to create a mock service with webhooks for testing.
Usage: python tools/seed_service.py
"""

import asyncio
import sys
import os
from datetime import datetime

# Add the app directory to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from app.models.service_user import ServiceUser
from app.models.webhook import Webhook
from app.core.config import settings
import uuid


async def create_mock_service():
    """Create a mock service with webhooks for testing."""
    
    # Create async engine
    engine = create_async_engine(settings.DATABASE_URL, echo=True)
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    
    async with async_session() as session:
        try:
            # Check if mock_service already exists
            query = select(ServiceUser).where(ServiceUser.name == "mock_service")
            result = await session.execute(query)
            existing_service = result.scalar_one_or_none()
            
            if existing_service:
                print(f"\n✅ Service 'mock_service' already exists!")
                print(f"Service ID: {existing_service.id}")
                print(f"Is Active: {existing_service.is_active}")
                
                # Check if webhooks exist
                webhook_query = select(Webhook).where(Webhook.service_id == existing_service.id)
                webhook_result = await session.execute(webhook_query)
                webhooks = webhook_result.scalars().all()
                
                if webhooks:
                    print(f"\n📌 Existing webhooks:")
                    for webhook in webhooks:
                        print(f"  - {webhook.url} (Active: {webhook.is_active})")
                
                return existing_service
            
            # Create new service
            service, api_key = await ServiceUser.create_service(
                db=session,
                name="mock_service",
                description="Mock service for testing notification system"
            )
            
            print(f"\n🎉 Created new service 'mock_service'!")
            print(f"Service ID: {service.id}")
            print(f"API Key: {api_key}")
            print(f"\n⚠️  IMPORTANT: Save this API key! It won't be shown again.")
            
            # Create default webhooks
            webhooks_data = [
                {
                    "url": "https://webhook.site/YOUR-UNIQUE-ID",  # Replace with your webhook.site URL
                    "description": "Primary webhook endpoint for testing"
                },
                {
                    "url": "http://localhost:8001/webhook",
                    "description": "Local development webhook endpoint"
                }
            ]
            
            for webhook_data in webhooks_data:
                webhook = Webhook(
                    id=uuid.uuid4(),
                    service_id=service.id,
                    url=webhook_data["url"],
                    description=webhook_data["description"],
                    is_active=True,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                session.add(webhook)
            
            await session.commit()
            
            print(f"\n📌 Created webhooks:")
            for webhook_data in webhooks_data:
                print(f"  - {webhook_data['url']}")
            
            print(f"\n🔐 Authentication headers for API requests:")
            print(f"X-Service-Id: {service.id}")
            print(f"X-API-Key: {api_key}")
            
            print(f"\n📝 Example curl command:")
            print(f'''curl -X POST http://localhost:8000/api/v1/sms \\
  -H "Content-Type: application/json" \\
  -H "X-Service-Id: {service.id}" \\
  -H "X-API-Key: {api_key}" \\
  -d '{{"recipient": "+1234567890", "content": "Test message"}}'
            ''')
            
            return service
            
        except Exception as e:
            print(f"\n❌ Error creating mock service: {str(e)}")
            await session.rollback()
            raise
        finally:
            await engine.dispose()


async def update_webhook_urls():
    """Update webhook URLs for existing mock_service."""
    
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    
    async with async_session() as session:
        try:
            # Get mock_service
            query = select(ServiceUser).where(ServiceUser.name == "mock_service")
            result = await session.execute(query)
            service = result.scalar_one_or_none()
            
            if not service:
                print("❌ Service 'mock_service' not found. Run the script first to create it.")
                return
            
            # Get webhooks
            webhook_query = select(Webhook).where(Webhook.service_id == service.id)
            webhook_result = await session.execute(webhook_query)
            webhooks = webhook_result.scalars().all()
            
            if not webhooks:
                print("❌ No webhooks found for mock_service")
                return
            
            print(f"\n📌 Current webhooks for mock_service:")
            for i, webhook in enumerate(webhooks):
                print(f"{i+1}. {webhook.url} (Active: {webhook.is_active})")
            
            # Ask user if they want to update
            update = input("\nDo you want to update webhook URLs? (y/n): ")
            if update.lower() != 'y':
                return
            
            # Update webhook URLs
            for i, webhook in enumerate(webhooks):
                new_url = input(f"\nEnter new URL for webhook {i+1} (or press Enter to keep current): ")
                if new_url:
                    webhook.url = new_url  # type: ignore
                    webhook.updated_at = datetime.utcnow()  # type: ignore
            
            await session.commit()
            print("\n✅ Webhook URLs updated successfully!")
            
        except Exception as e:
            print(f"\n❌ Error updating webhooks: {str(e)}")
            await session.rollback()
        finally:
            await engine.dispose()


if __name__ == "__main__":
    print("🚀 Notification Service - Service Seeder")
    print("=" * 50)
    
    # Check if user wants to update webhooks
    if len(sys.argv) > 1 and sys.argv[1] == "--update-webhooks":
        asyncio.run(update_webhook_urls())
    else:
        asyncio.run(create_mock_service())
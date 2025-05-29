# Notification Microservice

A robust, scalable notification microservice built with FastAPI, PostgreSQL, Redis, and Celery. It supports multiple notification channels (SMS, Email, WhatsApp) with provider abstraction, authentication, webhook callbacks, and advanced retry mechanisms.

## 📚 Documentation

- **[Architecture Guide](ARCHITECTURE.md)** - Detailed system architecture, components, and design decisions
- **[Flow Documentation](FLOWS.md)** - Step-by-step flows for all operations
- **[CLI Guide](CLI_GUIDE.md)** - Comprehensive CLI tools documentation

## Table of Contents
- [Overview](#overview)
- [Architecture](#architecture)
- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Database Setup](#database-setup)
- [Running the Service](#running-the-service)
- [CLI Tools](#cli-tools)
- [Authentication](#authentication)
- [API Documentation](#api-documentation)
- [Webhook System](#webhook-system)
- [Provider Management](#provider-management)
- [Service Management](#service-management)
- [How It Works](#how-it-works)
- [Testing](#testing)
- [Monitoring](#monitoring)
- [Troubleshooting](#troubleshooting)

## Overview

This microservice provides a unified API for sending notifications through various channels while handling:
- **Multi-provider support** with automatic failover
- **Service authentication** with API keys
- **Webhook callbacks** for delivery status
- **Advanced retry logic** with exponential backoff
- **Rate limiting** for API protection
- **Deduplication** to prevent duplicate messages
- **Priority-based queuing** for time-sensitive notifications

## Architecture

The notification microservice uses a modern, scalable architecture with async processing and provider abstraction.

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Client    │────▶│  FastAPI    │────▶│   Celery    │
│  Service    │     │    API      │     │   Worker    │
└─────────────┘     └─────────────┘     └─────────────┘
                            │                    │
                            ▼                    ▼
                    ┌─────────────┐     ┌─────────────┐
                    │ PostgreSQL  │     │   Redis     │
                    │  Database   │     │   Queue     │
                    └─────────────┘     └─────────────┘
                                               │
                                               ▼
                                    ┌─────────────────────┐
                                    │ Notification        │
                                    │ Providers           │
                                    │ (MSG91, Mock, etc)  │
                                    └─────────────────────┘
```

📖 **[See detailed architecture documentation →](ARCHITECTURE.md)**

## Features

### Core Features
- **Multi-channel Support**: SMS, Email, WhatsApp
- **Provider Abstraction**: Easy to add new providers
- **Async Processing**: Non-blocking API with Celery workers
- **Retry Mechanism**: Configurable retry with exponential backoff
- **Priority Queuing**: Instant, High, Normal, Low priorities
- **Deduplication**: Prevent duplicate messages within time window

### Security & Authentication
- **Service Authentication**: API key-based authentication
- **Rate Limiting**: Per-service rate limits (20 failed attempts per 2 hours)
- **Service Isolation**: Services can only access their own data

### Webhook System
- **Delivery Callbacks**: Automatic webhooks on successful delivery
- **Retry Logic**: 5-6 immediate attempts, then exponential backoff up to 3 hours
- **Status Updates**: Webhooks for retry attempts and failures
- **Acknowledgment**: 200 OK response marks webhook as acknowledged

### Monitoring & Management
- **Delivery Tracking**: Complete history of delivery attempts
- **Status API**: Query notification status and details
- **Revocation**: Cancel pending notifications
- **Provider Management**: Database-driven provider configuration

## Prerequisites

- Python 3.11+
- PostgreSQL 15+
- Redis 7+
- Docker & Docker Compose (recommended)

## Installation

### Using Docker (Recommended)

1. Clone the repository:
```bash
git clone https://github.com/yourusername/notification-microservice.git
cd notification-microservice
```

2. Create environment file:
```bash
cp .env.example .env
```

3. Configure your environment variables in `.env`:
```env
# Database
DATABASE_URL=postgresql+asyncpg://notification_user:dev_password@postgres:5432/notification_service
POSTGRES_PASSWORD=dev_password

# MSG91 API (Optional - for SMS/WhatsApp)
MSG91_API_KEY=your_msg91_api_key
MSG91_SENDER_ID=your_sender_id

# Security
INTERNAL_API_KEY=your-default-development-key
API_KEY_SALT=change-this-in-production-to-a-random-string
SERVICE_REGISTRATION_PASSWORD=secure-registration-password-change-me
```

4. Build and start services:
```bash
docker-compose up --build
```

This will start:
- **API Service**: http://localhost:8000
- **PostgreSQL**: localhost:5433
- **Redis**: localhost:6379
- **Celery Worker**: Background worker
- **Flower**: http://localhost:5556 (Celery monitoring)

### Manual Installation

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Install and start PostgreSQL and Redis

3. Run database migrations:
```bash
alembic upgrade head
```

4. Start the API server:
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

5. Start Celery worker:
```bash
celery -A app.core.celery_app worker --loglevel=info
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | Required |
| `MSG91_API_KEY` | MSG91 API key for SMS/WhatsApp | Optional |
| `MSG91_SENDER_ID` | MSG91 sender ID | "often" |
| `CELERY_BROKER_URL` | Redis URL for Celery | redis://redis:6379/0 |
| `CELERY_RESULT_BACKEND` | Redis URL for results | redis://redis:6379/0 |
| `API_KEY_SALT` | Salt for API key hashing | Required |

## Database Setup

### Running Migrations

```bash
# Inside container
docker-compose exec notification-service alembic upgrade head

# Or locally
alembic upgrade head
```

### Seeding Data

The service includes interactive CLI tools for setup and configuration. See the [CLI Guide](CLI_GUIDE.md) for detailed documentation.

#### 1. Seed Providers

The service includes a provider seeding tool to add notification providers:

```bash
# Inside container
docker-compose exec notification-service python tools/seed_provider.py

# Or locally
python tools/seed_provider.py
```

This creates two default providers:
- **mock**: A mock provider for testing (supports all channels)
- **msg91**: MSG91 provider for SMS and WhatsApp

#### 2. Create Service Account

Create a service account with API credentials:

**Option A: Interactive Service Creation (Recommended)**
```bash
# Inside container
docker-compose exec notification-service python tools/create_service.py

# Or locally
python tools/create_service.py
```

This provides:
- Interactive prompts for service configuration
- Multiple webhook setup with advanced options
- Custom headers and event filtering
- Retry configuration per webhook

**Option B: Quick Mock Service**
```bash
# Inside container
docker-compose exec notification-service python tools/seed_service.py

# Or locally
python tools/seed_service.py
```

This creates:
- A `mock_service` account with API credentials
- Two webhook URLs for testing
- Example curl commands

**Important**: Save the API key shown - it won't be displayed again!

Example output:
```
🎉 Created new service 'mock_service'!
Service ID: 53e80e3e-36b6-4518-88d7-474893a8b9eb
API Key: 53e80e3e36b6451888d7474893a8b9eb-7db6ecc86400431790df49a17596962a

📌 Created webhooks:
  - https://webhook.site/YOUR-UNIQUE-ID
  - http://localhost:8001/webhook
```

## Running the Service

### Development Mode

```bash
# Start all services
docker-compose up

# Or start specific services
docker-compose up api worker

# View logs
docker-compose logs -f notification-service
docker-compose logs -f celery-worker
```

### Production Mode

```bash
# Build optimized images
docker-compose -f docker-compose.yml -f docker-compose.prod.yml build

# Start services
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

## CLI Tools

The notification microservice includes comprehensive CLI tools for setup, management, and operations.

### Service Management

```bash
# Interactive service creation with webhooks
python tools/create_service.py

# List all services
python tools/create_service.py --list

# Reset API key for a service
python tools/create_service.py --reset-key

# Quick mock service setup
python tools/seed_service.py
```

### Provider Management

```bash
# Interactive provider setup
python tools/seed_provider.py
```

### Key Features:
- **Interactive Prompts**: User-friendly guided setup
- **Webhook Configuration**: Advanced webhook options with retry settings
- **Secure Credentials**: API keys are hashed and shown only once
- **Service Isolation**: Each service has its own API key and data access

📖 **[See complete CLI documentation →](CLI_GUIDE.md)**

## Authentication

All API endpoints require authentication using service credentials:

### Headers Required
- `X-Service-Id`: Your service UUID
- `X-API-Key`: Your service API key

### Example Request
```bash
curl -X POST http://localhost:8000/api/v1/sms \
  -H "Content-Type: application/json" \
  -H "X-Service-Id: 53e80e3e-36b6-4518-88d7-474893a8b9eb" \
  -H "X-API-Key: 53e80e3e36b6451888d7474893a8b9eb-7db6ecc86400431790df49a17596962a" \
  -d '{
    "recipient": "+1234567890",
    "content": "Hello from Notification Service!",
    "priority": "high"
  }'
```

### Rate Limiting
- Failed authentication attempts are rate-limited
- Maximum 20 failed attempts per 2 hours per service
- Successful authentication resets the counter

## API Documentation

### Base URL
```
http://localhost:8000/api/v1
```

### Endpoints

#### 1. Send SMS
```http
POST /sms
```

Request:
```json
{
  "recipient": "+1234567890",
  "content": "Your OTP is 123456",
  "sender_id": "MYAPP",
  "provider_id": "msg91",
  "priority": "instant",
  "meta_data": {
    "user_id": "12345",
    "campaign": "otp"
  }
}
```

Response:
```json
{
  "success": true,
  "status": "queued",
  "provider_name": "msg91",
  "message_id": null,
  "provider_response": {
    "message": "Notification queued for processing",
    "notification_id": "550e8400-e29b-41d4-a716-446655440000"
  }
}
```

#### 2. Send Email
```http
POST /email
```

Request:
```json
{
  "to": ["user@example.com"],
  "subject": "Welcome to our service",
  "body": "Plain text content",
  "html_body": "<h1>HTML content</h1>",
  "priority": "normal",
  "provider_id": "mock"
}
```

#### 3. Send WhatsApp
```http
POST /whatsapp
```

Request:
```json
{
  "recipient": "+1234567890",
  "content": "Your order #12345 has been shipped",
  "template_id": "order_shipped",
  "media_url": "https://example.com/image.jpg",
  "priority": "high"
}
```

#### 4. Get Notification Details
```http
GET /notifications/{notification_id}
```

Response:
```json
{
  "notification": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "type": "sms",
    "status": "delivered",
    "recipient": "+1234567890",
    "content": "Your OTP is 123456",
    "priority": "instant",
    "retry_count": 0,
    "retries_left": 3,
    "created_at": "2024-01-15T10:30:00",
    "delivered_at": "2024-01-15T10:30:02"
  },
  "delivery_attempts": [
    {
      "id": "attempt-id",
      "status": "delivered",
      "provider_id": "msg91",
      "attempted_at": "2024-01-15T10:30:01",
      "response_data": {...}
    }
  ],
  "task_info": {
    "status": null,
    "eta": null,
    "max_retries": 3
  }
}
```

#### 5. List Service Notifications
```http
GET /notifications?skip=0&limit=100&status=delivered&notification_type=sms
```

Parameters:
- `skip`: Pagination offset (default: 0)
- `limit`: Results per page (max: 1000)
- `status`: Filter by status (pending, queued, delivered, failed)
- `notification_type`: Filter by type (sms, email, whatsapp)

#### 6. Revoke Notification
```http
POST /notifications/{notification_id}/revoke
```

Response:
```json
{
  "message": "Notification 550e8400-e29b-41d4-a716-446655440000 has been revoked",
  "status": "CANCELLED"
}
```

#### 7. List Providers
```http
GET /providers
```

Response:
```json
[
  {
    "id": "provider-uuid",
    "name": "msg91",
    "supported_types": ["sms", "whatsapp"],
    "is_active": true,
    "priority": 1
  }
]
```

### API Documentation UI

Interactive API documentation is available at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Webhook System

The notification service includes a comprehensive webhook system that sends real-time notifications about delivery status and events. This enables your application to track notification lifecycle and respond to delivery events.

### Overview

Webhooks are HTTP POST requests sent to your configured endpoints whenever specific events occur:
- **Created**: When a notification is initially created
- **Retry Scheduled**: When a notification is queued for retry
- **Retry Attempted**: When a retry attempt is made
- **Delivered**: When a notification is successfully delivered
- **Failed**: When all delivery attempts have failed
- **Cancelled**: When a notification is manually revoked

### Webhook Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Notification  │────▶│  Webhook System  │────▶│  Your Endpoint  │
│     Events      │     │                  │     │                 │
└─────────────────┘     └──────────────────┘     └─────────────────┘
        │                        │                        │
        │                        │                        │
        ▼                        ▼                        ▼
 ┌─────────────┐         ┌─────────────┐         ┌─────────────┐
 │  Database   │         │   Redis     │         │  Response   │
 │   Events    │         │   Queue     │         │   Handler   │
 └─────────────┘         └─────────────┘         └─────────────┘
```

### How Webhooks Work

#### 1. Event-Driven Architecture
- Webhooks are triggered at each stage of the notification lifecycle
- Events are processed immediately for the first attempt
- Failed webhooks are queued for retry with exponential backoff

#### 2. Delivery Strategy
- **Immediate Attempt**: First webhook is sent synchronously when the event occurs
- **Retry Queue**: Failed webhooks are placed in a separate queue for background processing
- **Smart Retry Logic**: Different retry behavior based on HTTP response codes

#### 3. Retry Logic
```
First Attempt (Immediate)
    ↓ (if fails)
Retry Queue → Attempt 1 (1 minute delay)
    ↓ (if fails)  
Retry Queue → Attempt 2 (5 minute delay)
    ↓ (if fails)
Retry Queue → Attempt 3 (15 minute delay)
    ↓ (if fails)
Mark as FAILED
```

### Webhook Configuration

#### 1. Create Webhooks via API

```http
POST /api/v1/webhooks
Content-Type: application/json
X-Service-Id: your-service-id
X-API-Key: your-api-key

{
  "url": "https://your-app.com/webhook",
  "description": "Production webhook endpoint",
  "is_active": true
}
```

#### 2. List Your Webhooks

```http
GET /api/v1/webhooks
X-Service-Id: your-service-id
X-API-Key: your-api-key
```

Response:
```json
{
  "webhooks": [
    {
      "id": "webhook-uuid",
      "url": "https://your-app.com/webhook",
      "description": "Production webhook endpoint",
      "is_active": true,
      "created_at": "2024-01-15T10:30:00",
      "updated_at": "2024-01-15T10:30:00"
    }
  ]
}
```

### Webhook Events & Payloads

#### Event: `notification.created`
Sent when a notification is first created and queued.

```json
{
  "event": "created",
  "notification_id": "550e8400-e29b-41d4-a716-446655440000",
  "service_id": "service-uuid",
  "type": "sms",
  "status": "pending",
  "recipient": "+1234567890",
  "content": "Your OTP is 123456",
  "subject": null,
  "priority": "high",
  "created_at": "2024-01-15T10:30:00Z",
  "meta_data": {
    "user_id": "12345",
    "campaign": "otp"
  },
  "attempt_number": 0,
  "total_attempts": 0,
  "max_retries": 3,
  "webhook_attempt": 1
}
```

#### Event: `notification.delivered`
Sent when a notification is successfully delivered.

```json
{
  "event": "delivered",
  "notification_id": "550e8400-e29b-41d4-a716-446655440000",
  "service_id": "service-uuid",
  "type": "sms",
  "status": "delivered",
  "recipient": "+1234567890",
  "content": "Your OTP is 123456",
  "subject": null,
  "priority": "high",
  "created_at": "2024-01-15T10:30:00Z",
  "delivered_at": "2024-01-15T10:30:05Z",
  "external_id": "msg91-message-id",
  "provider_response": {
    "status": "delivered",
    "message_id": "msg91-message-id"
  },
  "attempt_number": 1,
  "total_attempts": 1,
  "webhook_attempt": 1
}
```

#### Event: `notification.failed`
Sent when all delivery attempts have been exhausted.

```json
{
  "event": "failed",
  "notification_id": "550e8400-e29b-41d4-a716-446655440000",
  "service_id": "service-uuid",
  "type": "sms",
  "status": "failed",
  "recipient": "+1234567890",
  "content": "Your OTP is 123456",
  "subject": null,
  "priority": "high",
  "created_at": "2024-01-15T10:30:00Z",
  "failed_at": "2024-01-15T11:00:00Z",
  "error_message": "All delivery attempts failed",
  "attempt_number": 3,
  "total_attempts": 3,
  "max_retries": 3,
  "webhook_attempt": 1
}
```

#### Event: `notification.cancelled`
Sent when a notification is manually revoked/cancelled.

```json
{
  "event": "cancelled",
  "notification_id": "550e8400-e29b-41d4-a716-446655440000",
  "service_id": "service-uuid",
  "type": "sms",
  "status": "cancelled",
  "recipient": "+1234567890",
  "content": "Your OTP is 123456",
  "subject": null,
  "priority": "high",
  "created_at": "2024-01-15T10:30:00Z",
  "cancelled_at": "2024-01-15T10:32:00Z",
  "cancellation_reason": "Revoked by user",
  "attempt_number": 0,
  "webhook_attempt": 1
}
```

### Webhook Headers

Every webhook request includes these headers:

```http
Content-Type: application/json
X-Webhook-Event: notification.delivered
X-Notification-Id: 550e8400-e29b-41d4-a716-446655440000
X-Service-Id: service-uuid
X-Webhook-Attempt: 1
User-Agent: NotificationService-Webhook/1.0
```

### Webhook Response Handling

#### Success Response (200 OK)
```json
{
  "status": "received",
  "message": "Webhook processed successfully"
}
```

#### Retry Logic Based on Status Codes

| Status Code Range | Action | Retry Behavior |
|-------------------|--------|----------------|
| 200-299 | Success | Mark as acknowledged, no retries |
| 400-499 | Client Error | Stop retrying, mark as failed |
| 500-599 | Server Error | Retry with exponential backoff |
| Network Error | Connection Issue | Retry with exponential backoff |
| Timeout | Request Timeout | Retry with exponential backoff |

### Setting Up Webhook Endpoints

#### 1. Python/FastAPI Webhook Endpoint

```python
from fastapi import FastAPI, Request, Header
from typing import Optional
import json

app = FastAPI()

@app.post("/webhook")
async def receive_webhook(
    request: Request,
    x_webhook_event: Optional[str] = Header(None),
    x_notification_id: Optional[str] = Header(None),
    x_webhook_attempt: Optional[int] = Header(None)
):
    payload = await request.json()
    
    print(f"Received {x_webhook_event} for notification {x_notification_id}")
    print(f"Attempt: {x_webhook_attempt}")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    
    # Process based on event type
    event = payload.get('event')
    
    if event == 'delivered':
        print("✅ Notification delivered successfully")
        # Update your database, send confirmation email, etc.
        
    elif event == 'failed':
        print("❌ Notification delivery failed")
        # Log error, alert admins, retry with different method, etc.
        
    elif event == 'cancelled':
        print("🚫 Notification was cancelled")
        # Update UI, clean up resources, etc.
    
    # Return 200 OK to acknowledge
    return {"status": "received", "processed": True}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
```

#### 2. Testing with webhook.site

For quick testing without setting up your own endpoint:

1. Go to https://webhook.site
2. Copy your unique URL (e.g., `https://webhook.site/#!/12345678-1234-1234-1234-123456789012`)
3. Add this URL as a webhook in your service
4. Send test notifications and view real-time webhook data

### Webhook Monitoring

#### 1. View Webhook Deliveries

```http
GET /api/v1/webhooks/{webhook_id}/deliveries
X-Service-Id: your-service-id
X-API-Key: your-api-key
```

Response:
```json
{
  "webhook_id": "webhook-uuid",
  "deliveries": [
    {
      "id": "delivery-uuid",
      "notification_id": "550e8400-e29b-41d4-a716-446655440000",
      "status": "acknowledged", 
      "attempt_count": 1,
      "last_attempt_at": "2024-01-15T10:30:02Z",
      "acknowledged_at": "2024-01-15T10:30:02Z",
      "response_status_code": 200,
      "response_body": "{\"status\":\"received\"}",
      "created_at": "2024-01-15T10:30:01Z"
    }
  ]
}
```

### Best Practices

1. **Endpoint Design**
   - Always return 200 OK for successful processing
   - Return 4xx for client errors (don't retry)
   - Return 5xx for server errors (will retry)
   - Keep processing time under 30 seconds

2. **Error Handling**
   - Implement proper error handling in webhook endpoints
   - Log all webhook events for debugging
   - Consider idempotency for duplicate deliveries

3. **Security**
   - Use HTTPS endpoints
   - Validate incoming payload structure
   - Implement rate limiting on webhook endpoints

4. **Monitoring**
   - Monitor webhook delivery success rates
   - Set up alerts for repeated failures
   - Track webhook processing performance

## Provider Management

### Available Providers

1. **Mock Provider** (Default)
   - Supports: SMS, Email, WhatsApp
   - Purpose: Testing and development
   - Always returns success

2. **MSG91 Provider**
   - Supports: SMS, WhatsApp
   - Requires: MSG91_API_KEY in environment
   - Production-ready

### Adding a New Provider

1. Create provider class in `app/providers/`:
```python
from app.providers.base import BaseProvider

class NewProvider(BaseProvider):
    def __init__(self, config: Dict[str, Any]):
        super().__init__("new_provider", config)
    
    async def send_sms(self, message: SMSMessage) -> ProviderResponse:
        # Implementation
        pass
```

2. Register in `app/providers/registry.py`

3. Add to database using seed script

### Provider Selection

Providers are selected based on:
1. Explicit `provider_id` in request
2. Notification type support
3. Provider priority in database
4. Active status

## Service Management

### Creating a New Service

1. Using the seed script:
```bash
python tools/seed_service.py
```

2. Programmatically:
```python
from app.models.service_user import ServiceUser

service, api_key = await ServiceUser.create_service(
    db=session,
    name="my_service",
    description="My application service"
)
print(f"API Key: {api_key}")  # Save this!
```

### Managing Webhooks

Update webhook URLs:
```bash
python tools/seed_service.py --update-webhooks
```

## How It Works

### Notification Flow

1. **API Request**: Client sends notification request with authentication
2. **Validation**: Request validated and deduplicated
3. **Database**: Notification record created with PENDING status
4. **Queue**: Task queued to Celery based on priority
5. **Worker Processing**:
   - Worker picks up task
   - Selects appropriate provider
   - Attempts delivery
   - Updates status (DELIVERED/FAILED)
6. **Webhook Trigger**: On success, webhook notifications queued
7. **Webhook Delivery**: Webhooks sent with retry logic

### What Happens at Each Step

#### Step 1: API Request
- Client sends POST request to `/api/v1/notifications/{type}`
- Headers include Service ID and API Key
- Request body contains recipient, content, and optional parameters

#### Step 2: Authentication & Validation
- Service credentials verified against database
- Rate limiting checked (max 20 failed attempts per 2 hours)
- Request body validated using Pydantic models
- Deduplication check performed (30-minute window)

#### Step 3: Database Operations
- Notification record created with UUID
- Status set to PENDING
- Provider selected based on type and priority
- Task ID stored for tracking

#### Step 4: Task Queuing
- Task sent to Celery via Redis
- Priority determines queue:
  - `instant/high` → high_priority queue
  - `normal/low` → default queue
- Task contains notification ID for async processing

#### Step 5: Background Processing
- Worker fetches notification from database
- Provider API called (MSG91, etc.)
- Response processed and status updated
- Delivery attempts logged

#### Step 6: Webhook Notifications
- Active webhooks loaded for service
- Event payload constructed with full details
- Immediate HTTP POST attempt
- Failed webhooks queued for retry

#### Step 7: Webhook Retry Logic
- Failed webhooks retry with exponential backoff
- Delays: 1 minute → 5 minutes → 15 minutes
- Status codes determine retry behavior:
  - 2xx: Success, no retry
  - 4xx: Client error, no retry
  - 5xx/timeout: Server error, retry

📖 **[See detailed flow documentation →](FLOWS.md)**

### Priority Handling

- **Instant**: Processed immediately in high-priority queue
- **High**: Processed with higher priority
- **Normal**: Standard queue processing
- **Low**: Processed when queues are less busy

### Retry Mechanism

1. **Provider Failures**: Up to 3 retries with delays (5min, 15min, 30min)
2. **Webhook Failures**: 
   - 5-6 immediate attempts
   - Then exponential backoff up to 3 hours
3. **Final State**: Marked as FAILED after all retries exhausted

### Deduplication

- Prevents duplicate messages within 30-minute window
- Based on: recipient + content + type
- Can be disabled per request

## Testing

### Using Mock Service

1. Get credentials from seed script output
2. Test SMS notification:
```bash
curl -X POST http://localhost:8000/api/v1/sms \
  -H "Content-Type: application/json" \
  -H "X-Service-Id: YOUR_SERVICE_ID" \
  -H "X-API-Key: YOUR_API_KEY" \
  -d '{
    "recipient": "+1234567890",
    "content": "Test message"
  }'
```

3. Check notification status:
```bash
curl -X GET http://localhost:8000/api/v1/notifications/NOTIFICATION_ID \
  -H "X-Service-Id: YOUR_SERVICE_ID" \
  -H "X-API-Key: YOUR_API_KEY"
```

### Testing Webhooks

1. Use webhook.site for easy testing
2. Update webhook URL in database
3. Send a notification
4. Check webhook.site for received payloads

## Monitoring

### Celery Flower

Monitor task queues and workers:
- URL: http://localhost:5556
- Shows active tasks, completed tasks, failures
- Worker status and performance

### Database Queries

Check notification status:
```sql
-- Recent notifications
SELECT id, type, status, recipient, created_at 
FROM notifications 
ORDER BY created_at DESC 
LIMIT 10;

-- Failed notifications
SELECT * FROM notifications 
WHERE status = 'failed' 
AND created_at > NOW() - INTERVAL '1 hour';

-- Webhook delivery status
SELECT * FROM webhook_deliveries 
WHERE status != 'acknowledged' 
ORDER BY created_at DESC;
```

### Logs

View service logs:
```bash
# API logs
docker-compose logs -f notification-service

# Worker logs
docker-compose logs -f celery-worker

# All logs
docker-compose logs -f
```

## Troubleshooting

### Common Issues

1. **Authentication Errors**
   - Verify headers: `X-Service-Id` and `X-API-Key`
   - Check if service is active in database
   - Check rate limit status

2. **Notifications Not Sending**
   - Check Celery worker is running
   - Verify provider configuration
   - Check provider API keys
   - Look for errors in worker logs

3. **Webhooks Not Received**
   - Verify webhook URL is accessible
   - Check webhook_deliveries table for attempts
   - Ensure notification was delivered successfully
   - Check for network/firewall issues

4. **Database Connection Issues**
   - Verify DATABASE_URL is correct
   - Check PostgreSQL is running
   - Run migrations: `alembic upgrade head`

### Debug Mode

Enable debug logging:
```python
# In app/core/config.py
ENVIRONMENT = "development"  # Enables debug logs
```

### Health Check

Check service health:
```bash
curl http://localhost:8000/health
```

Response:
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z",
  "version": "1.0.0",
  "services": {
    "database": "connected",
    "redis": "connected",
    "celery": "running"
  }
}
```

## Project Structure

```
notification-microservice/
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── notifications.py    # Main API endpoints
│   │       ├── health.py          # Health check endpoint
│   │       └── stats.py           # Statistics endpoints
│   ├── core/
│   │   ├── auth.py               # Authentication middleware
│   │   ├── celery.py             # Celery configuration
│   │   ├── config.py             # Application settings
│   │   ├── database.py           # Database connection
│   │   └── security.py           # Security utilities
│   ├── models/
│   │   ├── notification.py       # Notification model
│   │   ├── service_user.py       # Service/User model
│   │   ├── webhook.py            # Webhook models
│   │   ├── provider.py           # Provider model
│   │   └── delivery_attempt.py   # Delivery tracking
│   ├── providers/
│   │   ├── base.py              # Base provider class
│   │   ├── mock_provider.py     # Mock provider
│   │   ├── msg91_provider.py    # MSG91 provider
│   │   └── registry.py          # Provider registry
│   ├── repositories/
│   │   ├── notification_repository.py
│   │   └── provider_repository.py
│   ├── services/
│   │   └── notification_service.py  # Business logic
│   ├── tasks/
│   │   ├── notification_tasks.py    # Celery tasks
│   │   └── webhook_tasks.py         # Webhook tasks
│   └── main.py                      # FastAPI app
├── alembic/
│   └── versions/                    # Database migrations
├── tools/
│   ├── seed_provider.py            # Provider seeding
│   └── seed_service.py             # Service seeding
├── docker-compose.yml              # Docker configuration
├── Dockerfile                      # API container
├── Dockerfile.worker              # Worker container
├── requirements.txt               # Python dependencies
└── README.md                      # This file
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
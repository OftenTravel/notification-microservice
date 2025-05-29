# Notification Microservice CLI Guide

## Table of Contents
- [Overview](#overview)
- [Setup Tools](#setup-tools)
- [Service Management](#service-management)
- [Provider Management](#provider-management)
- [Database Management](#database-management)
- [Testing Tools](#testing-tools)
- [Development Workflow](#development-workflow)
- [Production Deployment](#production-deployment)

## Overview

The Notification Microservice provides a comprehensive set of CLI tools for setup, configuration, and management. All tools are designed to be interactive and user-friendly.

## Setup Tools

### Initial Project Setup

```bash
# 1. Clone and setup the project
git clone <repository-url>
cd notification-microservice

# 2. Run initial setup script
./setup.sh
```

**What setup.sh does:**
- Creates project directory structure
- Initializes Python packages
- Sets up virtual environment using `uv`
- Configures git repository
- Provides next-step instructions

### Environment Configuration

```bash
# 1. Copy environment template
cp .env.example .env

# 2. Edit environment variables
nano .env
```

**Required Environment Variables:**
```env
# Database
DATABASE_URL=postgresql+asyncpg://notification_user:dev_password@localhost:5432/notification_service
POSTGRES_PASSWORD=dev_password

# Security
API_KEY_SALT=your-random-salt-string-change-in-production

# Providers (optional)
MSG91_API_KEY=your_msg91_api_key
MSG91_SENDER_ID=your_sender_id
```

### Database Setup

```bash
# 1. Ensure PostgreSQL is running
# For Docker users:
docker-compose up -d postgres

# 2. Run database migrations
alembic upgrade head

# 3. Verify migrations
alembic current
```

## Service Management

### Interactive Service Creation

The `create_service.py` tool provides a comprehensive interactive interface for creating services with webhooks.

```bash
python tools/create_service.py
```

**Interactive Flow:**
1. **Service Details**
   - Enter unique service name (spaces converted to underscores)
   - Optional description
   
2. **Webhook Configuration** (optional)
   - Add multiple webhook endpoints
   - Configure headers, events, retries
   - Set active/inactive status

3. **Review & Confirm**
   - Summary of configuration
   - Confirm to create

**Example Session:**
```
🚀 Notification Service - Interactive Service Creator
============================================================

📝 Service Details
----------------------------------------
Service name (unique identifier, no spaces): my_app
Service description: Production notification service for MyApp

📌 Webhook Configuration
----------------------------------------
Do you want to add webhooks? (Y/n): y

🔗 Webhook #1
Webhook URL: https://api.myapp.com/notifications/webhook
Description [Webhook endpoint #1]: Production webhook
Enable this webhook? (Y/n): y

Configure advanced options? (y/N): y
Add custom headers? (y/N): y
Enter custom headers (format: key=value, empty line to finish):
> X-Webhook-Secret=my-secret-key
> 

Available events: notification.sent, notification.delivered, notification.failed, notification.bounced
Events to subscribe (comma-separated, or 'all' for all events) [all]: all
Max retry attempts [3]: 5
Timeout in seconds [30]: 45

Add another webhook? (y/N): n

============================================================
📋 Service Configuration Summary
============================================================

🏷️  Name: my_app
📝 Description: Production notification service for MyApp

📌 Webhooks (1):
   1. https://api.myapp.com/notifications/webhook ✅

============================================================

Create this service? (Y/n): y

✅ Service created successfully!

============================================================
🎉 Service Created Successfully!
============================================================

🆔 Service ID: 53e80e3e-36b6-4518-88d7-474893a8b9eb
🔑 API Key: 53e80e3e36b6451888d7474893a8b9eb-7db6ecc86400431790df49a17596962a

⚠️  IMPORTANT: Save these credentials! The API key won't be shown again.

🔐 Authentication Headers:
   X-Service-Id: 53e80e3e-36b6-4518-88d7-474893a8b9eb
   X-API-Key: 53e80e3e36b6451888d7474893a8b9eb-7db6ecc86400431790df49a17596962a
```

### List All Services

```bash
python tools/create_service.py --list
```

**Output Example:**
```
📋 Existing Services (3):
--------------------------------------------------------------------------------

🏷️  my_app
   ID: 53e80e3e-36b6-4518-88d7-474893a8b9eb
   Active: ✅
   Created: 2024-01-15 10:30:00
   Webhooks: 2 active / 3 total
   Description: Production notification service for MyApp

🏷️  test_service
   ID: 12345678-1234-1234-1234-123456789012
   Active: ✅
   Created: 2024-01-14 15:20:00
   Webhooks: 1 active / 1 total
   Description: Testing environment service

🏷️  legacy_app
   ID: 87654321-4321-4321-4321-210987654321
   Active: ❌
   Created: 2023-12-01 08:00:00
   Webhooks: 0 active / 2 total

--------------------------------------------------------------------------------
```

### Reset API Key

```bash
python tools/create_service.py --reset-key
```

**Interactive Flow:**
1. Lists all available services
2. Select service by number
3. Confirm reset (warns about invalidating current key)
4. Displays new API key

**Example:**
```
🔑 Reset Service API Key
----------------------------------------

📋 Available Services:
1. my_app (ID: 53e80e3e-36b6-4518-88d7-474893a8b9eb)
2. test_service (ID: 12345678-1234-1234-1234-123456789012)
3. legacy_app (ID: 87654321-4321-4321-4321-210987654321)

Select service number (or 'q' to quit): 1

⚠️  You are about to reset the API key for: my_app
   This will invalidate the current API key!

Are you sure you want to continue? (y/N): y

============================================================
✅ API Key Reset Successfully!
============================================================

🏷️  Service: my_app
🆔 Service ID: 53e80e3e-36b6-4518-88d7-474893a8b9eb
🔑 New API Key: 53e80e3e36b6451888d7474893a8b9eb-a1b2c3d4e5f6789012345678901234567

⚠️  IMPORTANT: Save this API key! It won't be shown again.
```

### Quick Mock Service Setup

For development and testing, use the seed_service.py script:

```bash
# Create mock service with default webhooks
python tools/seed_service.py

# Update existing mock service webhooks
python tools/seed_service.py --update-webhooks
```

## Provider Management

### Interactive Provider Setup

```bash
python tools/seed_provider.py
```

**Features:**
- Pre-configured templates for common providers
- Custom provider configuration
- Update existing providers
- Validate configuration

**Example Session:**
```
🚀 Notification Service - Provider Seeder
============================================

Select an option:
1. Add MSG91 Provider
2. Add Twilio Provider (Coming Soon)
3. Add Mock Provider (for testing)
4. Add Custom Provider
5. List All Providers
6. Exit

Your choice: 1

Setting up MSG91 Provider
-------------------------
This provider already exists. Do you want to update it? (y/N): y

Supported notification types:
✓ sms
✓ email
✓ whatsapp

Is provider active? (Y/n): y
Provider priority (1-100) [1]: 1

MSG91 Configuration:
API Key (required): your-msg91-api-key
Sender ID [often]: MYAPP
DLT Template ID (optional): 
WhatsApp Template Namespace (optional): 

✅ Provider 'msg91' updated successfully!
```

### List Providers via API

```bash
# Requires authentication
curl -X GET http://localhost:8000/api/v1/providers \
  -H "X-Service-Id: YOUR_SERVICE_ID" \
  -H "X-API-Key: YOUR_API_KEY"
```

## Database Management

### Migration Commands

```bash
# Create a new migration
alembic revision -m "Add new feature"

# Apply all migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# View migration history
alembic history

# Show current migration
alembic current
```

### Database Inspection

```bash
# Connect to database
docker-compose exec postgres psql -U notification_user -d notification_service

# Or locally
psql postgresql://notification_user:dev_password@localhost:5432/notification_service
```

**Useful SQL Queries:**
```sql
-- Check service status
SELECT id, name, is_active, created_at 
FROM service_users 
ORDER BY created_at DESC;

-- View recent notifications
SELECT n.id, n.type, n.status, n.recipient, n.created_at, s.name as service
FROM notifications n
JOIN service_users s ON n.service_id = s.id
ORDER BY n.created_at DESC
LIMIT 10;

-- Check webhook delivery status
SELECT wd.*, w.url 
FROM webhook_deliveries wd
JOIN webhooks w ON wd.webhook_id = w.id
WHERE wd.status != 'acknowledged'
ORDER BY wd.created_at DESC;

-- Provider statistics
SELECT p.name, p.is_active,
  COUNT(DISTINCT n.id) as total_notifications,
  COUNT(DISTINCT CASE WHEN n.status = 'delivered' THEN n.id END) as delivered,
  COUNT(DISTINCT CASE WHEN n.status = 'failed' THEN n.id END) as failed
FROM providers p
LEFT JOIN notifications n ON n.provider_id = p.id
GROUP BY p.id, p.name, p.is_active;
```

## Testing Tools

### Test Email Sending

```bash
# Using the provided test script
./test_recipients_fix.sh

# Or manually
curl -X POST http://localhost:8000/api/v1/notifications/email \
  -H "Content-Type: application/json" \
  -H "X-Service-Id: YOUR_SERVICE_ID" \
  -H "X-API-Key: YOUR_API_KEY" \
  -d '{
    "to": ["test@example.com"],
    "subject": "Test Email",
    "body": "This is a test email",
    "html_body": "<h1>Test Email</h1><p>This is a test email</p>"
  }'
```

### Test SMS Sending

```bash
curl -X POST http://localhost:8000/api/v1/notifications/sms \
  -H "Content-Type: application/json" \
  -H "X-Service-Id: YOUR_SERVICE_ID" \
  -H "X-API-Key: YOUR_API_KEY" \
  -d '{
    "recipient": "+1234567890",
    "content": "Test SMS message",
    "priority": "high"
  }'
```

### Test Webhook Reception

```bash
# Start a local webhook receiver
python -m http.server 8001

# Or use the test script
python test_msg91_webhook.py
```

## Development Workflow

### 1. Initial Setup
```bash
# Clone and setup
git clone <repo>
cd notification-microservice
./setup.sh

# Configure environment
cp .env.example .env
# Edit .env with your settings

# Start services
docker-compose up -d
```

### 2. Database Setup
```bash
# Run migrations
docker-compose exec notification-service alembic upgrade head

# Seed providers
docker-compose exec notification-service python tools/seed_provider.py

# Create test service
docker-compose exec notification-service python tools/seed_service.py
```

### 3. Development Cycle
```bash
# Watch logs
docker-compose logs -f

# Run specific service
docker-compose up notification-service

# Restart after changes
docker-compose restart notification-service

# Access shell
docker-compose exec notification-service bash
```

### 4. Testing
```bash
# Use generated curl commands from seed_service.py
# Monitor Flower for task execution: http://localhost:5556
# Check webhook deliveries at webhook.site
```

## Production Deployment

### 1. Environment Preparation
```bash
# Use production environment file
cp .env.production .env

# Ensure secure values for:
# - API_KEY_SALT (use strong random string)
# - DATABASE_URL (production database)
# - Redis URLs (production Redis)
```

### 2. Database Setup
```bash
# Run migrations on production database
alembic upgrade head

# Create production providers
python tools/seed_provider.py

# Create production services
python tools/create_service.py
```

### 3. Docker Deployment
```bash
# Build production images
docker-compose -f docker-compose.yml -f docker-compose.prod.yml build

# Deploy with proper scaling
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d \
  --scale worker=3
```

### 4. Health Monitoring
```bash
# Check service health
curl http://your-domain.com/health

# Monitor worker status
curl http://your-domain.com/api/v1/stats/workers \
  -H "X-Service-Id: YOUR_SERVICE_ID" \
  -H "X-API-Key: YOUR_API_KEY"
```

### 5. Backup & Recovery
```bash
# Backup database
pg_dump -h localhost -U notification_user -d notification_service > backup.sql

# Backup service credentials
python tools/create_service.py --list > services_backup.txt
```

## Troubleshooting Commands

### Check Service Status
```bash
# Docker status
docker-compose ps

# Service logs
docker-compose logs notification-service
docker-compose logs celery-worker

# Database connection
docker-compose exec notification-service python -c "
from app.core.database import engine
import asyncio
asyncio.run(engine.connect())
print('Database connected!')
"
```

### Clear Queues
```bash
# Access Redis CLI
docker-compose exec redis redis-cli

# In Redis CLI:
# List all keys
KEYS *

# Clear specific queue
DEL celery

# Clear all
FLUSHALL
```

### Reset Failed Authentication
```bash
# Clear rate limit for a service
docker-compose exec redis redis-cli DEL "auth_failures:SERVICE_ID"
```

## Best Practices

1. **Always save API keys** when creating services - they cannot be retrieved later
2. **Use webhook.site** for testing webhooks before production endpoints
3. **Monitor Flower** (http://localhost:5556) during development
4. **Check logs** when notifications fail - they contain detailed error information
5. **Use the mock provider** for development to avoid external API calls
6. **Set appropriate priorities** for notifications based on urgency
7. **Configure webhook retries** based on endpoint reliability
8. **Regularly backup** service configurations and credentials
# Notification Microservice Architecture

## Table of Contents
- [System Overview](#system-overview)
- [Architecture Diagram](#architecture-diagram)
- [Core Components](#core-components)
- [Data Flow](#data-flow)
- [Database Schema](#database-schema)
- [Provider System](#provider-system)
- [Webhook System](#webhook-system)
- [Authentication & Security](#authentication--security)
- [Task Queue Architecture](#task-queue-architecture)
- [Deployment Architecture](#deployment-architecture)

## System Overview

The Notification Microservice is a scalable, provider-agnostic notification system built with:
- **FastAPI**: High-performance async web framework
- **PostgreSQL**: Primary database for persistent storage
- **Redis**: Message broker and caching layer
- **Celery**: Distributed task queue for async processing
- **Docker**: Containerization for easy deployment

### Key Design Principles
1. **Provider Agnostic**: Easy to add new notification providers
2. **Async First**: Non-blocking API with background processing
3. **Reliability**: Comprehensive retry mechanisms and failure handling
4. **Observability**: Detailed tracking of every notification attempt
5. **Multi-tenancy**: Service-based isolation with API key authentication

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                                   Client Applications                               │
│                        (Web Apps, Mobile Apps, Backend Services)                    │
└─────────────────────────────────────┬───────────────────────────────────────────────┘
                                      │ HTTPS
                                      │ API Key Auth
                                      ▼
┌────────────────────────────────────────────────────────────────────────────────────┐
│                              API Gateway (FastAPI)                                 │
│   ┌─────────────┐  ┌──────────────┐  ┌───────────────┐  ┌─────────────────────┐    │
│   │   Auth      │  │   Rate       │  │  Request      │  │    API              │    │
│   │ Middleware  │──│  Limiting    │──│  Validation   │──│  Endpoints          │    │
│   └─────────────┘  └──────────────┘  └───────────────┘  └─────────────────────┘    │
└─────────────────────────────────────┬──────────────────────────────────────────────┘
                                      │
                    ┌─────────────────┴─────────────────┐
                    │                                   │
                    ▼                                   ▼
┌──────────────────────────────┐    ┌──────────────────────────────┐
│       PostgreSQL             │    │            Redis             │
│  ┌─────────────────────┐     │    │   ┌──────────────────────┐   │
│  │ • notifications     │     │    │   │ • Task Queue         │   │
│  │ • service_users     │     │    │   │ • Result Backend     │   │
│  │ • providers         │     │    │   │ • Rate Limit Cache   │   │
│  │ • webhooks          │     │    │   │ • Dedup Cache        │   │
│  │ • webhook_deliveries│     │    │   └──────────────────────┘   │
│  │ • delivery_attempts │     │    └──────────────────────────────┘
│  └─────────────────────┘     │                    │
└──────────────────────────────┘                    │
                    │                               │
                    │                               ▼
                    │         ┌─────────────────────────────────────┐
                    │         │          Celery Workers             │
                    │         │  ┌──────────────────────────────┐   │
                    └─────────│  │ • send_notification_task     │   │
                              │  │ • retry_webhook              │   │
                              │  │ • mark_notification_failed   │   │
                              │  └──────────────────────────────┘   │
                              └───────────────┬─────────────────────┘
                                              │
                                              ▼
                    ┌───────────────────────────────────────────────┐
                    │              Provider Gateway                 │
                    │  ┌─────────┐  ┌─────────┐  ┌─────────────┐    │
                    │  │  MSG91  │  │  Mock   │  │   Future    │    │
                    │  │Provider │  │Provider │  │  Providers  │    │
                    │  └─────────┘  └─────────┘  └─────────────┘    │
                    └───────────────────────────────────────────────┘
                                              │
                                              ▼
                    ┌─────────────────────────────────────────────────┐
                    │         External Services & Recipients          │
                    │   (SMS Gateways, Email Servers, WhatsApp API)   │
                    └─────────────────────────────────────────────────┘
```

## Core Components

### 1. API Layer (FastAPI)
- **Location**: `/app/api/`
- **Responsibilities**:
  - Request validation and authentication
  - Rate limiting and request throttling
  - API versioning (v1)
  - Async request handling
  - OpenAPI documentation generation

### 2. Authentication Middleware
- **Location**: `/app/core/auth.py`
- **Features**:
  - API key-based authentication
  - Service ID validation
  - Failed attempt tracking
  - Rate limiting (20 failed attempts per 2 hours)

### 3. Business Logic Layer
- **Location**: `/app/services/`
- **Key Services**:
  - `NotificationService`: Core notification logic
  - Provider selection
  - Deduplication
  - Priority handling

### 4. Data Access Layer
- **Location**: `/app/repositories/`
- **Repositories**:
  - `NotificationRepository`: CRUD operations for notifications
  - `ProviderRepository`: Provider configuration management

### 5. Background Processing (Celery)
- **Location**: `/app/tasks/`
- **Task Types**:
  - Notification sending tasks
  - Webhook delivery tasks
  - Retry tasks

### 6. Provider System
- **Location**: `/app/providers/`
- **Architecture**:
  ```
  BaseProvider (Abstract)
       │
       ├── MSG91Provider
       ├── MockProvider
       └── FutureProviders...
  ```

## Data Flow

### 1. Notification Creation Flow
```
Client Request
    │
    ▼
API Authentication ──────► Rate Limit Check
    │                             │
    │ (Success)                   │ (Blocked)
    ▼                             ▼
Request Validation           Return 429
    │
    ▼
Deduplication Check ────────► Return Existing
    │                             │
    │ (New)                       │
    ▼                             │
Create DB Record                  │
    │                             │
    ▼                             │
Queue to Celery ◄─────────────────┘
    │
    ▼
Return Response
```

### 2. Notification Processing Flow
```
Celery Task Pickup
    │
    ▼
Load Notification ──────► Mark Failed (Not Found)
    │
    ▼
Select Provider ─────────► Use Default
    │                         │
    ▼                         ▼
Attempt Delivery ◄────────────┘
    │
    ├── Success ──► Update Status ──► Trigger Webhook
    │
    └── Failure ──► Retry Logic
                        │
                        ├── Retry Available ──► Schedule Retry
                        │
                        └── Max Retries ──► Mark Failed ──► Trigger Webhook
```

### 3. Webhook Delivery Flow
```
Notification Event
    │
    ▼
Load Active Webhooks
    │
    ▼
Immediate Attempt ─────────► Success ──► Mark Acknowledged
    │                             │
    │ (Failure)                   │
    ▼                             │
Check Status Code                 │
    │                             │
    ├── 4xx ──► Mark Failed ◄─────┘
    │
    └── 5xx/Timeout ──► Queue Retry
                            │
                            ▼
                      Exponential Backoff
                      (1min, 5min, 15min)
```

## Database Schema

### Core Tables

```sql
-- Service Users (Multi-tenancy)
service_users
├── id (UUID, PK)
├── name (String, Unique)
├── api_key_hash (String)
├── description (Text)
├── is_active (Boolean)
├── created_at (Timestamp)
└── updated_at (Timestamp)

-- Notifications
notifications
├── id (UUID, PK)
├── service_id (UUID, FK → service_users)
├── type (Enum: sms, email, whatsapp)
├── status (Enum: pending, queued, delivered, failed, cancelled)
├── priority (Enum: low, normal, high, instant)
├── recipient (String)
├── content (Text)
├── subject (String, nullable)
├── external_id (String, nullable)
├── retry_count (Integer)
├── task_id (String, nullable)
├── created_at (Timestamp)
├── delivered_at (Timestamp, nullable)
└── meta_data (JSONB)

-- Providers
providers
├── id (UUID, PK)
├── name (String, Unique)
├── supported_types (Array[String])
├── is_active (Boolean)
├── priority (Integer)
├── config (JSONB)
├── created_at (Timestamp)
└── updated_at (Timestamp)

-- Webhooks
webhooks
├── id (UUID, PK)
├── service_id (UUID, FK → service_users)
├── url (String)
├── description (Text)
├── is_active (Boolean)
├── headers (JSONB)
├── events (Array[String])
├── max_retries (Integer)
├── timeout_seconds (Integer)
├── created_at (Timestamp)
└── updated_at (Timestamp)

-- Webhook Deliveries
webhook_deliveries
├── id (UUID, PK)
├── webhook_id (UUID, FK → webhooks)
├── notification_id (UUID, FK → notifications)
├── status (Enum: pending, acknowledged, failed, retrying)
├── attempt_count (Integer)
├── task_id (String, nullable)
├── last_attempt_at (Timestamp)
├── acknowledged_at (Timestamp, nullable)
├── response_status_code (Integer, nullable)
├── response_body (Text, nullable)
├── error_message (Text, nullable)
└── created_at (Timestamp)

-- Delivery Attempts
delivery_attempts
├── id (UUID, PK)
├── notification_id (UUID, FK → notifications)
├── provider_id (UUID, FK → providers)
├── status (Enum: delivered, failed)
├── attempted_at (Timestamp)
├── response_data (JSONB)
├── error_message (Text, nullable)
└── created_at (Timestamp)
```

## Provider System

### Provider Interface
```python
class BaseProvider(ABC):
    @abstractmethod
    async def send_sms(self, message: SMSMessage) -> ProviderResponse
    
    @abstractmethod
    async def send_email(self, message: EmailMessage) -> ProviderResponse
    
    @abstractmethod
    async def send_whatsapp(self, message: WhatsAppMessage) -> ProviderResponse
```

### Provider Selection Algorithm
1. Check if specific provider requested
2. Filter providers by notification type support
3. Filter by active status
4. Sort by priority (ascending)
5. Select first matching provider

### Provider Configuration
Stored in database as JSONB:
```json
{
  "api_key": "encrypted_key",
  "sender_id": "MYAPP",
  "base_url": "https://api.provider.com",
  "timeout": 30,
  "retry_attempts": 3
}
```

## Webhook System

### Webhook Architecture
```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│ Notification    │────▶│ Webhook Manager  │────▶│ HTTP Client     │
│ Events          │     │                  │     │                 │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                                │                         │
                                ▼                         ▼
                        ┌──────────────────┐     ┌─────────────────┐
                        │ Retry Queue      │     │ Client Endpoint │
                        │ (Celery)         │     │                 │
                        └──────────────────┘     └─────────────────┘
```

### Webhook Events
- `notification.created`
- `notification.retry_scheduled`
- `notification.retry_attempted`
- `notification.delivered`
- `notification.failed`
- `notification.cancelled`

### Retry Strategy
- **Immediate**: First attempt synchronous
- **Backoff**: 1min → 5min → 15min
- **Max Attempts**: 4 (1 immediate + 3 retries)
- **Smart Retry**: Based on HTTP status codes

## Authentication & Security

### API Key Structure
```
{service_id}-{random_uuid}
Example: 53e80e3e36b6451888d7474893a8b9eb-7db6ecc86400431790df49a17596962a
```

### Security Features
1. **API Key Hashing**: Using SHA256 with salt
2. **Rate Limiting**: Per-service limits
3. **Service Isolation**: Data access restricted by service_id
4. **Failed Attempt Tracking**: Prevents brute force
5. **Request Validation**: Pydantic models for all inputs

## Task Queue Architecture

### Queue Configuration
```python
CELERY_TASK_ROUTES = {
    'notification.send': {'queue': 'notifications'},
    'webhook.deliver': {'queue': 'webhooks'},
    'notification.retry': {'queue': 'retries'}
}
```

### Priority Handling
- **instant**: Immediate processing, no delay
- **high**: Priority queue, processed first
- **normal**: Standard queue processing
- **low**: Processed when queues are idle

### Retry Configuration
```python
RETRY_DELAYS = [300, 900, 1800]  # 5min, 15min, 30min
WEBHOOK_RETRY_DELAYS = [60, 300, 900]  # 1min, 5min, 15min
```

## Deployment Architecture

### Container Structure
```
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│   nginx/proxy   │  │   API Server    │  │  Celery Worker  │
│   (Optional)    │  │   (FastAPI)     │  │  (Background)   │
└─────────────────┘  └─────────────────┘  └─────────────────┘
         │                    │                      │
         └────────────────────┴──────────────────────┘
                              │
         ┌────────────────────┴──────────────────────┐
         │                    │                      │
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│   PostgreSQL    │  │      Redis      │  │     Flower      │
│   (Database)    │  │  (Message Queue)│  │   (Monitoring)  │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

### Scaling Considerations
1. **API Servers**: Horizontally scalable behind load balancer
2. **Workers**: Scale based on queue depth
3. **Database**: Read replicas for queries
4. **Redis**: Redis Cluster for high availability
5. **Monitoring**: Centralized logging and metrics

### Health Checks
- **API**: `/health` endpoint checks DB and Redis
- **Workers**: Celery inspect for worker status
- **Database**: Connection pool monitoring
- **Redis**: PING command for availability
# Notification Microservice - Detailed Flows

## Table of Contents
- [Service Creation Flow](#service-creation-flow)
- [Notification Sending Flow](#notification-sending-flow)
- [Webhook Processing Flow](#webhook-processing-flow)
- [Provider Selection Flow](#provider-selection-flow)
- [Retry Mechanism Flow](#retry-mechanism-flow)
- [Authentication Flow](#authentication-flow)
- [MSG91 Integration Flow](#msg91-integration-flow)

## Service Creation Flow

### Interactive Service Creation (create_service.py)

```
START: python tools/create_service.py
    │
    ▼
1. Display Welcome Header
    │
    ▼
2. Collect Service Details
    ├── Service Name (required, spaces → underscores)
    └── Description (optional)
    │
    ▼
3. Webhook Configuration Decision
    ├── Yes → Continue to Webhook Setup
    └── No → Skip to Summary
    │
    ▼
4. For Each Webhook:
    ├── Collect URL (validate http/https)
    ├── Description (auto-generated if empty)
    ├── Active Status (default: true)
    └── Advanced Options?
        ├── No → Use defaults
        └── Yes → Configure:
            ├── Custom Headers (key=value pairs)
            ├── Event Filtering (default: all events)
            ├── Max Retries (default: 3)
            └── Timeout Seconds (default: 30)
    │
    ▼
5. Add Another Webhook?
    ├── Yes → Return to Step 4
    └── No → Continue
    │
    ▼
6. Display Configuration Summary
    ├── Service Name & Description
    └── All Webhooks with Status
    │
    ▼
7. Confirm Creation?
    ├── No → EXIT (Cancelled)
    └── Yes → Continue
    │
    ▼
8. Database Operations:
    ├── Check if service exists
    │   ├── Exists → ERROR: Service already exists
    │   └── Not Exists → Continue
    │
    ├── Create ServiceUser record
    │   ├── Generate UUID service_id
    │   ├── Generate API key: {service_id}-{random_uuid}
    │   ├── Hash API key with salt
    │   └── Save to database
    │
    └── Create Webhook records
        └── For each webhook config:
            ├── Generate webhook UUID
            ├── Link to service_id
            └── Save configuration
    │
    ▼
9. Display Success Output:
    ├── Service ID & API Key (⚠️ Save this!)
    ├── Authentication Headers
    └── Example curl commands
    │
    ▼
END: Service Created Successfully
```

### Quick Mock Service Creation (seed_service.py)

```
START: python tools/seed_service.py [--update-webhooks]
    │
    ▼
1. Check Command Arguments
    ├── --update-webhooks → Update existing webhooks
    └── No args → Create new service
    │
    ▼
2. Database Connection
    │
    ▼
3. For New Service:
    ├── Check if 'mock_service' exists
    │   ├── Exists → Display existing credentials
    │   └── Not Exists → Create new
    │
    └── Create Service:
        ├── Name: "mock_service"
        ├── Description: "Test service for development"
        ├── Generate credentials
        └── Create default webhooks:
            ├── https://webhook.site/{unique-id}
            └── http://localhost:8001/webhook
    │
    ▼
4. For Update Webhooks:
    ├── Load existing mock_service
    ├── Delete old webhooks
    └── Create new webhooks with fresh URLs
    │
    ▼
5. Display Output:
    ├── Service credentials
    ├── Webhook URLs
    └── Example API calls
    │
    ▼
END
```

## Notification Sending Flow

### API Request to Delivery

```
START: Client sends POST /api/v1/notifications/{type}
    │
    ▼
1. API Gateway Processing
    ├── Extract Headers (X-Service-Id, X-API-Key)
    ├── Parse Request Body
    └── Route to appropriate endpoint
    │
    ▼
2. Authentication Middleware (auth.py:52)
    ├── Validate Service ID format
    ├── Load ServiceUser from DB
    ├── Check service is_active
    ├── Verify API key hash
    └── Check rate limits
        ├── Success → Continue
        └── Failure → 
            ├── Increment failed attempts
            ├── Check if > 20 attempts in 2 hours
            └── Return 401/429
    │
    ▼
3. Request Validation (notifications.py)
    ├── Validate notification type
    ├── Validate recipient format
    ├── Validate content/body
    └── Set defaults (priority, dedup)
    │
    ▼
4. Deduplication Check
    ├── Skip if dedup=false
    └── Check Redis cache:
        Key: f"dedup:{service_id}:{type}:{recipient}:{content_hash}"
        TTL: 30 minutes
        ├── Found → Return existing notification
        └── Not Found → Continue
    │
    ▼
5. Provider Selection (notification_service.py:147)
    ├── Explicit provider_id?
    │   ├── Yes → Load specific provider
    │   └── No → Auto-select:
    │       ├── Filter by notification type
    │       ├── Filter by is_active
    │       ├── Sort by priority
    │       └── Select first match
    └── No provider → ERROR
    │
    ▼
6. Create Notification Record
    ├── Generate UUID
    ├── Status: PENDING
    ├── Link to service & provider
    ├── Set retry_count: 0
    └── Save to database
    │
    ▼
7. Queue to Celery (notification_service.py:201)
    ├── Task: send_notification_task
    ├── Queue: Based on priority
    │   ├── instant → high_priority queue
    │   ├── high → high_priority queue
    │   └── normal/low → default queue
    ├── Args: notification_id
    └── Store task_id in notification
    │
    ▼
8. Return API Response
    {
      "success": true,
      "status": "queued",
      "provider_name": "...",
      "notification_id": "..."
    }
    │
    ▼
9. Background Processing (notification_tasks.py:20)
    ├── Worker picks up task
    ├── Load notification from DB
    ├── Update status: QUEUED → SENDING
    └── Send webhook (created event)
    │
    ▼
10. Provider Delivery (providers/)
    ├── Load provider instance
    ├── Build provider-specific payload
    ├── Make API call
    └── Handle response:
        ├── Success → 
        │   ├── Update status: DELIVERED
        │   ├── Set external_id
        │   ├── Send webhook (delivered)
        │   └── Return success
        └── Failure →
            ├── Log attempt in delivery_attempts
            ├── Check retry_count < max_retries
            ├── Yes → Schedule retry
            └── No → Mark as FAILED
    │
    ▼
END: Notification Delivered/Failed
```

### Detailed Task Processing

```
send_notification_task(notification_id) - notification_tasks.py:20
    │
    ▼
1. Setup (Lines 24-31)
    ├── Get database session
    ├── Initialize variables
    └── Set task context
    │
    ▼
2. Load Notification (Lines 35-51)
    ├── Query by ID and service
    ├── Not found → Mark failed
    ├── Check status not already processed
    └── Load provider details
    │
    ▼
3. Check Cancellation (Lines 53-58)
    ├── Status == CANCELLED → Exit
    └── Continue processing
    │
    ▼
4. Update Status (Lines 60-65)
    ├── Set status: SENDING
    ├── Increment retry_count
    └── Save to database
    │
    ▼
5. Provider Delivery (Lines 70-95)
    ├── Get provider instance
    ├── Build message object
    ├── Call provider.send_{type}()
    └── Process response
    │
    ▼
6. Handle Success (Lines 100-115)
    ├── Update status: DELIVERED
    ├── Set delivered_at timestamp
    ├── Store external_id
    ├── Log delivery attempt
    └── Trigger webhook
    │
    ▼
7. Handle Failure (Lines 120-165)
    ├── Log failed attempt
    ├── Check retry logic:
    │   ├── retry_count >= max_retries → Mark FAILED
    │   └── retry_count < max_retries → Schedule retry
    │
    └── Retry Scheduling:
        ├── Calculate delay: [5min, 15min, 30min]
        ├── Create new task with countdown
        ├── Update task_id
        └── Send retry webhook
    │
    ▼
END
```

## Webhook Processing Flow

### Webhook Trigger Flow

```
Notification Event Occurs
    │
    ▼
1. Identify Event Type
    ├── created
    ├── retry_scheduled
    ├── retry_attempted  
    ├── delivered
    ├── failed
    └── cancelled
    │
    ▼
2. Load Active Webhooks (notification_service.py:250)
    SELECT * FROM webhooks 
    WHERE service_id = ? AND is_active = true
    │
    ▼
3. For Each Webhook:
    ├── Build Payload (notification_service.py:270)
    │   ├── Event details
    │   ├── Notification data
    │   ├── Timestamps
    │   └── Attempt counters
    │
    ├── Create/Update WebhookDelivery record
    │   ├── Status: PENDING
    │   ├── attempt_count: 0
    │   └── Link to notification
    │
    └── Immediate Delivery Attempt
        │
        ▼
4. HTTP Request (notification_service.py:315)
    ├── Method: POST
    ├── Headers:
    │   ├── Content-Type: application/json
    │   ├── X-Webhook-Event: {event}
    │   ├── X-Notification-Id: {id}
    │   ├── X-Service-Id: {service_id}
    │   ├── X-Webhook-Attempt: {attempt}
    │   └── + Custom headers from webhook config
    ├── Timeout: 30 seconds
    └── Body: JSON payload
    │
    ▼
5. Response Handling
    ├── 200-299 → Success
    │   ├── Update status: ACKNOWLEDGED
    │   ├── Set acknowledged_at
    │   └── Store response
    │
    ├── 400-499 → Client Error
    │   ├── Update status: FAILED
    │   ├── Don't retry
    │   └── Log error
    │
    └── 500-599/Timeout → Server Error
        ├── Queue retry task
        └── Continue to retry flow
    │
    ▼
END
```

### Webhook Retry Flow (webhook_tasks.py)

```
retry_webhook(webhook_delivery_id, retry_count) - webhook_tasks.py:25
    │
    ▼
1. Load Webhook Delivery (Lines 30-45)
    ├── Join with webhook & notification
    ├── Check exists
    └── Verify not already acknowledged
    │
    ▼
2. Check Retry Limit (Lines 47-55)
    ├── retry_count >= 3 → Mark FAILED
    └── Continue with retry
    │
    ▼
3. Build Request (Lines 60-90)
    ├── Reconstruct event payload
    ├── Set headers (attempt = retry_count + 2)
    └── Apply custom headers
    │
    ▼
4. Make HTTP Request (Lines 95-120)
    ├── Timeout: webhook.timeout_seconds
    ├── Capture response/error
    └── Update delivery record
    │
    ▼
5. Handle Response (Lines 125-165)
    ├── 200-299 → Mark ACKNOWLEDGED
    ├── 400-499 → Mark FAILED (no retry)
    └── 500+/Error → Schedule next retry
    │
    ▼
6. Schedule Next Retry (Lines 170-185)
    ├── Delays: [60s, 300s, 900s]
    ├── Create task with countdown
    └── Update task_id
    │
    ▼
END
```

## Provider Selection Flow

```
START: Need to select provider for notification
    │
    ▼
1. Check Explicit Provider (notification_service.py:140)
    ├── provider_id provided?
    │   ├── Yes → Load specific provider
    │   └── No → Continue to auto-select
    │
    ▼
2. Load All Providers
    SELECT * FROM providers
    WHERE is_active = true
    ORDER BY priority ASC
    │
    ▼
3. Filter by Notification Type
    For each provider:
    ├── Check if type in supported_types[]
    └── Keep only matching providers
    │
    ▼
4. Select First Match
    ├── Found → Use provider
    └── None → ERROR: No provider available
    │
    ▼
5. Initialize Provider Instance
    ├── Load provider class (registry.py)
    ├── Pass configuration
    └── Return instance
    │
    ▼
END: Provider selected
```

## Retry Mechanism Flow

### Notification Retry Logic

```
Delivery Failed
    │
    ▼
1. Check Retry Eligibility
    ├── retry_count >= max_retries (3)?
    │   ├── Yes → Mark as FAILED
    │   └── No → Continue
    │
    ▼
2. Calculate Retry Delay
    retry_count │ delay
    ───────────┼────────
         0     │ 5 min  (300s)
         1     │ 15 min (900s)
         2     │ 30 min (1800s)
    │
    ▼
3. Schedule Retry Task
    ├── Task: send_notification_task
    ├── Args: notification_id
    ├── Countdown: delay seconds
    └── Queue: Based on priority
    │
    ▼
4. Update Notification
    ├── Keep status as PENDING
    ├── Update task_id
    └── Save to database
    │
    ▼
5. Send Webhook Event
    ├── Event: retry_scheduled
    ├── Include next_attempt_at
    └── Include retry_count
    │
    ▼
END: Retry scheduled
```

### Webhook Retry Logic

```
Webhook Delivery Failed
    │
    ▼
1. Analyze HTTP Status
    ├── 2xx → Success (no retry)
    ├── 4xx → Client error (no retry)
    └── 5xx/Timeout → Server error (retry)
    │
    ▼
2. Check Retry Count
    ├── attempt_count >= 3?
    │   ├── Yes → Mark FAILED
    │   └── No → Continue
    │
    ▼
3. Calculate Backoff
    attempt │ delay
    ────────┼────────
       1    │ 1 min  (60s)
       2    │ 5 min  (300s)
       3    │ 15 min (900s)
    │
    ▼
4. Queue Retry Task
    ├── Task: retry_webhook
    ├── Args: (delivery_id, retry_count)
    └── Countdown: delay
    │
    ▼
END: Webhook retry queued
```

## Authentication Flow

```
START: API Request Received
    │
    ▼
1. Extract Headers (auth.py:52)
    ├── X-Service-Id
    └── X-API-Key
    │
    ▼
2. Validate Service ID
    ├── Check UUID format
    └── Invalid → 401 "Invalid service ID"
    │
    ▼
3. Load Service (auth.py:70)
    SELECT * FROM service_users
    WHERE id = ? AND is_active = true
    ├── Not found → 401 "Invalid credentials"
    └── Found → Continue
    │
    ▼
4. Check Rate Limit (auth.py:85)
    Redis Key: f"auth_failures:{service_id}"
    ├── Get failure count
    └── Count >= 20?
        ├── Yes → 429 "Too many attempts"
        └── No → Continue
    │
    ▼
5. Verify API Key (auth.py:95)
    ├── Hash provided key with salt
    ├── Compare with stored hash
    └── Match?
        ├── No → 
        │   ├── Increment failure count
        │   ├── Set 2-hour TTL
        │   └── Return 401
        └── Yes → 
            ├── Reset failure count
            └── Continue
    │
    ▼
6. Attach Service to Request
    request.state.service = service
    │
    ▼
END: Authentication successful
```

## MSG91 Integration Flow

### Outbound SMS via MSG91

```
START: Send SMS via MSG91Provider
    │
    ▼
1. Prepare Request (msg91_provider.py:50)
    ├── Endpoint: /api/v5/flow/
    ├── Headers:
    │   ├── authkey: {api_key}
    │   └── Content-Type: application/json
    └── Body:
        {
          "template_id": "...",
          "recipients": [{
            "mobiles": "91..."
          }]
        }
    │
    ▼
2. Make API Call
    ├── Timeout: 30 seconds
    ├── Retry: 3 attempts
    └── Exponential backoff
    │
    ▼
3. Handle Response
    ├── Success (200) →
    │   ├── Extract request_id
    │   ├── Status: delivered
    │   └── Return success
    └── Failure →
        ├── Parse error message
        └── Return failure
    │
    ▼
END
```

### MSG91 Webhook Reception

```
START: POST /api/v1/msg91/webhook
    │
    ▼
1. Parse Webhook Data (msg91/webhooks.py:30)
    ├── Extract event type
    ├── Extract message details
    └── Validate required fields
    │
    ▼
2. Find Notification
    SELECT * FROM notifications
    WHERE external_id = ?
    ├── Not found → Log and ignore
    └── Found → Continue
    │
    ▼
3. Process Event Status
    ├── "DLR" → Delivered
    ├── "FAILED" → Failed
    ├── "CLICK" → Clicked
    └── Other → Log only
    │
    ▼
4. Update Notification
    ├── Update status
    ├── Add delivery timestamp
    └── Store provider response
    │
    ▼
5. Trigger Internal Webhooks
    └── Send event to service webhooks
    │
    ▼
END: Return 200 OK
```

## Complete Example: SMS Notification Journey

```
1. Client Request
   POST /api/v1/notifications/sms
   Headers: X-Service-Id: abc-123, X-API-Key: secret
   Body: {"recipient": "+1234567890", "content": "Hello"}
        │
        ▼
2. Authentication
   → Validate service & API key
   → Check rate limits
        │
        ▼
3. Create Notification
   → ID: notif-789
   → Status: PENDING
   → Provider: msg91
        │
        ▼
4. Queue Task
   → Task ID: task-456
   → Queue: high_priority
        │
        ▼
5. API Response
   → {"notification_id": "notif-789", "status": "queued"}
        │
        ▼
6. Worker Processing (async)
   → Pick up task-456
   → Load notification
   → Send via MSG91
        │
        ▼
7. MSG91 API Call
   → POST https://api.msg91.com/api/v5/flow/
   → Response: {"request_id": "msg91-123"}
        │
        ▼
8. Update Notification
   → Status: DELIVERED
   → external_id: msg91-123
        │
        ▼
9. Webhook Delivery
   → POST https://client.com/webhook
   → Event: notification.delivered
        │
        ▼
10. Client Webhook Response
    → 200 OK
    → Webhook marked ACKNOWLEDGED
        │
        ▼
END: SMS successfully delivered and client notified
```
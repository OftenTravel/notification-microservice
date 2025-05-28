# Email Template Curl Requests

## 1. Full Request with All Template Variables

```bash
curl -X POST "http://localhost:8000/api/v1/notifications/email?priority=high" \
  -H "Content-Type: application/json" \
  -H "X-Service-Id: 032fa6b8-03ba-4311-9e83-2a36d6e9a288" \
  -H "X-API-Key: 032fa6b803ba43119e832a36d6e9a288-5ed7680755fa4833841735c0c0a79a72" \
  -d '{
    "provider_id": "7081cd11-eb45-4279-9f99-9e44190e41d6",
    "to": ["sarvesh@mcp.travel"],
    "subject": "Welcome to Often!",
    "body": "",
    "html_body": " ",
    "from_email": "contact@o84nhii.mailer91.com",
    "from_name": "Often",
    "template_id": "38257",
    "meta_data": {
      "BRAND_NAME": "Often",
      "USER_NAME": "Sarvesh",
      "NOTIFICATION_TITLE": "Your Account is Ready!",
      "NOTIFICATION_MESSAGE": "Welcome to Often! Your account has been successfully created and you can now start using our platform.",
      "NOTIFICATION_DATE": "May 27, 2025 at 2:30 PM",
      "REFERENCE_ID": "REF-2025-0527-001",
      "ACTION_URL": "https://often.com/get-started",
      "ACTION_TEXT": "Get Started",
      "SUPPORT_EMAIL": "support@often.com",
      "SUPPORT_PHONE": "+1 (555) 123-4567",
      "WEBSITE_URL": "https://often.com",
      "COMPANY_ADDRESS": "123 Business St, Suite 100, San Francisco, CA 94105",
      "UNSUBSCRIBE_URL": "https://often.com/unsubscribe",
      "PRIVACY_URL": "https://often.com/privacy"
    }
  }'
```

## 2. Minimal Request to Test Auto-Completion

```bash
curl -X POST "http://localhost:8000/api/v1/notifications/email?priority=high" \
  -H "Content-Type: application/json" \
  -H "X-Service-Id: 032fa6b8-03ba-4311-9e83-2a36d6e9a288" \
  -H "X-API-Key: 032fa6b803ba43119e832a36d6e9a288-5ed7680755fa4833841735c0c0a79a72" \
  -d '{
    "provider_id": "7081cd11-eb45-4279-9f99-9e44190e41d6",
    "to": ["sarvesh@mcp.travel"],
    "subject": "Welcome to Often!",
    "body": "",
    "html_body": " ",
    "template_id": "38257",
    "meta_data": {
      "BRAND_NAME": "Often",
      "USER_NAME": "Sarvesh",
      "NOTIFICATION_TITLE": "Test Notification",
      "NOTIFICATION_MESSAGE": "This is a test email with minimal data."
    }
  }'
```

## 3. Alternative Format Using Recipients Array (MSG91 Native Format)

```bash
curl -X POST "http://localhost:8000/api/v1/notifications/email?priority=high" \
  -H "Content-Type: application/json" \
  -H "X-Service-Id: 032fa6b8-03ba-4311-9e83-2a36d6e9a288" \
  -H "X-API-Key: 032fa6b803ba43119e832a36d6e9a288-5ed7680755fa4833841735c0c0a79a72" \
  -d '{
    "provider_id": "7081cd11-eb45-4279-9f99-9e44190e41d6",
    "recipients": [
      {
        "to": [
          {
            "email": "sarvesh@mcp.travel",
            "name": "Sarvesh"
          }
        ],
        "variables": {
          "BRAND_NAME": "Often",
          "USER_NAME": "Sarvesh",
          "NOTIFICATION_TITLE": "Your Account is Ready!",
          "NOTIFICATION_MESSAGE": "Welcome to Often! Your account has been successfully created.",
          "NOTIFICATION_DATE": "May 27, 2025 at 2:30 PM",
          "REFERENCE_ID": "REF-2025-0527-001",
          "ACTION_URL": "https://often.com/get-started",
          "ACTION_TEXT": "Get Started",
          "SUPPORT_EMAIL": "support@often.com",
          "SUPPORT_PHONE": "+1 (555) 123-4567",
          "WEBSITE_URL": "https://often.com",
          "COMPANY_ADDRESS": "123 Business St, Suite 100, San Francisco, CA 94105",
          "UNSUBSCRIBE_URL": "https://often.com/unsubscribe",
          "PRIVACY_URL": "https://often.com/privacy"
        }
      }
    ],
    "subject": "Welcome to Often!",
    "body": "",
    "html_body": " ",
    "from_email": "contact@o84nhii.mailer91.com",
    "from_name": "Often",
    "template_id": "38257"
  }'
```

## Notes:

1. **Priority Parameter**: The priority should be passed as a query parameter:
   ```
   http://localhost:8000/api/v1/notifications/email?priority=high
   ```

2. **Provider Configuration** (from database):
   - Provider ID: `7081cd11-eb45-4279-9f99-9e44190e41d6`
   - Default from_email: `contact@o84nhii.mailer91.com`
   - Default from_name: `Often`
   - Domain: `84nhii.mailer91.com`

3. **Template Info**:
   - Template Version ID: `38257`
   - Template Slug: `test_html_template_onboarding`

4. **Important Changes**:
   - `template_id` is now at the root level of the request body (not in meta_data)
   - Template variables go in `meta_data` for simple format
   - Template variables go in `recipients[].variables` for native MSG91 format

The system should save the notification details in the notification table and deliver the email using MSG91.
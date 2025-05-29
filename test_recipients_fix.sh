#!/bin/bash

# Test with both to and recipients fields
curl -X 'POST' \
  'http://localhost:8000/api/v1/notifications/email?priority=HIGH' \
  -H 'accept: application/json' \
  -H 'X-Service-Id: 6dddbf0e-d6ab-4539-a0a0-9f5c26f81c2b' \
  -H 'X-API-Key: 6dddbf0ed6ab4539a0a09f5c26f81c2b-ad61a34f6b1a4e01bf3ee5fc4bf0de07' \
  -H 'Content-Type: application/json' \
  -d '{
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
        "VAR1": "John",
        "VAR2": "12345"
      }
    }
  ],
  "subject": "Test Recipients Fix",
  "body": "",
  "html_body": "Test email with recipients",
  "from_email": "contact@84nhii.mailer91.com",
  "from_name": "Often",
  "cc": [],
  "bcc": [],
  "template_id": "often_onboarding",
  "domain": "84nhii.mailer91.com"
}'
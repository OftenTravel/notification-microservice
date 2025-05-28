#!/bin/bash

# Test with both to and recipients fields
curl -X 'POST' \
  'http://localhost:8000/api/v1/notifications/email?priority=HIGH' \
  -H 'accept: application/json' \
  -H 'X-Service-Id: 032fa6b8-03ba-4311-9e83-2a36d6e9a288' \
  -H 'X-API-Key: 032fa6b803ba43119e832a36d6e9a288-5ed7680755fa4833841735c0c0a79a72' \
  -H 'Content-Type: application/json' \
  -d '{
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
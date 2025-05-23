# Notification Microservice

A flexible and scalable notification service that supports multiple delivery providers (email, SMS, push notifications, etc.).

## Overview

This microservice handles the delivery of notifications through various channels. It provides a unified API for sending notifications while abstracting away the complexity of individual provider implementations.

## Prerequisites

- Node.js (v14 or higher)
- npm or yarn
- MongoDB (for notification storage and tracking)
- Redis (optional, for rate limiting and caching)

## Installation

1. Clone the repository:
  ```
  git clone https://github.com/yourusername/notification-microservice.git
  cd notification-microservice
  ```

2. Install dependencies:
  ```
  npm install
  ```

3. Create a `.env` file based on the `.env.example` template:
  ```
  cp .env.example .env
  ```

4. Configure your environment variables in the `.env` file.

## Configuration

Edit the `.env` file to configure:

- Database connection
- Default notification providers
- Provider API keys and credentials
- Service port and environment

## Running the Service

### Development Mode

```
npm run dev
```

### Production Mode

```
npm run build
npm start
```

## Adding a New Notification Provider

### 1. Create Provider Implementation

Create a new file in the `src/providers` directory:

```javascript
// src/providers/new-provider.js
const { BaseProvider } = require('./base-provider');

class NewProvider extends BaseProvider {
  constructor(config) {
   super('new-provider');
   this.config = config;
  }

  async send(notification) {
   // Implementation for sending notification
   try {
    // Provider-specific logic
    // e.g., API call to the provider service
    
    return {
      success: true,
      providerResponseId: 'response-id',
    };
   } catch (error) {
    return {
      success: false,
      error: error.message,
    };
   }
  }
}

module.exports = { NewProvider };
```

### 2. Register the Provider

Add your new provider to the provider registry in `src/providers/index.js`:

```javascript
const { EmailProvider } = require('./email-provider');
const { SmsProvider } = require('./sms-provider');
const { NewProvider } = require('./new-provider');

const providerRegistry = {
  email: EmailProvider,
  sms: SmsProvider,
  'new-provider': NewProvider,
};

module.exports = { providerRegistry };
```

### 3. Configure the Provider

Add configuration for your provider in your `.env` file:

```
NEW_PROVIDER_API_KEY=your_api_key
NEW_PROVIDER_SECRET=your_secret
```

Add the provider configuration to `src/config/providers.js`:

```javascript
module.exports = {
  email: {
   // Email provider config
  },
  sms: {
   // SMS provider config
  },
  'new-provider': {
   apiKey: process.env.NEW_PROVIDER_API_KEY,
   secret: process.env.NEW_PROVIDER_SECRET,
   // Other provider-specific config
  }
};
```

### 4. Using the New Provider

You can now use your provider when sending notifications:

```javascript
const notificationService = require('./services/notification');

await notificationService.send({
  provider: 'new-provider',
  to: 'recipient-id',
  content: {
   // Provider-specific content structure
  }
});
```

## API Documentation

### Send Notification

```
POST /api/notifications

{
  "provider": "email",
  "to": "user@example.com",
  "content": {
   "subject": "Hello",
   "body": "World"
  },
  "priority": "high",
  "metadata": {
   "category": "welcome"
  }
}
```

For more API endpoints and detailed documentation, see [API_DOCS.md](API_DOCS.md).
## Project Structure

```
notification-microservice/
├── app/
│   ├── core/
│   │   ├── __init__.py
│   │   └── exceptions.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── messages.py
│   │   ├── responses.py
│   │   └── api.py
│   ├── providers/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── mock_provider.py
│   │   └── registry.py
│   ├── services/
│   │   ├── __init__.py
│   │   └── notification_service.py
│   ├── tests/
│   │   ├── __init__.py
│   │   └── test_mock_provider.py
│   └── main.py
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── run_api.py
└── README.md
```

<!-- docs\API_REFERENCE.md -->
# NakshatraAI API - Quick Start Guide

## Overview

RESTful API for the NakshatraAI astrology chatbot. Built with FastAPI, supports both Vedic and Western astrology.

## Features

- ✅ **Chat Endpoint** - Conversational astrology queries
- ✅ **User Management** - Profile and birth data CRUD
- ✅ **Chart Calculations** - Real-time birth chart generation
- ✅ **API Key Authentication** - Secure access control
- ✅ **Rate Limiting** - 10 requests/minute per API key
- ✅ **Auto Documentation** - Swagger UI and ReDoc
- ✅ **Docker Support** - Containerized deployment

## Quick Start

### 1. Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env

# Edit .env and configure:
# 1. Add your Gemini or OpenAI API key
# 2. Set your custom API keys (any string you choose)

# Example .env:
# GOOGLE_API_KEY=AIzaSy...your-gemini-key
# VALID_API_KEYS=my-dev-key-123
# LLM_PROVIDER=gemini

# Run server
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

# API docs available at:
# http://localhost:8000/api/docs
```

### 2. Docker Deployment

```bash
# Edit .env file first (see above)

# Run container with docker-compose
docker-compose up -d

# View logs
docker-compose logs -f
```

## Authentication

**IMPORTANT:** The "X-API-Key" is just an HTTP header name (industry standard).  
It is **NOT** related to Twitter/X API.

### How It Works

1. **You create your own API keys** (any string):
   - Examples: `my-secret-key`, `dev-key-123`, `prod-api-key-xyz`
   
2. **Add them to .env file**:
   ```env
   VALID_API_KEYS=key1,key2,key3
   ```

3. **Clients send the key in request header**:
   ```bash
   curl -H "X-API-Key: key1" http://localhost:8000/api/v1/chat
   ```

### LLM Configuration

You need **ONE** of these options:

#### Option 1: Google Cloud (Vertex AI) - Recommended

1. Create service account in [Google Cloud Console](https://console.cloud.google.com)
2. Enable Vertex AI API
3. Download service account JSON key file

```env
GOOGLE_CREDENTIALS_PATH=/path/to/service-account-key.json
GOOGLE_PROJECT_ID=your-project-id
GOOGLE_LOCATION=us-central1
LLM_PROVIDER=google
LLM_MODEL=gemini-2.0-flash-exp
```

#### Option 2: OpenAI

Get API key from [OpenAI Platform](https://platform.openai.com/api-keys)

```env
OPENAI_API_KEY=sk-your-openai-key
LLM_PROVIDER=openai
LLM_MODEL=gpt-4
```

### Health Check
```bash
GET /api/v1/health
```

### Chat
```bash
POST /api/v1/chat
Headers: X-API-Key: your-api-key
Body:
{
  "query": "When will I get married?",
  "user_id": "user123",
  "conversation_history": [],
  "include_chart_data": false
}
```

### User Management
```bash
# Get user
GET /api/v1/user/{user_id}
Headers: X-API-Key: your-api-key

# Create user
POST /api/v1/user
Headers: X-API-Key: your-api-key
Body: { UserProfile }

# Update user
PUT /api/v1/user/{user_id}
Headers: X-API-Key: your-api-key
Body: { UserUpdate }
```

### Chat (Backend Integration) — Correct Protocol

> ⚠️ **Important:** The chatbot uses a **2-step protocol**.  
> You MUST call `/initialize` once before `/message` for every new user.
> Subsequent calls to `/initialize` for the same user are safely ignored, as Redis session data is now persistent.

---

#### Step 1 — Initialize Session

**Endpoint:** `POST /api/v1/chat/initialize`

```json
{
  "user_id": "unique-user-or-session-id",
  "user_profile": {
    "user_id": "unique-user-or-session-id",
    "name": "Arjun Sharma",
    "date_of_birth": "1990-05-15",
    "time_of_birth": "14:30:00",
    "place_of_birth": "New Delhi, India",
    "latitude": 28.6139,
    "longitude": 77.2090,
    "timezone": "Asia/Kolkata",
    "preferred_system": "vedic"
  },
  "conversation_history": []
}
```

> `conversation_history` is a list of `{ "question": "...", "answer": "...", "source": "external", "timestamp": "..." }` objects.  
> Pass previous messages here if resuming a conversation; pass `[]` for new sessions.

**Response (Success):**
```json
{
  "user_id": "unique-user-or-session-id",
  "status": "success"
}
```

**Response (Already Initialized):**
```json
{
  "user_id": "unique-user-or-session-id",
  "status": "already_initialized"
}
```
*(Indicates the user's permanent session is active and no data was overwritten)*

---

#### Step 2 — Send Message

**Endpoint:** `POST /api/v1/chat/message`

```json
{
  "user_id": "unique-user-or-session-id",
  "question": "When will I get married?"
}
```

> ❗ `user_id` here MUST be identical to the one used in `/initialize`.

**Response:**
```json
{
  "user_id": "unique-user-or-session-id",
  "question": "When will I get married?",
  "answer": "Based on your birth chart...",
  "source": "openai"
}
```

---

#### Field Name Reference (CRITICAL — Do Not Mix Up)

| Correct field name | Wrong / old name | Used in |
|---|---|---|
| `date_of_birth` | `birth_date` | `user_profile` in `/initialize` |
| `time_of_birth` | `birth_time` | `user_profile` in `/initialize` |
| `preferred_system` | `astrology_system` | `user_profile` in `/initialize` |
| `place_of_birth` | *(was missing)* | `user_profile` in `/initialize` |
| `question` | `message` | `/message` request body |
| `user_id` | `session_id` | both endpoints |



### Chart Calculation
```bash
POST /api/v1/calculate/chart
Headers: X-API-Key: your-api-key
Body:
{
  "date_of_birth": "1990-03-15",
  "time_of_birth": "14:30:00",
  "latitude": 26.9124,
  "longitude": 75.7873,
  "timezone": "Asia/Kolkata",
  "system": "vedic"
}
```

---

## Authentication

### 1. Public API Keys
All public endpoints require `X-API-Key` authentication.

**Header:** `X-API-Key: your-api-key`

Configure valid API keys in `.env`:
```env
VALID_API_KEYS=key1,key2,key3
```

### 2. Internal Service Secret
The backend integration endpoint uses a high-security shared secret.

**Header:** `X-Internal-Service: your-shared-secret`

Configure this in `.env`:
```env
INTERNAL_SERVICE_SECRET=super-secret-123
```

## Redis Session Management

The backend integration endpoint utilizes Redis for:
- **24-Hour Expiry**: Conversation history is automatically cleared after 24 hours of inactivity.
- **20 Message Limit**: Only the last 20 messages are kept for context to maintain performance.
- **Context Persistence**: User birth details are cached per session.

## Rate Limiting

- **10 requests/minute** per API key
- **100 requests/hour** per API key

Rate limit headers returned in response:
- `X-RateLimit-Limit`
- `X-RateLimit-Remaining`
- `X-RateLimit-Reset`

## Response Format

### Success Response
```json
{
  "answer": "Based on your 7th house...",
  "intent": "NEEDS_RAG",
  "confidence": 0.85,
  "processing_time": 1.23,
  "query_analysis": {
    "category": "general",
    "sensitivity_level": 0.0,
    "handling_strategy": "proceed_normal"
  },
  "timestamp": "2026-02-02T14:00:00Z"
}
```

### Error Response
```json
{
  "error": "Invalid request",
  "details": "Missing required field",
  "timestamp": "2026-02-02T14:00:00Z",
  "path": "/api/v1/chat"
}
```

## Testing

```bash
# Run health check
curl http://localhost:8000/api/v1/health

# Test chat endpoint
curl -X POST http://localhost:8000/api/v1/chat \
  -H "X-API-Key: test-key" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is my sun sign?",
    "user_id": "test_user"
  }'
```

## Documentation

- **Swagger UI:** http://localhost:8000/api/docs
- **ReDoc:** http://localhost:8000/api/redoc
- **OpenAPI JSON:** http://localhost:8000/api/openapi.json

## Configuration

See `.env.example` for all configuration options:

- `DEBUG` - Enable debug mode
- `HOST` - Server host (default: 0.0.0.0)
- `PORT` - Server port (default: 8000)
- `VALID_API_KEYS` - Comma-separated API keys
- `ALLOWED_ORIGINS` - CORS allowed origins
- `RATE_LIMIT_PER_MINUTE` - Rate limit threshold
- `GOOGLE_API_KEY` - Gemini API key
- `LLM_PROVIDER` - LLM provider (gemini/openai)
- `MONGODB_URI` - MongoDB connection string
- `USE_DUMMY_USER_DB` - Use in-memory user DB (true/false)

## Production Deployment

1. **Set environment variables**
   - Disable DEBUG mode
   - Set strong API keys
   - Restrict CORS origins
   - Configure MongoDB URI

2. **Use Docker**
   ```bash
   docker-compose up -d
   ```

3. **Enable HTTPS** (use reverse proxy like Nginx)

4. **Monitor** with health check endpoint

## Support

For issues or questions, refer to the project documentation.

<!-- docs/API_REFERENCE.md -->
# NakshatraAI — API Reference

> **Last Updated:** March 2026
> **Base URL:** `http://localhost:8000` (local) or your deployed host

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Authentication](#authentication)
3. [Endpoints](#endpoints)
   - [Health Check](#health-check)
   - [Chat — Initialize Session](#chat--initialize-session)
   - [Chat — Send Message](#chat--send-message)
   - [Chart Calculation](#chart-calculation)
   - [User Management](#user-management)
4. [Field Name Reference](#field-name-reference-critical--do-not-mix-up)
5. [Rate Limiting](#rate-limiting)
6. [Response Format](#response-format)
7. [Redis Session Behavior](#redis-session-behavior)
8. [Error Codes](#error-codes)
9. [Configuration Reference](#configuration-reference)

---

## Quick Start

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Set at minimum:
#   OPENAI_API_KEY=sk-...
#   VALID_API_KEYS=my-dev-key

# Start Redis and API server
redis-server &
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

# Interactive docs:
# http://localhost:8000/api/docs   (Swagger UI)
# http://localhost:8000/api/redoc  (ReDoc)
```

### Docker

```bash
# Edit .env first, then:
docker-compose up -d
docker-compose logs -f api
```

---

## Authentication

### Public API Keys

All endpoints require an `X-API-Key` header.

> **Note:** "X-API-Key" is a standard HTTP header name — it is not related to the Twitter/X API.

**You create your own keys** (any string), add them to `.env`, and clients send them in headers:

```env
VALID_API_KEYS=my-dev-key,prod-key-xyz,mobile-app-key
```

```bash
curl -H "X-API-Key: my-dev-key" http://localhost:8000/api/v1/health
```

### Internal Service Secret

Backend-to-backend calls (server → NakshatraAI) use an additional high-security header:

**Header:** `X-Internal-Service: your-shared-secret`

```env
INTERNAL_SERVICE_SECRET=super-secret-string
```

### LLM Configuration

**Option 1 — OpenAI (recommended)**

```env
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
OPENAI_API_KEY=sk-your-openai-key
```

**Option 2 — Ollama (local, free)**

```env
LLM_PROVIDER=ollama
LLM_MODEL=qwen2.5:7b
```

---

## Endpoints

### Health Check

```
GET /health
GET /api/v1/health
```

No authentication required.

**Response:**
```json
{
  "status": "healthy",
  "version": "2.0.0"
}
```

---

### Chat — Backend Integration: Correct Protocol

> **Important:** The chatbot uses a **2-step protocol**.
> You MUST call `/initialize` once before calling `/message` for each new user.
> Subsequent `/initialize` calls for the same user are safely ignored — no data is overwritten.

---

#### Step 1 — Initialize Session

**Endpoint:** `POST /api/v1/chat/initialize`

**Headers:**
```
X-API-Key: your-api-key
Content-Type: application/json
```

**Request Body:**
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

`conversation_history` is a list of `{ "question": "...", "answer": "...", "source": "external", "timestamp": "..." }` objects.
Pass prior messages when resuming a conversation; pass `[]` for new sessions.

**Response (new session):**
```json
{
  "user_id": "unique-user-or-session-id",
  "status": "success"
}
```

**Response (session already exists):**
```json
{
  "user_id": "unique-user-or-session-id",
  "status": "already_initialized"
}
```

---

#### Step 2 — Send Message

**Endpoint:** `POST /api/v1/chat/message`

**Headers:**
```
X-API-Key: your-api-key
Content-Type: application/json
```

**Request Body:**
```json
{
  "user_id": "unique-user-or-session-id",
  "question": "When will my career improve?"
}
```

> The `user_id` must exactly match the one used in `/initialize`.

**Response:**
```json
{
  "user_id": "unique-user-or-session-id",
  "question": "When will my career improve?",
  "answer": "Based on your birth chart, your current Jupiter Mahadasha suggests...",
  "source": "openai"
}
```

---

### Chart Calculation

Calculate a birth chart on demand (independent of chat session).

**Endpoint:** `POST /api/v1/calculate/chart`

**Headers:**
```
X-API-Key: your-api-key
Content-Type: application/json
```

**Request Body:**
```json
{
  "date_of_birth": "1990-03-15",
  "time_of_birth": "14:30:00",
  "latitude": 26.9124,
  "longitude": 75.7873,
  "timezone": "Asia/Kolkata",
  "system": "vedic"
}
```

| Field | Type | Values | Description |
|---|---|---|---|
| `date_of_birth` | string | `YYYY-MM-DD` | Birth date |
| `time_of_birth` | string | `HH:MM:SS` | Birth time (24h) |
| `latitude` | float | -90 to 90 | Birth place latitude |
| `longitude` | float | -180 to 180 | Birth place longitude |
| `timezone` | string | IANA tz name | e.g. `Asia/Kolkata` |
| `system` | string | `vedic`, `western` | Astrology system |

**Response:** Full chart data including houses, planetary positions, aspects, and dashas.

---

### User Management

```bash
# Get user profile
GET /api/v1/user/{user_id}
X-API-Key: your-api-key

# Create user
POST /api/v1/user
X-API-Key: your-api-key
Body: { UserProfile }

# Update user
PUT /api/v1/user/{user_id}
X-API-Key: your-api-key
Body: { UserUpdate }
```

---

## Field Name Reference (CRITICAL — Do Not Mix Up)

| Correct field name | Wrong / old name | Used in |
|---|---|---|
| `date_of_birth` | `birth_date` | `user_profile` in `/initialize` |
| `time_of_birth` | `birth_time` | `user_profile` in `/initialize` |
| `preferred_system` | `astrology_system` | `user_profile` in `/initialize` |
| `place_of_birth` | *(was missing)* | `user_profile` in `/initialize` |
| `question` | `message` | `/message` request body |
| `user_id` | `session_id` | both endpoints |

---

## Rate Limiting

- **10 requests/minute** per API key

Rate limit headers returned in every response:
- `X-RateLimit-Limit` — requests allowed per window
- `X-RateLimit-Remaining` — requests remaining this window
- `X-RateLimit-Reset` — epoch timestamp when window resets

On exceeding the limit, the server returns `HTTP 429 Too Many Requests`.

---

## Response Format

### Success (chat message)
```json
{
  "user_id": "unique-user-or-session-id",
  "question": "When will I get married?",
  "answer": "Based on your 7th house...",
  "source": "openai"
}
```

### Success (full response with metadata)
```json
{
  "answer": "Based on your 7th house...",
  "intent": "RAG_WITH_CALCULATION",
  "confidence": 0.85,
  "processing_time": 1.23,
  "query_analysis": {
    "category": "marriage",
    "sensitivity_level": 0.0,
    "handling_strategy": "proceed_normal"
  },
  "timestamp": "2026-03-10T14:00:00Z"
}
```

### Error
```json
{
  "error": "Invalid request",
  "details": "Missing required field: user_id",
  "timestamp": "2026-03-10T14:00:00Z",
  "path": "/api/v1/chat/message"
}
```

---

## Redis Session Behavior

| Data | Storage | Policy |
|---|---|---|
| User Profile | Redis (permanent) | No TTL — never expires |
| Birth Chart | Redis (permanent) | No TTL — birth geometry never changes |
| Conversation History | Redis (permanent) | Sliding window of last **10** messages |
| Transits | Redis | Refreshed when `stored_at` is older than `TRANSIT_REFRESH_HOURS` (default: 24h) |
| Dashas | Redis | Refreshed when `stored_at` is older than `DASHA_REFRESH_DAYS` (default: 30d) |

All user data persists indefinitely — users returning after months of inactivity retain their full session context.

---

## Error Codes

| HTTP Status | Meaning |
|---|---|
| `200` | Success |
| `400` | Bad request (invalid input or missing fields) |
| `401` | Missing or invalid API key |
| `404` | User or resource not found |
| `422` | Validation error (Pydantic schema mismatch) |
| `429` | Rate limit exceeded |
| `500` | Internal server error |

---

## Configuration Reference

Key `.env` variables affecting API behavior:

| Variable | Default | Description |
|---|---|---|
| `DEBUG` | `false` | Enable debug mode and verbose logging |
| `HOST` | `0.0.0.0` | Server bind address |
| `PORT` | `8000` | Server port |
| `VALID_API_KEYS` | — | Comma-separated public API keys |
| `INTERNAL_SERVICE_SECRET` | — | Backend-to-backend auth secret |
| `ALLOWED_ORIGINS` | `*` | CORS origins (restrict in production) |
| `RATE_LIMIT_PER_MINUTE` | `10` | Rate limit per API key |
| `LLM_PROVIDER` | `openai` | `openai` or `ollama` |
| `LLM_MODEL` | `gpt-4o-mini` | LLM model name |
| `OPENAI_API_KEY` | — | OpenAI API key |

---

## Interactive Documentation

When the server is running:

- **Swagger UI:** `http://localhost:8000/api/docs`
- **ReDoc:** `http://localhost:8000/api/redoc`
- **OpenAPI JSON:** `http://localhost:8000/api/openapi.json`

---

## Production Checklist

1. Set `DEBUG=false`
2. Use strong, unique values for `VALID_API_KEYS` and `INTERNAL_SERVICE_SECRET`
3. Restrict `ALLOWED_ORIGINS` to your frontend domain(s)
4. Run behind an HTTPS reverse proxy (Nginx, Caddy, etc.)
5. Use `docker-compose up -d` with the provided configuration
6. Monitor via the `/health` endpoint

# NakshatraAI API - Quick Setup Guide

## Prerequisites

Choose ONE option for LLM:

### Option 1: Google Cloud (Vertex AI) - RECOMMENDED

1. **Create Google Cloud Project**
   - Go to [Google Cloud Console](https://console.cloud.google.com)
   - Create a new project or select existing

2. **Enable Vertex AI API**
   - Navigate to APIs & Services
   - Enable "Vertex AI API"

3. **Create Service Account**
   - Go to IAM & Admin → Service Accounts
   - Create service account with "Vertex AI User" role
   - Generate and download JSON key file

### Option 2: OpenAI

1. **Get API Key**
   - Go to [OpenAI Platform](https://platform.openai.com/api-keys)
   - Create new API key
   - Copy the key

---

## Setup Steps

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
# Copy example file
cp .env.example .env
```

### 3. Edit .env File

#### For Google Cloud:

```env
# Your custom API keys (any string you choose)
VALID_API_KEYS=my-dev-key-123

# Google Cloud Configuration
GOOGLE_CREDENTIALS_PATH=/path/to/service-account-key.json
GOOGLE_PROJECT_ID=your-project-id
GOOGLE_LOCATION=us-central1

LLM_PROVIDER=google
LLM_MODEL=gemini-2.0-flash-exp
```

#### For OpenAI:

```env
# Your custom API keys
VALID_API_KEYS=my-dev-key-123

# OpenAI Configuration
OPENAI_API_KEY=sk-your-api-key
LLM_PROVIDER=openai
LLM_MODEL=gpt-4
```

### 4. Run the API

```bash
# Start server
uvicorn src.api.main:app --reload

# API will be available at:
# http://localhost:8000

# Documentation:
# http://localhost:8000/api/docs
```

### 5. Test

```bash
# Health check (no auth)
curl http://localhost:8000/api/v1/health

# Chat (with your custom API key)
curl -X POST http://localhost:8000/api/v1/chat \
  -H "X-API-Key: my-dev-key-123" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is my sun sign?",
    "user_id": "test_user"
  }'
```

---

## Docker Deployment

### 1. Edit .env (same as above)

### 2. Run with Docker Compose

```bash
docker-compose up -d
```

### 3. View Logs

```bash
docker-compose logs -f
```

### 4. Stop

```bash
docker-compose down
```

---

## Google Cloud Service Account Setup (Detailed)

1. **Create Service Account**
   ```
   Console → IAM & Admin → Service Accounts → Create
   ```

2. **Grant Permissions**
   - Role: "Vertex AI User"
   - Role: "Service Account Token Creator" (optional)

3. **Create JSON Key**
   ```
   Service Account → Keys → Add Key → Create New Key → JSON
   ```

4. **Save JSON File**
   - Download to your project directory
   - Update `GOOGLE_CREDENTIALS_PATH` in `.env`

5. **Set Project ID**
   - Find in Google Cloud Console (top bar)
   - Update `GOOGLE_PROJECT_ID` in `.env`

---

## Troubleshooting

### Google Cloud Errors

**"Permission denied"**
- Ensure Vertex AI API is enabled
- Check service account has "Vertex AI User" role

**"Credentials not found"**
- Verify `GOOGLE_CREDENTIALS_PATH` points to correct file
- Use absolute path or path relative to project root

**"Invalid project ID"**
- Verify `GOOGLE_PROJECT_ID` matches your Google Cloud project

### OpenAI Errors

**"Invalid API key"**
- Check `OPENAI_API_KEY` is correct
- Ensure you have credits/quota

### API Errors

**"401 Unauthorized"**
- Include `X-API-Key` header
- Verify key matches one in `VALID_API_KEYS`

**"429 Rate Limit"**
- You've exceeded 10 requests/minute
- Wait 60 seconds or increase limit in `.env`

---

## Environment Variables Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `VALID_API_KEYS` | Yes | Your custom API keys (comma-separated) |
| `GOOGLE_CREDENTIALS_PATH` | For Google | Path to service account JSON |
| `GOOGLE_PROJECT_ID` | For Google | Google Cloud project ID |
| `GOOGLE_LOCATION` | No | Vertex AI region (default: us-central1) |
| `OPENAI_API_KEY` | For OpenAI | OpenAI API key |
| `LLM_PROVIDER` | Yes | `google` or `openai` |
| `LLM_MODEL` | Yes | Model name |

---

## Next Steps

1. Visit http://localhost:8000/api/docs for interactive API documentation
2. See `API_README.md` for detailed endpoint documentation
3. Check `walkthrough.md` for implementation details

# Quick Start - Google Cloud Already Setup

Since you already have Google Cloud project and APIs enabled, just do this:

## Step 1: Create Service Account & Download JSON Key

```bash
# Go to your Google Cloud Console
https://console.cloud.google.com

# Navigate to:
IAM & Admin → Service Accounts → Create Service Account

# Fill in:
Name: nakshatraai-api
Role: Vertex AI User

# Create key:
Keys tab → Add Key → Create New Key → JSON → Download
```

Save the downloaded JSON file as `google-credentials.json`

## Step 2: Setup Credentials Folder

```bash
# In your project directory
mkdir credentials
mv ~/Downloads/YOUR-PROJECT-*.json ./credentials/google-credentials.json
```

## Step 3: Update .env File

```bash
# Copy example
cp .env.example .env

# Edit .env and set:
VALID_API_KEYS=my-dev-key-123
GOOGLE_CREDENTIALS_PATH=./credentials/google-credentials.json
GOOGLE_PROJECT_ID=your-actual-project-id
GOOGLE_LOCATION=us-central1
LLM_PROVIDER=google
LLM_MODEL=gemini-2.5-flash
```

## Step 4: Install/Update Dependencies

```bash
pip install langchain-google-vertexai google-cloud-aiplatform google-auth
```

## Step 5: Run API

```bash
uvicorn src.api.main:app --reload
```

Visit: http://localhost:8000/api/docs

## Step 6: Test

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "X-API-Key: my-dev-key-123" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is my sun sign?", "user_id": "test"}'
```

## Troubleshooting

**If you get "Credentials not found":**
- Check file path in .env is correct
- Use absolute path if needed: `GOOGLE_CREDENTIALS_PATH=/full/path/to/google-credentials.json`

**If you get "Permission denied":**
- Ensure service account has "Vertex AI User" role
- Check Vertex AI API is enabled in your project

That's it! 🎉

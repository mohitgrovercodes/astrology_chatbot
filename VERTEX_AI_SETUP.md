# Vertex AI Setup Guide for GCP Credits

## Prerequisites Checklist

Before proceeding, make sure you have:

- [ ] A Google Cloud Platform (GCP) account with billing enabled
- [ ] GCP credits available in your account
- [ ] A GCP project created

## Step 1: Enable Vertex AI API

1. Go to: https://console.cloud.google.com/
2. Select your project (or create a new one)
3. Navigate to **APIs & Services > Library**
4. Search for "**Vertex AI API**"
5. Click **Enable**

##  Step 2: Install Vertex AI Package

Run this command to install the required package:

```bash
.\venv\Scripts\pip.exe install langchain-google-vertexai google-cloud-aiplatform
```

## Step 3: Set Up Authentication

You have two options:

### Option A: Application Default Credentials (Recommended for Development)

1. Install Google Cloud SDK: https://cloud.google.com/sdk/docs/install
2. Run authentication:
   ```bash
   gcloud auth application-default login
   ```
3. Follow the browser prompts to authenticate

### Option B: Service Account (Recommended for Production)

1. Go to: https://console.cloud.google.com/iam-admin/serviceaccounts
2. Click "**Create Service Account**"
3. Give it a name (e.g., "astro-chatbot-service")
4. Grant role: "**Vertex AI User**"
5. Click "**Create Key**" → JSON format
6. Download the JSON file
7. Save it securely (e.g., `config/gcp-service-account.json`)

## Step 4: Update .env File

Add these lines to your `.env` file:

```bash
# Vertex AI Configuration
GOOGLE_CLOUD_PROJECT=your-project-id-here
GOOGLE_APPLICATION_CREDENTIALS=./config/gcp-service-account.json  # If using service account
VERTEX_AI_LOCATION=us-central1  # or your preferred region
```

## Step 5: Verify Setup

Run the verification script:

```bash
python tests/test_vertex_ai.py
```

## Cost Estimation for PDF Extraction

Assuming you have ~1000 pages to extract from PDFs:

### Using Vertex AI (GCP Credits):

| Model | Input Cost | Output Cost | Est. Total (1000 pages) |
|-------|------------|-------------|-------------------------|
| gemini-2.5-flash | $0.075/1M tokens | $0.30/1M tokens | ~$15-30 |
| gemini-2.5-pro | $1.25/1M tokens | $5.00/1M tokens | ~$250-500 |

**Recommendation**: Use `gemini-2.5-flash` for extraction (faster, cheaper, good enough quality)

### Rate Limits (Vertex AI):

- Much higher than AI Studio
- Default: 60 requests/minute (can be increased)
- Suitable for batch processing

## Next Steps

After setup is complete, the IMPLEMENTATION_GUIDE.md will be updated to use Vertex AI instead of AI Studio.

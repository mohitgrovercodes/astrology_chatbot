# Google Cloud Setup - Quick Reference

## 1. Create Service Account

```bash
# Go to Google Cloud Console
https://console.cloud.google.com

# Navigate to:
IAM & Admin → Service Accounts → Create Service Account

# Name: nakshatraai-service-account
# Role: Vertex AI User
```

## 2. Enable APIs

```bash
# Enable Vertex AI API
APIs & Services → Enable APIs → Search "Vertex AI API" → Enable
```

## 3. Create JSON Key

```bash
# In Service Account:
Keys → Add Key → Create New Key → JSON → Create

# Save as: google-credentials.json
# Location: ./credentials/google-credentials.json
```

## 4. Update .env

```env
GOOGLE_CREDENTIALS_PATH=./credentials/google-credentials.json
GOOGLE_PROJECT_ID=your-project-id
GOOGLE_LOCATION=us-central1
LLM_PROVIDER=google
LLM_MODEL=gemini-2.0-flash-exp
```

## 5. Folder Structure

```
astro_chatbot/
├── credentials/
│   └── google-credentials.json  ← Your service account key
├── .env
└── ...
```

## 6. Test

```bash
python -c "import google.auth; print(google.auth.load_credentials_from_file('./credentials/google-credentials.json'))"
```

Should print: `(<Credentials...>, 'your-project-id')`

## Notes

- **Never commit** `google-credentials.json` to git
- Add to `.gitignore`: `credentials/*.json`
- For production, use environment-based credentials

<!-- QUICKSTART1.md -->
# 🚀 QUICK START - Gemini 3.0 Flash

## Step 1: Setup .env File (2 minutes)

Create a `.env` file in your project root:

```bash
# Copy the template
cp .env.example .env

# Edit with your values
nano .env  # or use any text editor
```

**Your .env should look like:**

```env
# LLM Configuration
LLM_PROVIDER=google
LLM_MODEL=gemini-3.0-flash
LLM_TEMPERATURE=0.1

# Google Cloud Credentials
GOOGLE_APPLICATION_CREDENTIALS=/path/to/your/service-account-key.json
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_REGION=us-central1

# Processing Configuration
BATCH_SIZE=10
MAX_WORKERS=5
RATE_LIMIT_RPM=60
MAX_RETRIES=3
RETRY_DELAY=2
```

**Replace:**
- `/path/to/your/service-account-key.json` → Your actual path
- `your-project-id` → Your GCP project ID

---

## Step 2: Install Dependencies (1 minute)

```bash
pip install python-dotenv langchain-google-genai google-generativeai pydantic tqdm
```

---

## Step 3: Test Connection (30 seconds)

```bash
# Quick test
python -c "
from dotenv import load_dotenv
load_dotenv()
from langchain_google_genai import ChatGoogleGenerativeAI
import os

model = os.getenv('LLM_MODEL', 'gemini-3.0-flash')
print(f'Using model: {model}')

llm = ChatGoogleGenerativeAI(model=model, temperature=0.1)
response = llm.invoke('Say hello')
print(f'Response: {response.content}')
print('✅ Connection successful!')
"
```

If you see "✅ Connection successful!" - you're ready!

---

## Step 4: Extract Validation Rules (15 minutes)

```bash
# Test with 2 files first
python extract_rules_json_gemini.py \
    --input-dir /path/to/your/json_chunks \
    --output vedic_validation_rules.json \
    --limit 2

# Check output
cat vedic_validation_rules.json | head -50

# If good, run on more files (or all)
python extract_rules_json_gemini.py \
    --input-dir /path/to/your/json_chunks \
    --output vedic_validation_rules.json \
    --limit 10  # or remove --limit for all files
```

**Expected Output:**
```
🚀 Vedic Validation Rule Extraction (JSON + Gemini)
📁 Input: /path/to/json_chunks
💾 Output: vedic_validation_rules.json
============================================================
✅ Initialized Gemini: gemini-3.0-flash
   Temperature: 0.1
   Project: your-project-id

📚 Found 2 JSON files

📖 Processing: brihat_parasara_chunks.json
  📄 Found 234 chunks
  Extracting: 100%|████████████| 234/234 [01:45<00:00]
    Chunk 45: Found 3 rules
    Chunk 67: Found 2 rules
  ✅ Extracted 47 rules from brihat_parasara_chunks.json

...

✅ EXTRACTION COMPLETE
📊 Total Rules Extracted: 89
```

---

## Step 5: Enrich Metadata (Optional, 15 minutes)

```bash
# Test with 2 files
python enrich_metadata_json_gemini.py \
    --input-dir /path/to/your/json_chunks \
    --output /path/to/enriched_chunks \
    --limit 2

# Check output
ls /path/to/enriched_chunks/

# If good, run on all
python enrich_metadata_json_gemini.py \
    --input-dir /path/to/your/json_chunks \
    --output /path/to/enriched_chunks
```

---

## Step 6: Test Validation Engine (2 minutes)

```bash
python vedic_validation_engine.py
```

**Expected Output:**
```
✅ Loaded 89 validation rules
   Promise: 45
   Timing: 28
   Trigger: 16

🔍 PROMISE VALIDATION (marriage)
============================================================
Checking 12 rules...
  [1] Functional Nature Check... ✅
  [2] Combustion Check... ✅
  ...

✅ PROMISE VALIDATION COMPLETE
```

---

## ✅ Checklist

- [ ] Created .env file with credentials
- [ ] Installed dependencies (python-dotenv, langchain-google-genai)
- [ ] Tested Gemini connection
- [ ] Extracted rules from 2+ files
- [ ] Reviewed rule quality
- [ ] (Optional) Enriched metadata
- [ ] Tested validation engine

---

## 🚨 Troubleshooting

### Error: "GOOGLE_APPLICATION_CREDENTIALS not set"

**Fix:**
```bash
# Check if .env exists
cat .env | grep GOOGLE_APPLICATION_CREDENTIALS

# Set manually if needed
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/key.json"
```

### Error: "No module named 'dotenv'"

**Fix:**
```bash
pip install python-dotenv
```

### Error: "Model gemini-3.0-flash not found"

**Possible causes:**
1. Model name typo - check .env has `LLM_MODEL=gemini-3.0-flash`
2. Vertex AI API not enabled in Google Cloud Console
3. Service account doesn't have access

**Fix:**
```bash
# Enable Vertex AI API
gcloud services enable aiplatform.googleapis.com

# Verify service account permissions
gcloud projects get-iam-policy YOUR_PROJECT_ID \
    --flatten="bindings[].members" \
    --filter="bindings.members:YOUR_SERVICE_ACCOUNT_EMAIL"
```

### Error: "Quota exceeded"

**Fix:**
- Use `--limit 5` to process fewer files
- Wait a few minutes between runs
- Request quota increase in Google Cloud Console

---

## 📝 All Commands (Copy-Paste)

```bash
# 1. Setup
cp .env.example .env
# Edit .env with your credentials

# 2. Install
pip install python-dotenv langchain-google-genai google-generativeai pydantic tqdm

# 3. Test connection
python -c "from dotenv import load_dotenv; load_dotenv(); from langchain_google_genai import ChatGoogleGenerativeAI; llm = ChatGoogleGenerativeAI(model='gemini-3.0-flash'); print('✅ Connected!')"

# 4. Extract rules (test)
python extract_rules_json_gemini.py --input-dir /path/to/json --output rules.json --limit 2

# 5. Extract rules (full)
python extract_rules_json_gemini.py --input-dir /path/to/json --output rules.json

# 6. Enrich metadata (optional)
python enrich_metadata_json_gemini.py --input-dir /path/to/json --output /path/to/enriched

# 7. Test validation
python vedic_validation_engine.py
```

---

## 🎯 What's Next?

Once you have:
- ✅ `vedic_validation_rules.json` with extracted rules
- ✅ (Optional) Enriched chunks with metadata

**Next:** Integrate into your orchestrator (see INTEGRATION_GUIDE.md)

---

## 💰 Cost Estimate (Gemini 3.0 Flash)

- **5,000 chunks**: ~$3-5
- **10,000 chunks**: ~$6-10
- **Processing time**: ~2-3 hours for 10,000 chunks

**Much cheaper than GPT-4!** 🎉

---

**Everything is configured for gemini-3.0-flash by default. Just set your .env and go!**

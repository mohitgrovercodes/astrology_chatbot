"""
Debug script to test intent classification.
"""

import os
import sys
from dotenv import load_dotenv

# Load environment
load_dotenv()

print("=" * 70)
print("INTENT CLASSIFIER DEBUG")
print("=" * 70)
print()

# Step 1: Check environment variables
print("Step 1: Environment Variables")
print("-" * 40)
print(f"LLM_PROVIDER: {os.getenv('DEFAULT_LLM_PROVIDER')}")
print(f"LLM_MODEL: {os.getenv('DEFAULT_LLM_MODEL')}")
print(f"GOOGLE_PROJECT: {os.getenv('GOOGLE_CLOUD_PROJECT')}")
print(f"GOOGLE_CREDENTIALS: {os.getenv('GOOGLE_APPLICATION_CREDENTIALS')}")
print()

# Step 2: Initialize LLM
print("Step 2: Initializing LLM...")
print("-" * 40)

try:
    from langchain_google_vertexai import ChatVertexAI
    import google.auth
    
    # Load credentials
    creds_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    if creds_path and os.path.exists(creds_path):
        print(f"✓ Loading credentials from: {creds_path}")
        credentials, project = google.auth.load_credentials_from_file(creds_path)
    else:
        print("✓ Using default credentials")
        credentials, project = google.auth.default()
    
    project_id = os.getenv('GOOGLE_CLOUD_PROJECT') or project
    model_name = os.getenv('DEFAULT_LLM_MODEL', 'gemini-2.0-flash-exp')
    
    print(f"✓ Project ID: {project_id}")
    print(f"✓ Model: {model_name}")
    
    llm = ChatVertexAI(
        model_name=model_name,
        credentials=credentials,
        project=project_id,
        temperature=0.3,
        location=os.getenv('VERTEX_AI_LOCATION', 'us-central1')
    )
    
    print("✓ LLM initialized successfully")
    print()
    
except Exception as e:
    print(f"✗ LLM initialization FAILED: {e}")
    print()
    sys.exit(1)

# Step 3: Test LLM
print("Step 3: Testing LLM...")
print("-" * 40)

try:
    response = llm.invoke("Say 'Hello'")
    print(f"✓ LLM Response: {response.content if hasattr(response, 'content') else str(response)}")
    print()
except Exception as e:
    print(f"✗ LLM invocation FAILED: {e}")
    print()
    sys.exit(1)

# Step 4: Initialize Intent Classifier
print("Step 4: Initializing Intent Classifier...")
print("-" * 40)

from src.ai.intent_classifier import LLMIntentClassifier

classifier = LLMIntentClassifier(llm=llm)
print(f"✓ Classifier initialized")
print(f"✓ LLM connected: {classifier.llm is not None}")
print()

# Step 5: Test Classification
print("Step 5: Testing Intent Classification...")
print("-" * 40)

test_queries = [
    "hi",
    "show my birth chart",
    "when will I get married",
    "what does Mars in 7th house mean"
]

for query in test_queries:
    print(f"\nQuery: '{query}'")
    result = classifier.classify(query, user_profile={})
    print(f"  Intent: {result['intent']}")
    print(f"  Confidence: {result['confidence']:.2f}")
    print(f"  Reasoning: {result['reasoning']}")
    print(f"  Cached: {result.get('cached', False)}")

print()
print("=" * 70)
print("✅ DEBUG COMPLETE")
print("=" * 70)

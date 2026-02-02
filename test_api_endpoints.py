"""
API Endpoint Test Suite
========================

Tests all major API endpoints with sample data.
Make sure the server is running: uvicorn src.api.main:app --reload
"""

import requests
import json
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:8000/api/v1"
API_KEY = "my-dev-key-123"  # From your .env file

HEADERS = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json"
}

# Test user data (from your dummy users)
TEST_USER = {
    "user_id": "user001",
    "name": "Arjun Kumar",
    "date_of_birth": "1995-03-15",
    "time_of_birth": "14:30:00",
    "place_of_birth": "Jaipur, Rajasthan, India",
    "latitude": 26.9124,
    "longitude": 75.7873,
    "timezone": "Asia/Kolkata"
}

def print_section(title):
    """Print a formatted section header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)

def print_result(endpoint, response):
    """Print formatted test result."""
    status = "PASS" if response.status_code in [200, 201] else "FAIL"
    print(f"\n[{status}] {endpoint}")
    print(f"Status: {response.status_code}")
    
    if response.status_code in [200, 201]:
        try:
            data = response.json()
            print(f"Response: {json.dumps(data, indent=2)[:500]}...")  # First 500 chars
        except:
            print(f"Response: {response.text[:200]}")
    else:
        print(f"Error: {response.text}")

# ============================================================================
# TEST 1: HEALTH CHECK
# ============================================================================
print_section("TEST 1: Health Check (No Auth Required)")

response = requests.get(f"{BASE_URL}/health")
print_result("GET /health", response)

# ============================================================================
# TEST 2: USER ENDPOINTS
# ============================================================================
print_section("TEST 2: User Endpoints")

# Get user profile
response = requests.get(
    f"{BASE_URL}/user/{TEST_USER['user_id']}",
    headers=HEADERS
)
print_result(f"GET /user/{TEST_USER['user_id']}", response)

# ============================================================================
# TEST 3: CHAT ENDPOINT (Main Conversational AI)
# ============================================================================
print_section("TEST 3: Chat Endpoint (Conversational AI)")

test_queries = [
    {
        "name": "Greeting (CHITCHAT)",
        "query": "Hello! Who are you?"
    },
    {
        "name": "Chart Request (CALCULATION_ONLY)",
        "query": "Show me my birth chart"
    },
    {
        "name": "Prediction (RAG_WITH_CALCULATION)",
        "query": "When will I get married?"
    },
    {
        "name": "Theory (RAG_ONLY)",
        "query": "What does Mars in 7th house mean?"
    }
]

for test in test_queries:
    print(f"\n--- {test['name']} ---")
    
    payload = {
        "query": test["query"],
        "user_id": TEST_USER["user_id"]
    }
    
    response = requests.post(
        f"{BASE_URL}/chat",
        headers=HEADERS,
        json=payload
    )
    
    print_result(f"POST /chat - {test['name']}", response)
    
    if response.status_code == 200:
        data = response.json()
        print(f"\nIntent: {data.get('intent', 'N/A')}")
        print(f"Answer Preview: {data.get('answer', '')[:200]}...")

# ============================================================================
# TEST 4: VEDIC CALCULATION ENDPOINTS
# ============================================================================
print_section("TEST 4: Vedic Calculation Endpoints")

chart_payload = {
    "date_of_birth": TEST_USER["date_of_birth"],
    "time_of_birth": TEST_USER["time_of_birth"],
    "latitude": TEST_USER["latitude"],
    "longitude": TEST_USER["longitude"],
    "timezone": TEST_USER["timezone"]
}

# Calculate Vedic Chart
response = requests.post(
    f"{BASE_URL}/calculate/vedic/chart",
    headers=HEADERS,
    json=chart_payload
)
print_result("POST /calculate/vedic/chart", response)

if response.status_code == 200:
    chart = response.json()
    print(f"\nChart Summary:")
    print(f"  Lagna: {chart.get('lagna')}")
    print(f"  Rashi: {chart.get('rashi')}")
    print(f"  Nakshatra: {chart.get('nakshatra')}")

# Get Yogas
response = requests.post(
    f"{BASE_URL}/calculate/vedic/yogas",
    headers=HEADERS,
    json=chart_payload
)
print_result("POST /calculate/vedic/yogas", response)

if response.status_code == 200:
    yogas = response.json()
    print(f"\nYogas Found: {yogas.get('count', 0)}")

# Get Dashas
response = requests.post(
    f"{BASE_URL}/calculate/vedic/dashas",
    headers=HEADERS,
    json=chart_payload
)
print_result("POST /calculate/vedic/dashas", response)

# ============================================================================
# TEST 5: WESTERN CALCULATION ENDPOINTS
# ============================================================================
print_section("TEST 5: Western Calculation Endpoints")

# Calculate Western Chart
response = requests.post(
    f"{BASE_URL}/calculate/western/chart",
    headers=HEADERS,
    json=chart_payload
)
print_result("POST /calculate/western/chart", response)

if response.status_code == 200:
    chart = response.json()
    print(f"\nWestern Chart Summary:")
    print(f"  Sun Sign: {chart.get('sun_sign')}")
    print(f"  Moon Sign: {chart.get('moon_sign')}")
    print(f"  Ascendant: {chart.get('ascendant_sign')}")

# ============================================================================
# TEST 6: CORE EPHEMERIS
# ============================================================================
print_section("TEST 6: Core Astronomical Calculations")

response = requests.post(
    f"{BASE_URL}/calculate/core/ephemeris",
    headers=HEADERS,
    json=chart_payload,
    params={"ayanamsa": "LAHIRI"}  # Optional: for sidereal
)
print_result("POST /calculate/core/ephemeris", response)

# ============================================================================
# SUMMARY
# ============================================================================
print_section("TEST SUMMARY")
print("""
All tests completed!

Next Steps:
1. Check the Swagger UI for interactive testing: http://localhost:8000/api/docs
2. Review any failed tests above
3. Test with different user IDs (user002, user003, user004)
4. Try edge cases (invalid dates, missing fields, etc.)

API Documentation: http://localhost:8000/api/docs
""")

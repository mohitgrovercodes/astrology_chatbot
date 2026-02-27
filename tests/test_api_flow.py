import requests
import uuid
import time

API_URL = "http://localhost:6262/api/v1"

def run_test():
    user_id = f"test_user_{uuid.uuid4().hex[:8]}"
    print(f"Testing with User ID: {user_id}")
    
    # 1. Initialize
    print("\n--- 1. Testing /initialize ---")
    payload = {
        "user_id": user_id,
        "user_profile": {
            "user_id": user_id,
            "name": "Test User",
            "date_of_birth": "2000-01-01",
            "time_of_birth": "12:00:00",
            "place_of_birth": "New Delhi, Delhi, India",
            "latitude": 28.6139,
            "longitude": 77.209,
            "timezone": "Asia/Kolkata",
            "preferred_system": "vedic"
        }
    }
    
    resp = requests.post(f"{API_URL}/chat/initialize", json=payload)
    print(f"Status Code: {resp.status_code}")
    print(f"Response: {resp.json()}")
    assert resp.status_code == 200
    
    # 2. Check Status from Redis
    print("\n--- 2. Checking Session Status ---")
    resp = requests.get(f"{API_URL}/chat/session/{user_id}/status")
    print(f"Status Code: {resp.status_code}")
    print(f"Response: {resp.json()}")
    assert resp.status_code == 200
    assert resp.json()['exists'] is True
    
    # 3. Send Message 1
    print("\n--- 3. Testing /message (First) ---")
    payload = {
        "user_id": user_id,
        "question": "What is my name and lagna?"
    }
    start = time.time()
    resp = requests.post(f"{API_URL}/chat/message", json=payload)
    print(f"Time taken: {time.time() - start:.2f}s")
    print(f"Status Code: {resp.status_code}")
    print(f"Response: {resp.json()}")
    
    # 4. Check Status to see history updated
    print("\n--- 4. Checking Session Status After Message ---")
    resp = requests.get(f"{API_URL}/chat/session/{user_id}/status")
    data = resp.json()
    print(f"Messages in history: {data['cached_data']['conversation_messages']}")
    assert data['cached_data']['conversation_messages'] > 0
    assert data['cached_data']['chart_data'] is True # Should have cached the chart
    
    print("\n✅ All tests passed. API successfully uses Redis flow.")

if __name__ == "__main__":
    run_test()

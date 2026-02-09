import httpx
import json
import time

# Configuration
BASE_URL = "http://localhost:8000/api/v1"
INTERNAL_SECRET = "super-secret-internal-key-123"
SESSION_ID = f"test-session-{int(time.time())}"

def test_chat_integration():
    print(f"--- Testing Backend Integration (Session: {SESSION_ID}) ---")
    
    payload = {
        "message": "My name is Mohit. When will I get married?",
        "session_id": SESSION_ID,
        "user_context": {
            "birth_date": "1995-10-01",
            "birth_time": "07:30:00",
            "latitude": 27.553,
            "longitude": 76.6346,
            "timezone": "Asia/Kolkata",
            "astrology_system": "vedic"
        }
    }
    
    headers = {
        "X-Internal-Service": INTERNAL_SECRET,
        "Content-Type": "application/json"
    }
    
    try:
        with httpx.Client(timeout=30.0) as client:
            # 1. Test first message
            print("Sending first query...")
            response = client.post(f"{BASE_URL}/chat", json=payload, headers=headers)
            
            if response.status_code != 200:
                print(f"[FAIL] Status Code: {response.status_code}")
                print(response.text)
                return
            
            data = response.json()
            print("[SUCCESS] Received response")
            print(f"Answer: {data['answer'][:100]}...")
            print(f"Sources: {len(data['sources'])}")
            print(f"Metadata: {data['metadata']}")
            
            # 2. Test session memory (second message)
            print("\nSending second query (context check)...")
            follow_up = {
                "message": "What is my name?",
                "session_id": SESSION_ID,
                "user_context": payload["user_context"]
            }
            
            response = client.post(f"{BASE_URL}/chat", json=follow_up, headers=headers)
            data = response.json()
            print(f"Answer: {data['answer']}")
            
            if "Mohit" in data['answer']:
                print("[SUCCESS] Session memory working (Redis)!")
            else:
                print("[WARN] Session memory might not be fully working or LLM ignored it.")
                
            # 3. Test Authentication rejection
            print("\nTesting authentication rejection...")
            bad_headers = {"X-Internal-Service": "wrong-secret"}
            response = client.post(f"{BASE_URL}/chat", json=payload, headers=bad_headers)
            if response.status_code == 403:
                print("[SUCCESS] Invalid secret rejected with 403.")
            else:
                print(f"[FAIL] Expected 403, got {response.status_code}")

    except Exception as e:
        print(f"[ERROR] {e}")

if __name__ == "__main__":
    # Note: Requires the server and Redis to be running
    print("NOTE: Make sure to run 'npm run dev' (or equivalent) and have Redis running before this test.")
    test_chat_integration()

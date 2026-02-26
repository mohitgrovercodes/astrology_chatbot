# scripts/test_redis_ttl.py
import redis
import json
import time
from src.api.config import settings
from src.session.manager import get_session_manager

def test_permanent_storage():
    print("Starting Redis TTL Verification Test...")
    
    manager = get_session_manager()
    user_id = f"ttl_test_{int(time.time())}"
    
    # 1. Initialize Session
    profile = {"name": "TTL Test User", "city": "Test City"}
    print(f"Initializing session for {user_id}...")
    manager.initialize_session(user_id, profile)
    
    # 2. Add a message
    print("Adding a message...")
    manager.add_message(user_id, "user", "Hello Redis")
    
    # 3. Store a summary
    print("Storing a summary...")
    manager.store_conversation_summary(user_id, "This is a test summary")
    
    # 4. Verify TTLs
    keys_to_check = [
        f"session:{user_id}:user_profile",
        f"session:{user_id}:history",
        f"session:{user_id}:summary",
        f"session:{user_id}:metadata"
    ]
    
    r = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, decode_responses=True)
    
    all_permanent = True
    for key in keys_to_check:
        ttl = r.ttl(key)
        if ttl == -1:
            print(f"[PASS] Key {key} is PERMANENT (TTL = -1)")
        else:
            print(f"[FAIL] Key {key} has TTL: {ttl}")
            all_permanent = False
            
    if all_permanent:
        print("\nSUCCESS: All critical session data is stored permanently.")
    else:
        print("\nFAILURE: Some session data still has time limits.")
        exit(1)

if __name__ == "__main__":
    test_permanent_storage()

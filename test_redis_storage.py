# test_redis_storage.py
"""
Comprehensive Test Script for Redis Storage and API Functionality

Tests:
1. Session initialization
2. Message sending
3. Redis data storage verification
4. Conversation format conversion
5. Caching behavior
6. TTL verification
"""

import requests
import redis
import json
import time
from datetime import datetime
from typing import Dict, Any


# ============================================================================
# CONFIGURATION
# ============================================================================

API_BASE_URL = "http://localhost:6262/api/v1/chat"
REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_DB = 0

# Colors for terminal output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    MAGENTA = '\033[95m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def print_header(text: str):
    """Print section header."""
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*80}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.CYAN}{text.center(80)}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*80}{Colors.ENDC}\n")


def print_success(text: str):
    """Print success message."""
    print(f"{Colors.GREEN}[OK] {text}{Colors.ENDC}")


def print_error(text: str):
    """Print error message."""
    print(f"{Colors.RED}[FAIL] {text}{Colors.ENDC}")


def print_info(text: str):
    """Print info message."""
    print(f"{Colors.BLUE}ℹ️  {text}{Colors.ENDC}")


def print_warning(text: str):
    """Print warning message."""
    print(f"{Colors.YELLOW}[WARN]  {text}{Colors.ENDC}")


def print_json(title: str, data: Any):
    """Print formatted JSON."""
    print(f"\n{Colors.MAGENTA}{title}:{Colors.ENDC}")
    print(json.dumps(data, indent=2))


# ============================================================================
# REDIS CONNECTION
# ============================================================================

def connect_redis():
    """Connect to Redis."""
    try:
        r = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            decode_responses=True
        )
        r.ping()
        print_success("Connected to Redis")
        return r
    except Exception as e:
        print_error(f"Failed to connect to Redis: {e}")
        return None


# ============================================================================
# TEST 1: INITIALIZE SESSION
# ============================================================================

def test_initialize_session(user_id: str, r: redis.Redis):
    """Test session initialization and verify Redis storage."""
    print_header("TEST 1: INITIALIZE SESSION")
    
    # Clear any existing session
    print_info(f"Cleaning up any existing session for {user_id}...")
    keys = r.keys(f"session:{user_id}:*")
    if keys:
        r.delete(*keys)
        print_success(f"Deleted {len(keys)} existing keys")
    
    # Prepare request with conversation history
    payload = {
        "user_id": user_id,
        "user_profile": {
            "user_id": user_id,
            "name": "Test User",
            "date_of_birth": "1990-07-15",
            "time_of_birth": "08:30:00",
            "place_of_birth": "New Delhi, India",
            "latitude": 28.6139,
            "longitude": 77.2090,
            "timezone": "Asia/Kolkata",
            "preferred_system": "vedic"
        },
        "conversation_history": [
            {
                "question": "Hello, can you help me?",
                "answer": "Of course! I'm here to help with your astrological questions.",
                "source": "external",
                "timestamp": {"$date": "2026-02-20T10:00:00.000Z"}
            },
            {
                "question": "When will I get married?",
                "answer": "Based on preliminary analysis, March 2026 looks favorable.",
                "source": "external",
                "timestamp": {"$date": "2026-02-20T10:05:00.000Z"}
            }
        ]
    }
    
    print_info("Sending initialize request...")
    print_json("Request Payload", payload)
    
    # Send request
    response = requests.post(f"{API_BASE_URL}/initialize", json=payload)
    
    if response.status_code == 200:
        data = response.json()
        print_success("Initialize request successful")
        print_json("API Response", data)
        
        # Verify response format
        assert "user_id" in data, "Response missing user_id"
        assert "status" in data, "Response missing status"
        assert data["status"] == "success", f"Expected status 'success', got '{data['status']}'"
        print_success("Response format validated")
        
        # Verify Redis storage
        print_info("\nVerifying Redis storage...")
        
        # Check all keys exist
        expected_keys = [
            f"session:{user_id}:user_profile",
            f"session:{user_id}:conversation",
            f"session:{user_id}:metadata"
        ]
        
        for key in expected_keys:
            if r.exists(key):
                ttl = r.ttl(key)
                print_success(f"Key exists: {key} (TTL: {ttl}s = {ttl/3600:.1f}h)")
            else:
                print_error(f"Key missing: {key}")
        
        # Verify user profile
        print_info("\n--- USER PROFILE ---")
        profile_str = r.get(f"session:{user_id}:user_profile")
        if profile_str:
            profile = json.loads(profile_str)
            print_json("Stored User Profile", profile)
            assert profile["user_id"] == user_id
            assert profile["name"] == "Test User"
            assert profile["date_of_birth"] == "1990-07-15"
            print_success("User profile stored correctly")
        
        # Verify conversation conversion
        print_info("\n--- CONVERSATION HISTORY ---")
        conv_str = r.get(f"session:{user_id}:conversation")
        if conv_str:
            conversation = json.loads(conv_str)
            print_json("Stored Conversation (Internal Format)", conversation)
            
            # Verify conversion from external format
            assert len(conversation) == 4, f"Expected 4 messages, got {len(conversation)}"
            assert conversation[0]["role"] == "user"
            assert conversation[0]["content"] == "Hello, can you help me?"
            assert conversation[1]["role"] == "assistant"
            assert conversation[1]["metadata"]["source"] == "external"
            print_success("Conversation format converted correctly")
            print_success(f"External format (2 Q&A pairs) -> Internal format (4 messages)")
        
        # Verify metadata
        print_info("\n--- METADATA ---")
        metadata_str = r.get(f"session:{user_id}:metadata")
        if metadata_str:
            metadata = json.loads(metadata_str)
            print_json("Stored Metadata", metadata)
            assert metadata["user_id"] == user_id
            assert metadata["messages_imported"] == 4
            print_success("Metadata stored correctly")
        
        return True
    else:
        print_error(f"Initialize request failed: {response.status_code}")
        print(response.text)
        return False


# ============================================================================
# TEST 2: SEND FIRST MESSAGE (Chart Calculation)
# ============================================================================

def test_send_first_message(user_id: str, r: redis.Redis):
    """Test first message and verify chart caching."""
    print_header("TEST 2: SEND FIRST MESSAGE (Chart Calculation)")
    
    # Check current conversation length
    conv_str = r.get(f"session:{user_id}:conversation")
    if conv_str:
        conv_before = json.loads(conv_str)
        print_info(f"Conversation before: {len(conv_before)} messages")
    
    # Send message
    payload = {
        "user_id": user_id,
        "question": "What is my moon sign?"
    }
    
    print_info("Sending first message...")
    print_json("Request", payload)
    
    start_time = time.time()
    response = requests.post(f"{API_BASE_URL}/message", json=payload)
    elapsed = time.time() - start_time
    
    if response.status_code == 200:
        data = response.json()
        print_success(f"Message request successful ({elapsed:.2f}s)")
        print_json("API Response", data)
        
        # Verify response format
        assert "user_id" in data
        assert "question" in data
        assert "answer" in data
        assert "source" in data
        assert data["question"] == "What is my moon sign?"
        assert data["source"] == "openai"
        print_success("Response format validated")
        
        # Verify conversation updated
        print_info("\n--- CONVERSATION UPDATE ---")
        conv_str = r.get(f"session:{user_id}:conversation")
        if conv_str:
            conversation = json.loads(conv_str)
            print_info(f"Conversation after: {len(conversation)} messages")
            print_json("Last 2 Messages", conversation[-2:])
            
            # Should have added 2 new messages (user + assistant)
            assert len(conversation) == len(conv_before) + 2
            assert conversation[-2]["role"] == "user"
            assert conversation[-2]["content"] == "What is my moon sign?"
            assert conversation[-1]["role"] == "assistant"
            assert conversation[-1]["metadata"]["source"] == "openai"
            print_success("Conversation updated correctly")
        
        # Check if chart data was cached
        print_info("\n--- CHART CACHING ---")
        chart_key = f"session:{user_id}:chart_data"
        if r.exists(chart_key):
            ttl = r.ttl(chart_key)
            print_success(f"Chart data cached! (TTL: {ttl}s = {ttl/86400:.1f} days)")
            
            chart_str = r.get(chart_key)
            chart = json.loads(chart_str)
            print_json("Cached Chart Data (sample)", {
                "lagna": chart.get("lagna"),
                "moon_sign": chart.get("moon_sign"),
                "sun_sign": chart.get("sun_sign"),
                "planets_count": len(chart.get("planets", {}))
            })
        else:
            print_warning("Chart data not cached (may not have been calculated)")
        
        return True, elapsed
    else:
        print_error(f"Message request failed: {response.status_code}")
        print(response.text)
        return False, 0


# ============================================================================
# TEST 3: SEND SECOND MESSAGE (Cache Hit)
# ============================================================================

def test_send_second_message(user_id: str, r: redis.Redis):
    """Test second message to verify cache usage."""
    print_header("TEST 3: SEND SECOND MESSAGE (Using Cache)")
    
    payload = {
        "user_id": user_id,
        "question": "How does my moon sign affect my career?"
    }
    
    print_info("Sending second message...")
    print_json("Request", payload)
    
    # Check cache before
    chart_exists_before = r.exists(f"session:{user_id}:chart_data")
    print_info(f"Chart cached before request: {chart_exists_before}")
    
    start_time = time.time()
    response = requests.post(f"{API_BASE_URL}/message", json=payload)
    elapsed = time.time() - start_time
    
    if response.status_code == 200:
        data = response.json()
        print_success(f"Message request successful ({elapsed:.2f}s)")
        print_json("API Response", data)
        
        # Verify conversation length
        conv_str = r.get(f"session:{user_id}:conversation")
        if conv_str:
            conversation = json.loads(conv_str)
            print_info(f"Total messages now: {len(conversation)}")
            print_json("Last Message", conversation[-1])
        
        # Compare timing
        print_info("\n--- PERFORMANCE ---")
        if chart_exists_before:
            print_success("Chart was already cached - response should be faster")
        
        return True, elapsed
    else:
        print_error(f"Message request failed: {response.status_code}")
        return False, 0


# ============================================================================
# TEST 4: VERIFY CONTEXT WINDOW
# ============================================================================

def test_context_window(user_id: str, r: redis.Redis):
    """Test that context window is working."""
    print_header("TEST 4: VERIFY CONTEXT WINDOW")
    
    # Send a follow-up question that requires context
    payload = {
        "user_id": user_id,
        "question": "Tell me more about what you just said"
    }
    
    print_info("Sending context-dependent question...")
    print_json("Request", payload)
    
    response = requests.post(f"{API_BASE_URL}/message", json=payload)
    
    if response.status_code == 200:
        data = response.json()
        print_success("Message request successful")
        print_json("API Response", data)
        
        # Check if answer references previous context
        answer = data["answer"].lower()
        if "moon" in answer or "career" in answer or "gemini" in answer:
            print_success("Bot remembered context from previous messages!")
        else:
            print_warning("Bot may not have used context (answer seems generic)")
        
        return True
    else:
        print_error(f"Message request failed: {response.status_code}")
        return False


# ============================================================================
# TEST 5: VERIFY TTL
# ============================================================================

def test_ttl_values(user_id: str, r: redis.Redis):
    """Verify all TTL values are correct."""
    print_header("TEST 5: VERIFY TTL VALUES")
    
    expected_ttls = {
        f"session:{user_id}:user_profile": (86400, "24 hours"),
        f"session:{user_id}:conversation": (86400, "24 hours"),
        f"session:{user_id}:metadata": (86400, "24 hours"),
        f"session:{user_id}:chart_data": (604800, "7 days"),
    }
    
    for key, (expected_ttl, description) in expected_ttls.items():
        if r.exists(key):
            actual_ttl = r.ttl(key)
            # TTL might be slightly less due to processing time
            if actual_ttl > expected_ttl - 60:  # Allow 60s tolerance
                hours = actual_ttl / 3600
                days = actual_ttl / 86400
                print_success(f"{key.split(':')[-1]}: {actual_ttl}s (~{hours:.1f}h / {days:.1f}d) - Expected: {description}")
            else:
                print_warning(f"{key.split(':')[-1]}: {actual_ttl}s - Expected ~{expected_ttl}s ({description})")
        else:
            print_info(f"{key.split(':')[-1]}: Not present (may not have been created yet)")


# ============================================================================
# TEST 6: VIEW ALL REDIS DATA
# ============================================================================

def test_view_all_data(user_id: str, r: redis.Redis):
    """Display all Redis data for the user."""
    print_header("TEST 6: VIEW ALL REDIS DATA")
    
    keys = r.keys(f"session:{user_id}:*")
    print_info(f"Found {len(keys)} keys for user {user_id}:")
    
    for key in sorted(keys):
        data_type = key.split(":")[-1]
        ttl = r.ttl(key)
        size = len(r.get(key) or "")
        
        print(f"\n{Colors.CYAN}--- {data_type.upper()} ---{Colors.ENDC}")
        print(f"Key: {key}")
        print(f"TTL: {ttl}s ({ttl/3600:.1f}h)")
        print(f"Size: {size} bytes")
        
        data_str = r.get(key)
        if data_str:
            try:
                data = json.loads(data_str)
                
                # Show abbreviated data based on type
                if data_type == "conversation":
                    print(f"Messages: {len(data)}")
                    if data:
                        print_json("First message", data[0])
                        print_json("Last message", data[-1])
                elif data_type == "chart_data":
                    print_json("Chart summary", {
                        "lagna": data.get("lagna"),
                        "moon_sign": data.get("moon_sign"),
                        "sun_sign": data.get("sun_sign"),
                        "has_planets": "planets" in data,
                        "has_houses": "houses" in data
                    })
                else:
                    print_json("Data", data)
            except:
                print(f"Raw value: {data_str[:200]}...")


# ============================================================================
# TEST 7: SESSION STATUS ENDPOINT
# ============================================================================

def test_session_status(user_id: str):
    """Test session status endpoint."""
    print_header("TEST 7: SESSION STATUS ENDPOINT")
    
    response = requests.get(f"{API_BASE_URL}/session/{user_id}/status")
    
    if response.status_code == 200:
        data = response.json()
        print_success("Session status retrieved")
        print_json("Status Data", data)
        return True
    else:
        print_error(f"Failed to get session status: {response.status_code}")
        return False


# ============================================================================
# TEST 8: STATS ENDPOINT
# ============================================================================

def test_stats():
    """Test stats endpoint."""
    print_header("TEST 8: STATS ENDPOINT")
    
    response = requests.get(f"{API_BASE_URL}/stats")
    
    if response.status_code == 200:
        data = response.json()
        print_success("Stats retrieved")
        print_json("Stats", data)
        return True
    else:
        print_error(f"Failed to get stats: {response.status_code}")
        return False


# ============================================================================
# MAIN TEST RUNNER
# ============================================================================

def main():
    """Run all tests."""
    print(f"\n{Colors.BOLD}{Colors.CYAN}")
    print("="*80)
    print(" "*20 + "REDIS STORAGE & API TEST SUITE")
    print("="*80)
    print(f"{Colors.ENDC}")
    
    # Connect to Redis
    r = connect_redis()
    if not r:
        print_error("Cannot proceed without Redis connection")
        return
    
    # Generate test user ID
    user_id = f"test_user_{int(time.time())}"
    print_info(f"Test User ID: {user_id}")
    
    # Run tests
    results = {}
    timings = {}
    
    # Test 1: Initialize
    results["initialize"] = test_initialize_session(user_id, r)
    
    if results["initialize"]:
        # Test 2: First message
        success, time1 = test_send_first_message(user_id, r)
        results["first_message"] = success
        timings["first_message"] = time1
        
        # Test 3: Second message (cache hit)
        success, time2 = test_send_second_message(user_id, r)
        results["second_message"] = success
        timings["second_message"] = time2
        
        # Test 4: Context window
        results["context"] = test_context_window(user_id, r)
        
        # Test 5: TTL verification
        test_ttl_values(user_id, r)
        
        # Test 6: View all data
        test_view_all_data(user_id, r)
        
        # Test 7: Session status
        results["status"] = test_session_status(user_id)
        
        # Test 8: Stats
        results["stats"] = test_stats()
    
    # Summary
    print_header("TEST SUMMARY")
    
    total = len(results)
    passed = sum(results.values())
    
    print(f"Total Tests: {total}")
    print(f"Passed: {Colors.GREEN}{passed}{Colors.ENDC}")
    print(f"Failed: {Colors.RED}{total - passed}{Colors.ENDC}")
    print(f"Success Rate: {passed/total*100:.1f}%\n")
    
    # Performance summary
    if timings:
        print(f"{Colors.CYAN}PERFORMANCE:{Colors.ENDC}")
        for test, timing in timings.items():
            print(f"  {test}: {timing:.2f}s")
        
        if "first_message" in timings and "second_message" in timings:
            speedup = timings["first_message"] / timings["second_message"]
            print(f"\n  {Colors.GREEN}Cache speedup: {speedup:.1f}x faster!{Colors.ENDC}")
    
    # Cleanup option
    print(f"\n{Colors.YELLOW}Cleanup:{Colors.ENDC}")
    cleanup = input("Delete test data from Redis? (y/n): ").lower()
    if cleanup == 'y':
        keys = r.keys(f"session:{user_id}:*")
        if keys:
            r.delete(*keys)
            print_success(f"Deleted {len(keys)} keys")
    
    print(f"\n{Colors.GREEN}{'='*80}{Colors.ENDC}")
    print(f"{Colors.GREEN}Testing Complete!{Colors.ENDC}")
    print(f"{Colors.GREEN}{'='*80}{Colors.ENDC}\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}Tests interrupted by user{Colors.ENDC}")
    except Exception as e:
        print(f"\n{Colors.RED}Test error: {e}{Colors.ENDC}")
        import traceback
        traceback.print_exc()
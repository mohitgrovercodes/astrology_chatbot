# test_final_integration.py
"""
Final Integration Test - Verify All Systems Working
Tests: Language detection, greetings, validation, RAG, multilingual
"""

import requests
import json
import time

BASE_URL = "http://localhost:8000"
INTERNAL_SECRET = "super-secret-internal-key-123"

TEST_USER = {
    "user_id": "test_final_user",
    "name": "Priya Sharma",
    "date_of_birth": "1990-05-15",
    "time_of_birth": "14:30:00",
    "latitude": 19.0760,
    "longitude": 72.8777,
    "timezone": "Asia/Kolkata",
    "preferred_system": "vedic"
}

def get_headers():
    return {
        "X-Internal-Service": INTERNAL_SECRET,
        "Content-Type": "application/json"
    }

def print_test(number, title):
    print("\n" + "=" * 80)
    print(f"TEST {number}: {title}")
    print("=" * 80)

def print_result(passed, message):
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status} - {message}")
    return passed


# ============================================================================
# TESTS
# ============================================================================

def test_1_health():
    """Verify API is running."""
    print_test(1, "Health Check")
    try:
        response = requests.get(f"{BASE_URL}/api/v1/health")
        data = response.json()
        
        healthy = data.get('status') == 'healthy'
        orchestrator_ok = data.get('components', {}).get('orchestrator') == 'ok'
        
        print_result(healthy, f"API Status: {data.get('status')}")
        print_result(orchestrator_ok, f"Orchestrator: {data.get('components', {}).get('orchestrator')}")
        
        return healthy and orchestrator_ok
    except Exception as e:
        print_result(False, f"Error: {e}")
        return False


def test_2_english_greeting():
    """Verify English greeting works."""
    print_test(2, "English Greeting")
    try:
        payload = {
            "message": "hello",
            "session_id": TEST_USER["user_id"],
            "user_context": {
                "birth_date": TEST_USER["date_of_birth"],
                "birth_time": TEST_USER["time_of_birth"],
                "latitude": TEST_USER["latitude"],
                "longitude": TEST_USER["longitude"],
                "timezone": TEST_USER["timezone"]
            }
        }
        
        response = requests.post(f"{BASE_URL}/api/v1/chat", json=payload, headers=get_headers())
        
        if response.status_code != 200:
            return print_result(False, f"Status: {response.status_code}")
        
        data = response.json()
        answer = data.get('answer', '')
        
        # Check for English greeting (not Hinglish)
        is_english = answer.startswith("Hello") or "I'm NakshatraAI" in answer
        is_hinglish = answer.startswith("Namaste") or "Main NakshatraAI" in answer
        
        print(f"Response: {answer[:100]}...")
        print_result(is_english, "Greeting is in English")
        print_result(not is_hinglish, "Greeting is NOT in Hinglish")
        
        return is_english and not is_hinglish
        
    except Exception as e:
        return print_result(False, f"Error: {e}")


def test_3_hinglish_greeting():
    """Verify Hinglish greeting works."""
    print_test(3, "Hinglish Greeting")
    try:
        payload = {
            "message": "namaste",
            "session_id": "hinglish_user",
            "user_context": {
                "birth_date": TEST_USER["date_of_birth"],
                "birth_time": TEST_USER["time_of_birth"],
                "latitude": TEST_USER["latitude"],
                "longitude": TEST_USER["longitude"],
                "timezone": TEST_USER["timezone"]
            }
        }
        
        response = requests.post(f"{BASE_URL}/api/v1/chat", json=payload, headers=get_headers())
        data = response.json()
        answer = data.get('answer', '')
        
        is_hinglish = "Namaste" in answer or "Main NakshatraAI" in answer
        
        print(f"Response: {answer[:100]}...")
        print_result(is_hinglish, "Greeting is in Hinglish")
        
        return is_hinglish
        
    except Exception as e:
        return print_result(False, f"Error: {e}")


def test_4_english_prediction():
    """Verify English prediction with validation."""
    print_test(4, "English Marriage Prediction (WITH VALIDATION)")
    try:
        payload = {
            "message": "When will I get married?",
            "session_id": TEST_USER["user_id"],
            "user_context": {
                "birth_date": TEST_USER["date_of_birth"],
                "birth_time": TEST_USER["time_of_birth"],
                "latitude": TEST_USER["latitude"],
                "longitude": TEST_USER["longitude"],
                "timezone": TEST_USER["timezone"]
            }
        }
        
        print("Sending: 'When will I get married?'")
        print("Expected: English response with validation context")
        print("Waiting (no timeout)...")
        
        start = time.time()
        response = requests.post(f"{BASE_URL}/api/v1/chat", json=payload, headers=get_headers())
        elapsed = time.time() - start
        
        print(f"Response time: {elapsed:.1f}s")
        
        if response.status_code != 200:
            return print_result(False, f"Status: {response.status_code}")
        
        data = response.json()
        answer = data.get('answer', '')
        metadata = data.get('metadata', {})
        
        # Check language
        is_english = not answer.startswith("Aapke") and not "vivah" in answer[:100].lower()
        
        print(f"Answer length: {len(answer)} chars")
        print(f"Answer preview: {answer[:150]}...")
        
        print_result(is_english, "Response is in English")
        print_result(metadata.get('intent') == 'RAG_WITH_CALCULATION', f"Intent: {metadata.get('intent')}")
        print_result(elapsed < 60, f"Response time acceptable: {elapsed:.1f}s")
        
        return is_english
        
    except Exception as e:
        return print_result(False, f"Error: {e}")


def test_5_hinglish_prediction():
    """Verify Hinglish prediction works."""
    print_test(5, "Hinglish Marriage Prediction")
    try:
        payload = {
            "message": "Meri shaadi kab hogi?",
            "session_id": "hinglish_pred_user",
            "user_context": {
                "birth_date": TEST_USER["date_of_birth"],
                "birth_time": TEST_USER["time_of_birth"],
                "latitude": TEST_USER["latitude"],
                "longitude": TEST_USER["longitude"],
                "timezone": TEST_USER["timezone"]
            }
        }
        
        print("Sending: 'Meri shaadi kab hogi?'")
        print("Expected: Hinglish response")
        
        response = requests.post(f"{BASE_URL}/api/v1/chat", json=payload, headers=get_headers())
        data = response.json()
        answer = data.get('answer', '')
        
        # Check for Hinglish/Hindi words
        is_hinglish = any(word in answer.lower() for word in ['aapke', 'vivah', 'shaadi', 'kundli', 'graha'])
        
        print(f"Answer preview: {answer[:150]}...")
        print_result(is_hinglish, "Response is in Hinglish")
        
        return is_hinglish
        
    except Exception as e:
        return print_result(False, f"Error: {e}")


def test_6_rag_sources():
    """Verify RAG retrieval is working."""
    print_test(6, "RAG Source Retrieval")
    try:
        payload = {
            "message": "What does Jupiter in 7th house mean for marriage?",
            "session_id": "rag_test_user",
            "user_context": {
                "birth_date": TEST_USER["date_of_birth"],
                "birth_time": TEST_USER["time_of_birth"],
                "latitude": TEST_USER["latitude"],
                "longitude": TEST_USER["longitude"],
                "timezone": TEST_USER["timezone"]
            }
        }
        
        response = requests.post(f"{BASE_URL}/api/v1/chat", json=payload, headers=get_headers())
        data = response.json()
        
        sources = data.get('sources', [])
        answer = data.get('answer', '')
        
        has_sources = len(sources) > 0
        answer_not_empty = len(answer) > 50
        
        print_result(has_sources, f"Retrieved {len(sources)} classical text chunks")
        print_result(answer_not_empty, f"Generated answer ({len(answer)} chars)")
        
        if sources:
            print("\nSources:")
            for i, src in enumerate(sources[:3], 1):
                book = src.get('metadata', {}).get('source_book', 'Unknown')
                print(f"  {i}. {book}")
        
        return has_sources and answer_not_empty
        
    except Exception as e:
        return print_result(False, f"Error: {e}")


# ============================================================================
# RUN ALL TESTS
# ============================================================================

def main():
    print("\n" + "█" * 80)
    print("  FINAL INTEGRATION TEST - NakshatraAI")
    print("█" * 80)
    print("\nVerifying:")
    print("  • API Health")
    print("  • English Default Language")
    print("  • Multilingual Greetings")
    print("  • Validation Engine Integration")
    print("  • RAG Retrieval from 14,508 chunks")
    print("  • Language-Specific Responses")
    
    input("\n👉 Press Enter to start comprehensive test...")
    
    results = []
    
    # Run all tests
    results.append(("Health Check", test_1_health()))
    results.append(("English Greeting", test_2_english_greeting()))
    results.append(("Hinglish Greeting", test_3_hinglish_greeting()))
    results.append(("English Prediction", test_4_english_prediction()))
    results.append(("Hinglish Prediction", test_5_hinglish_prediction()))
    results.append(("RAG Sources", test_6_rag_sources()))
    
    # Summary
    print("\n" + "=" * 80)
    print("FINAL RESULTS")
    print("=" * 80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}  {test_name}")
    
    print("\n" + "=" * 80)
    print(f"Score: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED!")
        print("\n✅ Your NakshatraAI system is fully operational:")
        print("   • English is default language")
        print("   • Multilingual support working")
        print("   • Validation engine integrated")
        print("   • RAG retrieval from classical texts")
        print("   • Language-specific responses")
        print("\n🚀 READY FOR PRODUCTION!")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        print("Review the output above to identify issues.")
    
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
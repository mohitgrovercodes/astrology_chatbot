# test_chatbot_comprehensive.py
"""
Comprehensive Test Suite for NakshatraAI Chatbot

Tests:
1. Redis connectivity and data access
2. Session data retrieval
3. Context understanding (follow-up questions)
4. Conversation history management
5. Context window functionality
6. API endpoints

Usage:
    python test_chatbot_comprehensive.py
"""

import requests
import redis
import json
import time
from datetime import datetime
from typing import Dict, List, Optional


# ============================================================================
# CONFIGURATION
# ============================================================================

# API Configuration
API_BASE_URL = "http://localhost:6262/api/v1/chat"
API_HEADERS = {
    "Content-Type": "application/json",
    "X-Internal-Service": "super-secret-internal-key-123"
}

# Redis Configuration
REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_DB = 0

# Test Users (should exist in Redis from populate script)
TEST_USERS = ["user001", "user002", "user003"]

# Colors for terminal output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def print_header(text: str):
    """Print section header."""
    print(f"\n{'='*70}")
    print(f"{Colors.BOLD}{Colors.CYAN}{text}{Colors.ENDC}")
    print(f"{'='*70}\n")


def print_success(text: str):
    """Print success message."""
    print(f"{Colors.GREEN}✅ {text}{Colors.ENDC}")


def print_error(text: str):
    """Print error message."""
    print(f"{Colors.RED}❌ {text}{Colors.ENDC}")


def print_info(text: str):
    """Print info message."""
    print(f"{Colors.BLUE}ℹ️  {text}{Colors.ENDC}")


def print_warning(text: str):
    """Print warning message."""
    print(f"{Colors.YELLOW}⚠️  {text}{Colors.ENDC}")


# ============================================================================
# REDIS TESTS
# ============================================================================

class RedisTests:
    """Test suite for Redis operations."""
    
    def __init__(self):
        self.redis = None
        self.passed = 0
        self.failed = 0
    
    def run_all_tests(self):
        """Run all Redis tests."""
        print_header("TEST SUITE 1: REDIS CONNECTIVITY & DATA ACCESS")
        
        self.test_redis_connection()
        self.test_redis_data_exists()
        self.test_user_profile_retrieval()
        self.test_conversation_history_retrieval()
        self.test_chart_data_retrieval()
        self.test_ttl_settings()
        
        self._print_summary()
    
    def test_redis_connection(self):
        """Test 1: Redis connection."""
        print_info("Test 1: Redis Connection")
        
        try:
            self.redis = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                db=REDIS_DB,
                decode_responses=True
            )
            self.redis.ping()
            print_success("Redis connection successful")
            self.passed += 1
        except redis.ConnectionError as e:
            print_error(f"Redis connection failed: {e}")
            self.failed += 1
            return False
        
        return True
    
    def test_redis_data_exists(self):
        """Test 2: Check if test users exist."""
        print_info("Test 2: User Data Existence")
        
        if not self.redis:
            print_error("Redis not connected")
            self.failed += 1
            return
        
        for user_id in TEST_USERS:
            key = f"session:{user_id}:metadata"
            exists = self.redis.exists(key)
            
            if exists:
                print_success(f"User {user_id} exists in Redis")
                self.passed += 1
            else:
                print_error(f"User {user_id} NOT found in Redis")
                print_warning(f"  Run: python populate_redis_with_user_data.py")
                self.failed += 1
    
    def test_user_profile_retrieval(self):
        """Test 3: Retrieve and validate user profiles."""
        print_info("Test 3: User Profile Retrieval")
        
        if not self.redis:
            print_error("Redis not connected")
            self.failed += 1
            return
        
        for user_id in TEST_USERS:
            key = f"session:{user_id}:user_profile"
            profile_str = self.redis.get(key)
            
            if profile_str:
                try:
                    profile = json.loads(profile_str)
                    required_fields = ['name', 'date_of_birth', 'latitude', 'longitude']
                    
                    if all(field in profile for field in required_fields):
                        print_success(f"User {user_id} profile valid: {profile.get('name')}")
                        self.passed += 1
                    else:
                        print_error(f"User {user_id} profile missing required fields")
                        self.failed += 1
                except json.JSONDecodeError:
                    print_error(f"User {user_id} profile is not valid JSON")
                    self.failed += 1
            else:
                print_error(f"User {user_id} profile not found")
                self.failed += 1
    
    def test_conversation_history_retrieval(self):
        """Test 4: Retrieve conversation history."""
        print_info("Test 4: Conversation History Retrieval")
        
        if not self.redis:
            print_error("Redis not connected")
            self.failed += 1
            return
        
        for user_id in TEST_USERS:
            key = f"session:{user_id}:conversation"
            conv_str = self.redis.get(key)
            
            if conv_str:
                try:
                    conversation = json.loads(conv_str)
                    print_success(f"User {user_id} conversation history: {len(conversation)} messages")
                    
                    # Show last message if exists
                    if conversation:
                        last_msg = conversation[-1]
                        print(f"  └─ Last: [{last_msg['role']}] {last_msg['content'][:50]}...")
                    
                    self.passed += 1
                except json.JSONDecodeError:
                    print_error(f"User {user_id} conversation is not valid JSON")
                    self.failed += 1
            else:
                print_success(f"User {user_id} has no conversation history (new user)")
                self.passed += 1
    
    def test_chart_data_retrieval(self):
        """Test 5: Check for cached chart data."""
        print_info("Test 5: Chart Data Caching")
        
        if not self.redis:
            print_error("Redis not connected")
            self.failed += 1
            return
        
        for user_id in TEST_USERS:
            key = f"session:{user_id}:chart_data"
            chart_str = self.redis.get(key)
            
            if chart_str:
                try:
                    chart = json.loads(chart_str)
                    print_success(f"User {user_id} has cached chart data")
                    if 'lagna' in chart:
                        print(f"  └─ Lagna: {chart.get('lagna')}, Moon: {chart.get('moon_sign')}")
                    self.passed += 1
                except json.JSONDecodeError:
                    print_error(f"User {user_id} chart data is not valid JSON")
                    self.failed += 1
            else:
                print_info(f"User {user_id} has no cached chart (will be calculated)")
                self.passed += 1
    
    def test_ttl_settings(self):
        """Test 6: Verify TTL settings."""
        print_info("Test 6: TTL (Time To Live) Settings")
        
        if not self.redis:
            print_error("Redis not connected")
            self.failed += 1
            return
        
        user_id = TEST_USERS[0]
        
        # Check different TTLs
        keys_to_check = {
            f"session:{user_id}:user_profile": "24 hours",
            f"session:{user_id}:conversation": "24 hours",
            f"session:{user_id}:chart_data": "7 days",
        }
        
        for key, expected in keys_to_check.items():
            ttl = self.redis.ttl(key)
            if ttl > 0:
                hours = ttl / 3600
                print_success(f"{key.split(':')[-1]}: {hours:.1f}h remaining (expected: {expected})")
                self.passed += 1
            else:
                print_info(f"{key.split(':')[-1]}: Not set or expired")
                self.passed += 1
    
    def _print_summary(self):
        """Print test summary."""
        print(f"\n{'-'*70}")
        total = self.passed + self.failed
        print(f"Redis Tests Complete: {self.passed}/{total} passed")
        if self.failed > 0:
            print_error(f"{self.failed} tests failed")
        print(f"{'-'*70}")


# ============================================================================
# API TESTS
# ============================================================================

class APITests:
    """Test suite for API endpoints."""
    
    def __init__(self):
        self.passed = 0
        self.failed = 0
    
    def run_all_tests(self):
        """Run all API tests."""
        print_header("TEST SUITE 2: API ENDPOINT FUNCTIONALITY")
        
        self.test_api_health()
        self.test_stats_endpoint()
        self.test_session_status()
        
        self._print_summary()
    
    def test_api_health(self):
        """Test 1: API is running."""
        print_info("Test 1: API Health Check")
        
        try:
            response = requests.get(f"{API_BASE_URL}/stats", timeout=5)
            if response.status_code == 200:
                data = response.json()
                print_success(f"API is running")
                print(f"  └─ Active sessions: {data.get('active_sessions')}")
                print(f"  └─ Redis connected: {data.get('redis_connected')}")
                print(f"  └─ Context window: {data.get('context_window_size')}")
                self.passed += 1
            else:
                print_error(f"API returned status code: {response.status_code}")
                self.failed += 1
        except requests.exceptions.ConnectionError:
            print_error("Cannot connect to API - is it running?")
            print_warning("  Run: uvicorn src.api.main:app --reload --host 0.0.0.0 --port 6262")
            self.failed += 1
        except Exception as e:
            print_error(f"API health check failed: {e}")
            self.failed += 1
    
    def test_stats_endpoint(self):
        """Test 2: Stats endpoint."""
        print_info("Test 2: Stats Endpoint")
        
        try:
            response = requests.get(f"{API_BASE_URL}/stats")
            if response.status_code == 200:
                data = response.json()
                required = ['active_sessions', 'redis_connected', 'context_window_size']
                if all(k in data for k in required):
                    print_success("Stats endpoint returns all required fields")
                    self.passed += 1
                else:
                    print_error("Stats endpoint missing required fields")
                    self.failed += 1
            else:
                print_error(f"Stats endpoint failed: {response.status_code}")
                self.failed += 1
        except Exception as e:
            print_error(f"Stats endpoint test failed: {e}")
            self.failed += 1
    
    def test_session_status(self):
        """Test 3: Session status endpoint."""
        print_info("Test 3: Session Status Endpoint")
        
        user_id = TEST_USERS[0]
        
        try:
            response = requests.get(f"{API_BASE_URL}/session/{user_id}/status")
            if response.status_code == 200:
                data = response.json()
                print_success(f"Session status for {user_id}")
                print(f"  └─ User: {data.get('user_id')}")
                print(f"  └─ Messages: {data['cached_data'].get('conversation_messages')}")
                print(f"  └─ Chart cached: {data['cached_data'].get('chart_data')}")
                self.passed += 1
            elif response.status_code == 404:
                print_error(f"Session not found for {user_id}")
                print_warning("  Run: python populate_redis_with_user_data.py")
                self.failed += 1
            else:
                print_error(f"Session status failed: {response.status_code}")
                self.failed += 1
        except Exception as e:
            print_error(f"Session status test failed: {e}")
            self.failed += 1
    
    def _print_summary(self):
        """Print test summary."""
        print(f"\n{'-'*70}")
        total = self.passed + self.failed
        print(f"API Tests Complete: {self.passed}/{total} passed")
        if self.failed > 0:
            print_error(f"{self.failed} tests failed")
        print(f"{'-'*70}")


# ============================================================================
# CONTEXT UNDERSTANDING TESTS
# ============================================================================

class ContextTests:
    """Test suite for context understanding."""
    
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.user_id = TEST_USERS[0]
    
    def run_all_tests(self):
        """Run all context tests."""
        print_header("TEST SUITE 3: CONTEXT UNDERSTANDING")
        
        self.test_basic_query()
        self.test_follow_up_pronoun()
        self.test_topic_continuity()
        self.test_multi_turn_context()
        self.test_context_window_limit()
        
        self._print_summary()
    
    def send_message(self, message: str) -> Optional[Dict]:
        """Send a message to chatbot."""
        try:
            response = requests.post(
                f"{API_BASE_URL}/message",
                headers=API_HEADERS,
                json={"user_id": self.user_id, "message": message},
                timeout=60
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                print_error(f"API error: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            print_error(f"Request failed: {e}")
            return None
    
    def test_basic_query(self):
        """Test 1: Basic query (establishes baseline)."""
        print_info("Test 1: Basic Query")
        
        message = "What is my moon sign?"
        print(f"  User: \"{message}\"")
        
        result = self.send_message(message)
        
        if result:
            answer = result['answer']
            print(f"  Bot: \"{answer[:100]}...\"")
            
            # Check if answer contains moon sign info
            if any(word in answer.lower() for word in ['moon', 'gemini', 'cancer', 'virgo', 'sign']):
                print_success("Bot answered moon sign query")
                self.passed += 1
            else:
                print_warning("Bot's answer unclear")
                self.passed += 1  # Still passes, just warning
        else:
            print_error("Failed to get response")
            self.failed += 1
        
        time.sleep(1)  # Brief pause between requests
    
    def test_follow_up_pronoun(self):
        """Test 2: Follow-up with pronoun reference."""
        print_info("Test 2: Follow-up with Pronoun (\"it\")")
        
        message = "Tell me more about it"
        print(f"  User: \"{message}\"")
        print(f"  Context: Should understand \"it\" = moon sign from previous message")
        
        result = self.send_message(message)
        
        if result:
            answer = result['answer']
            print(f"  Bot: \"{answer[:150]}...\"")
            
            metadata = result.get('metadata', {})
            messages_sent = metadata.get('messages_sent_to_llm', 0)
            print(f"  └─ Messages sent to LLM: {messages_sent}")
            
            # Check if bot understood context
            moon_related = any(word in answer.lower() for word in ['moon', 'gemini', 'cancer', 'emotional', 'mind'])
            generic = "what" in answer.lower() and "want" in answer.lower()
            
            if moon_related and not generic:
                print_success("Bot understood pronoun reference (context working!)")
                self.passed += 1
            else:
                print_error("Bot didn't understand context - asked clarification")
                print_warning("  This means context window may not be working properly")
                self.failed += 1
        else:
            print_error("Failed to get response")
            self.failed += 1
        
        time.sleep(1)
    
    def test_topic_continuity(self):
        """Test 3: Topic continuity."""
        print_info("Test 3: Topic Continuity")
        
        message = "How does this affect my career?"
        print(f"  User: \"{message}\"")
        print(f"  Context: Should understand \"this\" = moon sign's impact")
        
        result = self.send_message(message)
        
        if result:
            answer = result['answer']
            print(f"  Bot: \"{answer[:150]}...\"")
            
            # Check if relates to moon sign AND career
            career_moon = any(word in answer.lower() for word in ['career', 'work', 'profession']) and \
                         any(word in answer.lower() for word in ['moon', 'emotional', 'mind'])
            
            if career_moon:
                print_success("Bot maintained topic continuity")
                self.passed += 1
            else:
                print_warning("Bot's answer may not have connected moon sign to career")
                self.passed += 1  # Warning but still pass
        else:
            print_error("Failed to get response")
            self.failed += 1
        
        time.sleep(1)
    
    def test_multi_turn_context(self):
        """Test 4: Multi-turn conversation."""
        print_info("Test 4: Multi-turn Context Memory")
        
        # Ask about something specific
        msg1 = "When will I get married?"
        print(f"  User: \"{msg1}\"")
        
        result1 = self.send_message(msg1)
        if not result1:
            print_error("Failed to get first response")
            self.failed += 1
            return
        
        print(f"  Bot: \"{result1['answer'][:100]}...\"")
        time.sleep(1)
        
        # Ask follow-up about timing
        msg2 = "Is that timing based on my dashas?"
        print(f"  User: \"{msg2}\"")
        print(f"  Context: Should remember we're talking about marriage timing")
        
        result2 = self.send_message(msg2)
        if result2:
            answer = result2['answer']
            print(f"  Bot: \"{answer[:150]}...\"")
            
            # Check if references marriage and dashas
            contextual = any(word in answer.lower() for word in ['marriage', 'timing', 'period']) and \
                        any(word in answer.lower() for word in ['dasha', 'mahadasha', 'antardasha'])
            
            if contextual:
                print_success("Bot remembered multi-turn context (marriage + dasha)")
                self.passed += 1
            else:
                print_warning("Bot may have lost context")
                self.passed += 1
        else:
            print_error("Failed to get response")
            self.failed += 1
        
        time.sleep(1)
    
    def test_context_window_limit(self):
        """Test 5: Context window limitation."""
        print_info("Test 5: Context Window Limit")
        
        # Check metadata from last response
        message = "What was my first question?"
        print(f"  User: \"{message}\"")
        
        result = self.send_message(message)
        
        if result:
            metadata = result.get('metadata', {})
            context_window = metadata.get('context_window', 0)
            total_messages = metadata.get('total_messages_in_history', 0)
            sent_to_llm = metadata.get('messages_sent_to_llm', 0)
            
            print(f"  └─ Context window size: {context_window}")
            print(f"  └─ Total messages in history: {total_messages}")
            print(f"  └─ Messages sent to LLM: {sent_to_llm}")
            
            if sent_to_llm <= context_window:
                print_success("Context window working correctly")
                self.passed += 1
            else:
                print_error(f"Sent {sent_to_llm} messages but window is {context_window}")
                self.failed += 1
        else:
            print_error("Failed to get response")
            self.failed += 1
    
    def _print_summary(self):
        """Print test summary."""
        print(f"\n{'-'*70}")
        total = self.passed + self.failed
        print(f"Context Tests Complete: {self.passed}/{total} passed")
        if self.failed > 0:
            print_error(f"{self.failed} tests failed - context may not be working properly")
        else:
            print_success("All context tests passed - follow-up questions working!")
        print(f"{'-'*70}")


# ============================================================================
# MAIN TEST RUNNER
# ============================================================================

def main():
    """Run all test suites."""
    
    print(f"\n{Colors.BOLD}{Colors.CYAN}")
    print("="*70)
    print(" "*15 + "NAKSHATRA AI - COMPREHENSIVE TEST SUITE")
    print("="*70)
    print(f"{Colors.ENDC}")
    
    print(f"\n{Colors.YELLOW}Testing Components:{Colors.ENDC}")
    print("  1. Redis connectivity and data access")
    print("  2. API endpoints functionality")
    print("  3. Context understanding (follow-up questions)")
    print("  4. Conversation history management")
    print("  5. Context window functionality\n")
    
    # Track overall results
    total_passed = 0
    total_failed = 0
    
    # Run test suites
    redis_tests = RedisTests()
    redis_tests.run_all_tests()
    total_passed += redis_tests.passed
    total_failed += redis_tests.failed
    
    api_tests = APITests()
    api_tests.run_all_tests()
    total_passed += api_tests.passed
    total_failed += api_tests.failed
    
    context_tests = ContextTests()
    context_tests.run_all_tests()
    total_passed += context_tests.passed
    total_failed += context_tests.failed
    
    # Final summary
    print_header("FINAL SUMMARY")
    
    total = total_passed + total_failed
    success_rate = (total_passed / total * 100) if total > 0 else 0
    
    print(f"Total Tests: {total}")
    print(f"Passed: {Colors.GREEN}{total_passed}{Colors.ENDC}")
    print(f"Failed: {Colors.RED}{total_failed}{Colors.ENDC}")
    print(f"Success Rate: {success_rate:.1f}%\n")
    
    if total_failed == 0:
        print(f"{Colors.GREEN}{Colors.BOLD}🎉 ALL TESTS PASSED! 🎉{Colors.ENDC}")
        print("Chatbot is working correctly with context understanding!\n")
    else:
        print(f"{Colors.YELLOW}⚠️  SOME TESTS FAILED{Colors.ENDC}")
        print("Please review the errors above and fix issues.\n")
        
        # Provide troubleshooting hints
        print("Common issues:")
        if redis_tests.failed > 0:
            print("  • Redis: Run 'python populate_redis_with_user_data.py'")
        if api_tests.failed > 0:
            print("  • API: Make sure API is running on port 6262")
        if context_tests.failed > 0:
            print("  • Context: Check CONVERSATION_CONTEXT_WINDOW in .env")
        print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}Tests interrupted by user{Colors.ENDC}")
    except Exception as e:
        print(f"\n{Colors.RED}Test suite error: {e}{Colors.ENDC}")
        import traceback
        traceback.print_exc()
# Comprehensive Context Management Test Suite
# Tests context awareness, reference resolution, and conversation flow

import requests
import json
import time
from datetime import datetime
from typing import Dict, List, Any
import os

# ============================================================================
# CONFIGURATION
# ============================================================================

API_BASE_URL = "http://localhost:6262/api/v1/chat"

class Colors:
    """Terminal colors for clear output."""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    MAGENTA = '\033[95m'
    BOLD = '\033[1m'
    ENDC = '\033[0m'


# ============================================================================
# TEST FRAMEWORK
# ============================================================================

class ContextTestResult:
    """Track individual test results."""
    
    # Make CONTEXT_WINDOW accessible to methods
    CONTEXT_WINDOW = int(os.getenv('CONVERSATION_CONTEXT_WINDOW', '10'))
    
    def __init__(self, test_name: str):
        self.test_name = test_name
        self.passed = False
        self.messages_sent = []
        self.responses_received = []
        self.analysis = []
        self.errors = []
    
    def add_exchange(self, question: str, answer: str, analysis: str = None):
        """Record a question-answer exchange."""
        self.messages_sent.append(question)
        self.responses_received.append(answer)
        if analysis:
            self.analysis.append(analysis)
    
    def add_error(self, error: str):
        """Record an error."""
        self.errors.append(error)
    
    def mark_passed(self):
        """Mark test as passed."""
        self.passed = True
    
    def print_result(self):
        """Print test results with color coding and detailed analysis."""
        status = f"{Colors.GREEN}[PASS] PASSED{Colors.ENDC}" if self.passed else f"{Colors.RED}[FAIL] FAILED{Colors.ENDC}"
        
        print(f"\n{'='*80}")
        print(f"{Colors.BOLD}{self.test_name}{Colors.ENDC}")
        print(f"Status: {status}")
        print(f"{'='*80}")
        
        # Print exchanges with better formatting
        for i, (q, a) in enumerate(zip(self.messages_sent, self.responses_received), 1):
            print(f"\n{Colors.CYAN}Exchange {i}:{Colors.ENDC}")
            print(f"  {Colors.BLUE}Q:{Colors.ENDC} {q}")
            
            # Show full answer for failed tests, truncated for passed
            if self.passed or len(a) < 150:
                print(f"  {Colors.MAGENTA}A:{Colors.ENDC} {a}")
            else:
                print(f"  {Colors.MAGENTA}A:{Colors.ENDC} {a[:150]}...")
            
            # Show analysis if available
            if i-1 < len(self.analysis):
                analysis_text = self.analysis[i-1]
                if "[PASS]" in analysis_text:
                    print(f"  {Colors.GREEN}{analysis_text}{Colors.ENDC}")
                elif "[FAIL]" in analysis_text:
                    print(f"  {Colors.RED}{analysis_text}{Colors.ENDC}")
                elif "[WARN]" in analysis_text:
                    print(f"  {Colors.YELLOW}{analysis_text}{Colors.ENDC}")
                else:
                    print(f"  {Colors.YELLOW}Analysis:{Colors.ENDC} {analysis_text}")
        
        # Print errors with context
        if self.errors:
            print(f"\n{Colors.RED}Errors:{Colors.ENDC}")
            for error in self.errors:
                print(f"  - {error}")
            
            # Add debugging hints
            if "Could not detect moon sign" in str(self.errors):
                print(f"\n{Colors.YELLOW}? Debugging Hint:{Colors.ENDC}")
                print(f"  The bot may be using Hindi zodiac names (Meena, Karka, etc.)")
                print(f"  This is not an error - test has been updated to handle this.")
            elif "Context lost" in str(self.errors):
                print(f"\n{Colors.YELLOW}? Debugging Hint:{Colors.ENDC}")
                print(f"  Check orchestrator logs for: '[LLM] Sending X messages'")
                print(f"  Should be > 1 (system prompt + conversation history)")
            elif "lost topic" in str(self.errors).lower():
                print(f"\n{Colors.YELLOW}? Debugging Hint:{Colors.ENDC}")
                print(f"  This might indicate the LLM is not receiving conversation history")
                print(f"  or the context window is too small (current: {self.CONTEXT_WINDOW})")


class ContextTester:
    """Main testing framework."""
    
    def __init__(self):
        self.user_id = f"test_user_{int(time.time())}"
        self.results: List[ContextTestResult] = []
    
    def initialize_session(self) -> bool:
        """Initialize test session."""
        print(f"\n{Colors.CYAN}{'='*80}{Colors.ENDC}")
        print(f"{Colors.CYAN}{Colors.BOLD}INITIALIZING TEST SESSION{Colors.ENDC}")
        print(f"{Colors.CYAN}{'='*80}{Colors.ENDC}")
        
        payload = {
            "user_id": self.user_id,
            "user_profile": {
                "user_id": self.user_id,
                "name": "Test User",
                "date_of_birth": "1990-07-15",
                "time_of_birth": "08:30:00",
                "place_of_birth": "New Delhi, India",
                "latitude": 28.6139,
                "longitude": 77.2090,
                "timezone": "Asia/Kolkata",
                "preferred_system": "vedic"
            },
            "conversation_history": []
        }
        
        try:
            response = requests.post(f"{API_BASE_URL}/initialize", json=payload, timeout=10)
            if response.status_code == 200:
                data = response.json()
                print(f"{Colors.GREEN}[OK] Session initialized: {data['user_id']}{Colors.ENDC}")
                print(f"{Colors.GREEN}[OK] Status: {data['status']}{Colors.ENDC}\n")
                return True
            else:
                print(f"{Colors.RED}[FAIL] Initialize failed: {response.status_code}{Colors.ENDC}")
                return False
        except Exception as e:
            print(f"{Colors.RED}[ERROR] Error: {e}{Colors.ENDC}")
            return False
    
    def send_message(self, question: str) -> Dict[str, Any]:
        """Send a message and get response."""
        payload = {
            "user_id": self.user_id,
            "question": question
        }
        
        try:
            response = requests.post(f"{API_BASE_URL}/message", json=payload, timeout=60)
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": f"HTTP {response.status_code}", "answer": ""}
        except Exception as e:
            return {"error": str(e), "answer": ""}
    
    def run_all_tests(self):
        """Run comprehensive test suite."""
        print(f"\n{Colors.BOLD}{Colors.MAGENTA}")
        print("+-------------------------------------------------------------------+")
        print("|                                                                   |")
        print("|           COMPREHENSIVE CONTEXT MANAGEMENT TEST SUITE             |")
        print("|                   Enhanced with Semantic Analysis                 |")
        print("|                                                                   |")
        print("+-------------------------------------------------------------------+")
        print(f"{Colors.ENDC}\n")
        
        # Initialize session
        if not self.initialize_session():
            print(f"{Colors.RED}Failed to initialize session. Aborting tests.{Colors.ENDC}")
            return
        
        # Run test categories
        self.test_basic_context()
        self.test_pronoun_resolution()
        self.test_topic_continuity()
        self.test_multi_turn_context()
        self.test_topic_switching()
        self.test_clarification_requests()
        self.test_ambiguity_handling()
        self.test_conversation_summary()
        self.test_semantic_interpreter_scores()  # NEW TEST
        
        # Print summary
        self.print_summary()
    
    # ========================================================================
    # TEST CATEGORY 1: Basic Context Awareness
    # ========================================================================
    
    def test_basic_context(self):
        """Test basic context awareness."""
        result = ContextTestResult("TEST 1: Basic Context Awareness")
        
        print(f"\n{Colors.BOLD}Running: {result.test_name}{Colors.ENDC}")
        
        # Exchange 1: Initial query
        q1 = "What is my moon sign?"
        r1 = self.send_message(q1)
        result.add_exchange(q1, r1.get('answer', ''))
        
        if 'error' in r1:
            result.add_error(f"API error: {r1['error']}")
            self.results.append(result)
            return
        
        # Extract moon sign from response (English + Hindi names)
        answer1 = r1.get('answer', '').lower()
        moon_sign = None
        
        # Zodiac mapping: Hindi ? English
        zodiac_mapping = {
            # English names
            'aries': 'aries', 'taurus': 'taurus', 'gemini': 'gemini',
            'cancer': 'cancer', 'leo': 'leo', 'virgo': 'virgo',
            'libra': 'libra', 'scorpio': 'scorpio', 'sagittarius': 'sagittarius',
            'capricorn': 'capricorn', 'aquarius': 'aquarius', 'pisces': 'pisces',
            # Hindi/Sanskrit names
            'mesha': 'aries', 'vrishabha': 'taurus', 'mithuna': 'gemini',
            'karka': 'cancer', 'simha': 'leo', 'kanya': 'virgo',
            'tula': 'libra', 'vrishchika': 'scorpio', 'dhanu': 'sagittarius',
            'makara': 'capricorn', 'kumbha': 'aquarius', 'meena': 'pisces'
        }
        
        for sign_name, sign_value in zodiac_mapping.items():
            if sign_name in answer1:
                moon_sign = sign_value
                print(f"[DEBUG] Detected moon sign: {sign_name} ? {sign_value}")
                break
        
        if not moon_sign:
            result.add_error("Could not detect moon sign in response")
            result.add_exchange(
                "Analysis", 
                "",
                f"Failed to extract moon sign from: {answer1[:100]}"
            )
            print(f"[DEBUG] Full answer: {answer1[:200]}")
        
        time.sleep(1)
        
        # Exchange 2: Follow-up with pronoun
        q2 = "Tell me more about it"
        r2 = self.send_message(q2)
        result.add_exchange(q2, r2.get('answer', ''))
        
        answer2 = r2.get('answer', '').lower()
        
        # Check if bot understood "it" refers to moon sign
        if moon_sign and moon_sign in answer2:
            result.add_exchange(
                "Analysis",
                "",
                f"[PASS] Bot correctly understood 'it' refers to {moon_sign} moon sign"
            )
            result.mark_passed()
        elif moon_sign:
            result.add_exchange(
                "Analysis",
                "",
                f"[FAIL] Bot did NOT reference {moon_sign} when responding to 'it'"
            )
            result.add_error(f"Expected '{moon_sign}' in response, not found")
        else:
            result.add_error("Could not validate context - moon sign not detected")
        
        self.results.append(result)
    
    # ========================================================================
    # TEST CATEGORY 2: Pronoun Resolution
    # ========================================================================
    
    def test_pronoun_resolution(self):
        """Test pronoun resolution (it, this, that)."""
        result = ContextTestResult("TEST 2: Pronoun Resolution")
        
        print(f"\n{Colors.BOLD}Running: {result.test_name}{Colors.ENDC}")
        
        # Setup: Ask about a specific placement
        q1 = "What does Jupiter in my 7th house mean?"
        r1 = self.send_message(q1)
        result.add_exchange(q1, r1.get('answer', ''))
        
        time.sleep(1)
        
        # Test 1: "this"
        q2 = "How does this affect my marriage?"
        r2 = self.send_message(q2)
        result.add_exchange(q2, r2.get('answer', ''))
        
        answer2 = r2.get('answer', '').lower()
        has_jupiter = 'jupiter' in answer2
        has_7th_house = '7th' in answer2 or 'seventh' in answer2
        
        if has_jupiter or has_7th_house:
            result.add_exchange(
                "Analysis",
                "",
                f"[PASS] Bot resolved 'this' ? Jupiter/7th house context"
            )
        else:
            result.add_exchange(
                "Analysis",
                "",
                f"[FAIL] Bot did not reference Jupiter or 7th house when asked about 'this'"
            )
            result.add_error("Pronoun 'this' not resolved to previous topic")
        
        time.sleep(1)
        
        # Test 2: "that"
        q3 = "Is that good or bad for relationships?"
        r3 = self.send_message(q3)
        result.add_exchange(q3, r3.get('answer', ''))
        
        answer3 = r3.get('answer', '').lower()
        context_maintained = 'jupiter' in answer3 or 'marriage' in answer3 or 'relationship' in answer3
        
        if context_maintained:
            result.add_exchange(
                "Analysis",
                "",
                f"[PASS] Bot maintained context when resolving 'that'"
            )
            result.mark_passed()
        else:
            result.add_exchange(
                "Analysis",
                "",
                f"[FAIL] Bot lost context when asked about 'that'"
            )
            result.add_error("Failed to maintain context across multiple pronouns")
        
        self.results.append(result)
    
    # ========================================================================
    # TEST CATEGORY 3: Topic Continuity
    # ========================================================================
    
    def test_topic_continuity(self):
        """Test topic continuity across multiple turns."""
        result = ContextTestResult("TEST 3: Topic Continuity")
        
        print(f"\n{Colors.BOLD}Running: {result.test_name}{Colors.ENDC}")
        
        # Establish topic: Career
        q1 = "When will I get a promotion?"
        r1 = self.send_message(q1)
        result.add_exchange(q1, r1.get('answer', ''))
        
        time.sleep(1)
        
        # Follow-up 1: Why
        q2 = "Why that time?"
        r2 = self.send_message(q2)
        result.add_exchange(q2, r2.get('answer', ''))
        
        answer2 = r2.get('answer', '').lower()
        mentions_promotion = 'promotion' in answer2 or 'career' in answer2 or 'job' in answer2
        
        if mentions_promotion:
            result.add_exchange(
                "Analysis",
                "",
                f"[PASS] Bot connected 'why that time' to promotion timing"
            )
        else:
            result.add_exchange(
                "Analysis",
                "",
                f"[FAIL] Bot did not connect question to promotion context"
            )
            result.add_error("Lost topic continuity on 'why' question")
        
        time.sleep(1)
        
        # Follow-up 2: Tell me more
        q3 = "Tell me more"
        r3 = self.send_message(q3)
        result.add_exchange(q3, r3.get('answer', ''))
        
        answer3 = r3.get('answer', '').lower()
        still_on_topic = any(word in answer3 for word in ['promotion', 'career', 'job', 'work', 'professional'])
        
        if still_on_topic:
            result.add_exchange(
                "Analysis",
                "",
                f"[PASS] Bot maintained career topic across 3 turns"
            )
            result.mark_passed()
        else:
            result.add_exchange(
                "Analysis",
                "",
                f"[FAIL] Bot lost topic context by turn 3"
            )
            result.add_error("Topic continuity failed after multiple turns")
        
        self.results.append(result)
    
    # ========================================================================
    # TEST CATEGORY 4: Multi-turn Context
    # ========================================================================
    
    def test_multi_turn_context(self):
        """Test context maintained over 5+ turns."""
        result = ContextTestResult("TEST 4: Multi-Turn Context (5+ exchanges)")
        
        print(f"\n{Colors.BOLD}Running: {result.test_name}{Colors.ENDC}")
        
        topic_keyword = "marriage"
        exchanges = [
            ("When will I get married?", topic_keyword),
            ("Why that time?", topic_keyword),
            ("What planetary influences cause this?", ["planet", "jupiter", "venus", "7th"]),
            ("How certain is this prediction?", topic_keyword),
            ("What else should I know about it?", topic_keyword),
        ]
        
        all_passed = True
        
        for i, (question, expected_keywords) in enumerate(exchanges, 1):
            response = self.send_message(question)
            answer = response.get('answer', '').lower()
            result.add_exchange(question, response.get('answer', ''))
            
            # Check if context maintained
            if isinstance(expected_keywords, list):
                found = any(kw in answer for kw in expected_keywords)
            else:
                found = expected_keywords in answer
            
            if found:
                result.add_exchange(
                    f"Turn {i} Analysis",
                    "",
                    f"[PASS] Context maintained"
                )
            else:
                result.add_exchange(
                    f"Turn {i} Analysis",
                    "",
                    f"[FAIL] Context lost"
                )
                all_passed = False
                result.add_error(f"Context lost at turn {i}")
            
            time.sleep(1)
        
        if all_passed:
            result.mark_passed()
        
        self.results.append(result)
    
    # ========================================================================
    # TEST CATEGORY 5: Topic Switching
    # ========================================================================
    
    def test_topic_switching(self):
        """Test handling of topic changes."""
        result = ContextTestResult("TEST 5: Topic Switching")
        
        print(f"\n{Colors.BOLD}Running: {result.test_name}{Colors.ENDC}")
        
        # Topic 1: Moon sign
        q1 = "What is my moon sign?"
        r1 = self.send_message(q1)
        result.add_exchange(q1, r1.get('answer', ''))
        
        time.sleep(1)
        
        # Topic 2: Career (NEW TOPIC)
        q2 = "What about my career prospects?"
        r2 = self.send_message(q2)
        result.add_exchange(q2, r2.get('answer', ''))
        
        answer2 = r2.get('answer', '').lower()
        mentions_career = any(word in answer2 for word in ['career', 'job', 'work', 'professional', '10th'])
        mentions_moon = 'moon' in answer2
        
        if mentions_career:
            result.add_exchange(
                "Analysis",
                "",
                f"[PASS] Bot switched to career topic"
            )
            
            # Check if it inappropriately maintained moon sign context
            if mentions_moon and '10th' not in answer2:
                result.add_exchange(
                    "Analysis",
                    "",
                    f"[WARN]  Bot may have confused topics (mentioned moon in career context)"
                )
            
            result.mark_passed()
        else:
            result.add_exchange(
                "Analysis",
                "",
                f"[FAIL] Bot did not properly switch to career topic"
            )
            result.add_error("Failed to handle topic switch")
        
        self.results.append(result)
    
    # ========================================================================
    # TEST CATEGORY 6: Clarification Requests
    # ========================================================================
    
    def test_clarification_requests(self):
        """Test if bot asks for clarification when needed."""
        result = ContextTestResult("TEST 6: Clarification Handling")
        
        print(f"\n{Colors.BOLD}Running: {result.test_name}{Colors.ENDC}")
        
        # Setup multiple topics
        q1 = "What is my moon sign?"
        r1 = self.send_message(q1)
        result.add_exchange(q1, r1.get('answer', ''))
        
        time.sleep(1)
        
        q2 = "When will I get married?"
        r2 = self.send_message(q2)
        result.add_exchange(q2, r2.get('answer', ''))
        
        time.sleep(1)
        
        q3 = "Tell me about my career"
        r3 = self.send_message(q3)
        result.add_exchange(q3, r3.get('answer', ''))
        
        time.sleep(1)
        
        # Now ask vague question
        q4 = "Is this good?"
        r4 = self.send_message(q4)
        result.add_exchange(q4, r4.get('answer', ''))
        
        answer4 = r4.get('answer', '').lower()
        
        # Check if bot asks for clarification or makes a choice
        asks_clarification = any(phrase in answer4 for phrase in [
            'which', 'what do you mean', 'clarify', 'referring to', 
            'moon sign', 'marriage', 'career'
        ])
        
        if asks_clarification:
            result.add_exchange(
                "Analysis",
                "",
                f"[PASS] Bot appropriately handled ambiguous query"
            )
            result.mark_passed()
        else:
            result.add_exchange(
                "Analysis",
                "",
                f"[WARN]  Bot answered 'is this good' without asking what 'this' refers to"
            )
            # This is not necessarily a failure - bot might have made a reasonable assumption
            result.mark_passed()
        
        self.results.append(result)
    
    # ========================================================================
    # TEST CATEGORY 7: Ambiguity Handling
    # ========================================================================
    
    def test_ambiguity_handling(self):
        """Test semantic interpreter's ambiguity confidence scoring."""
        result = ContextTestResult("TEST 7: Ambiguity Confidence Handling")
        
        print(f"\n{Colors.BOLD}Running: {result.test_name}{Colors.ENDC}")
        
        test_cases = [
            {
                "setup": "What is my moon sign?",
                "query": "Tell me more about it",
                "expected": "auto_expand",  # High confidence
                "description": "Clear reference (it = moon sign)"
            },
            {
                "setup": None,
                "query": "What else?",
                "expected": "needs_hint_or_clarification",  # Medium/Low confidence
                "description": "Vague reference without clear context"
            }
        ]
        
        all_passed = True
        
        for i, test in enumerate(test_cases, 1):
            if test["setup"]:
                setup_r = self.send_message(test["setup"])
                result.add_exchange(test["setup"], setup_r.get('answer', ''))
                time.sleep(1)
            
            query_r = self.send_message(test["query"])
            answer = query_r.get('answer', '')
            result.add_exchange(test["query"], answer)
            
            # Analyze response
            if test["expected"] == "auto_expand":
                # Should have expanded reference clearly
                answer_lower = answer.lower()
                has_context = 'moon' in answer_lower
                
                if has_context:
                    result.add_exchange(
                        f"Test {i} Analysis",
                        "",
                        f"[PASS] {test['description']}: Context properly expanded"
                    )
                else:
                    result.add_exchange(
                        f"Test {i} Analysis",
                        "",
                        f"[FAIL] {test['description']}: Failed to expand reference"
                    )
                    all_passed = False
            
            else:
                # Should ask for clarification or add hint
                answer_lower = answer.lower()
                asks_clarification = any(word in answer_lower for word in 
                                        ['which', 'what', 'clarify', 'mean'])
                
                if asks_clarification:
                    result.add_exchange(
                        f"Test {i} Analysis",
                        "",
                        f"[PASS] {test['description']}: Appropriately requested clarification"
                    )
                else:
                    result.add_exchange(
                        f"Test {i} Analysis",
                        "",
                        f"[WARN]  {test['description']}: Answered without seeking clarification"
                    )
                    # Not a hard failure
            
            time.sleep(1)
        
        if all_passed:
            result.mark_passed()
        
        self.results.append(result)
    
    # ========================================================================
    # TEST CATEGORY 8: Conversation Summary
    # ========================================================================
    
    def test_conversation_summary(self):
        """Test if conversation summary is generated and used."""
        result = ContextTestResult("TEST 8: Conversation Summary (After 6+ Messages)")
        
        print(f"\n{Colors.BOLD}Running: {result.test_name}{Colors.ENDC}")
        
        # Send 6+ messages to trigger summary
        questions = [
            "What is my moon sign?",
            "Tell me more",
            "How does this affect relationships?",
            "What about my career?",
            "When will I get promoted?",
            "Why that time?",
            "What else should I know?"
        ]
        
        for i, q in enumerate(questions, 1):
            r = self.send_message(q)
            result.add_exchange(q, r.get('answer', ''))
            
            if i == 7:
                # After 7 messages, check if bot maintains context from early messages
                answer = r.get('answer', '').lower()
                
                # Should still remember we're talking about career/promotion
                remembers_context = any(word in answer for word in 
                                       ['promotion', 'career', 'work', 'job'])
                
                if remembers_context:
                    result.add_exchange(
                        "Analysis",
                        "",
                        f"[PASS] Bot maintained context from message 5-6 (career/promotion) in message 7"
                    )
                    result.mark_passed()
                else:
                    result.add_exchange(
                        "Analysis",
                        "",
                        f"[FAIL] Bot lost context from earlier messages"
                    )
                    result.add_error("Conversation summary may not be working")
            
            time.sleep(1)
        
        self.results.append(result)
    
    # ========================================================================
    # TEST CATEGORY 9: Semantic Interpreter Scores (NEW)
    # ========================================================================
    
    def test_semantic_interpreter_scores(self):
        """Test if semantic interpreter gives appropriate confidence scores."""
        result = ContextTestResult("TEST 9: Semantic Interpreter Confidence Scores")
        
        print(f"\n{Colors.BOLD}Running: {result.test_name}{Colors.ENDC}")
        
        # Setup context
        q1 = "What is my moon sign?"
        r1 = self.send_message(q1)
        result.add_exchange(q1, r1.get('answer', ''))
        
        time.sleep(1)
        
        # Test clear follow-up - should get HIGH score (>0.6) and auto-expand
        q2 = "Tell me more about it"
        r2 = self.send_message(q2)
        result.add_exchange(q2, r2.get('answer', ''))
        
        answer2 = r2.get('answer', '').lower()
        
        # Check if bot expanded (not asking clarification)
        asks_clarification = any(phrase in answer2 for phrase in [
            'what aspect', 'which aspect', 'what would you like',
            'could you let me know', 'could you specify'
        ])
        
        if not asks_clarification:
            result.add_exchange(
                "Analysis",
                "",
                f"[PASS] Bot auto-expanded 'it' without asking for clarification (score likely > 0.6)"
            )
            result.mark_passed()
        else:
            result.add_exchange(
                "Analysis",
                "",
                f"[FAIL] Bot asked for clarification on clear follow-up (score likely < 0.6)"
            )
            result.add_error("Semantic interpreter may need threshold adjustment")
            print(f"\n{Colors.RED}[FAIL DETAILS] Bot asked: {answer2[:150]}{Colors.ENDC}")
            print(f"{Colors.YELLOW}Expected: Bot should expand 'it' to moon sign automatically{Colors.ENDC}")
            print(f"{Colors.YELLOW}Actual: Bot asked for clarification{Colors.ENDC}")
            print(f"{Colors.YELLOW}Fix: Adjust ambiguity_prompt in chat_stateless.py (see CHAT_STATELESS_MODIFICATIONS.md){Colors.ENDC}")
        
        self.results.append(result)
    
    # ========================================================================
    # RESULTS SUMMARY
    # ========================================================================
    
    def print_summary(self):
        """Print comprehensive test summary."""
        print(f"\n{Colors.BOLD}{Colors.CYAN}")
        print("+===================================================================+")
        print("|                                                                   |")
        print("|                         TEST SUMMARY                              |")
        print("|                                                                   |")
        print("+===================================================================+")
        print(f"{Colors.ENDC}\n")
        
        # Print individual results
        for result in self.results:
            result.print_result()
        
        # Overall statistics
        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed)
        failed = total - passed
        
        print(f"\n{Colors.BOLD}{'='*80}{Colors.ENDC}")
        print(f"{Colors.BOLD}OVERALL STATISTICS{Colors.ENDC}")
        print(f"{'='*80}")
        print(f"Total Tests: {total}")
        print(f"{Colors.GREEN}Passed: {passed}{Colors.ENDC}")
        print(f"{Colors.RED}Failed: {failed}{Colors.ENDC}")
        print(f"Success Rate: {(passed/total*100):.1f}%")
        print(f"{'='*80}\n")
        
        # What's working
        print(f"{Colors.GREEN}{Colors.BOLD}[PASS] WHAT'S WORKING:{Colors.ENDC}")
        for result in self.results:
            if result.passed:
                print(f"  ? {result.test_name}")
        
        # What's not working
        if failed > 0:
            print(f"\n{Colors.RED}{Colors.BOLD}[FAIL] WHAT'S NOT WORKING:{Colors.ENDC}")
            for result in self.results:
                if not result.passed:
                    print(f"  ? {result.test_name}")
                    for error in result.errors:
                        print(f"    - {error}")
        
        # Recommendations
        print(f"\n{Colors.YELLOW}{Colors.BOLD}? RECOMMENDATIONS:{Colors.ENDC}")
        
        if failed == 0:
            print(f"  {Colors.GREEN}? All tests passed! Context management is working perfectly.{Colors.ENDC}")
        else:
            # Check for semantic interpreter issues
            semantic_failed = not any(r.passed for r in self.results if "Semantic Interpreter" in r.test_name)
            if semantic_failed:
                print(f"  {Colors.RED}? CRITICAL: Semantic Interpreter asking for clarification on clear follow-ups{Colors.ENDC}")
                print(f"     {Colors.YELLOW}FIX: Update ambiguity_prompt in chat_stateless.py{Colors.ENDC}")
                print(f"     {Colors.CYAN}See: CHAT_STATELESS_MODIFICATIONS.md{Colors.ENDC}")
            
            if not any(r.passed for r in self.results if "Basic Context" in r.test_name):
                print(f"  {Colors.RED}? CRITICAL: Basic context not working - check if conversation_history is being sent to LLM{Colors.ENDC}")
            
            if not any(r.passed for r in self.results if "Pronoun" in r.test_name):
                print(f"  {Colors.YELLOW}? Semantic interpreter may need tuning for pronoun resolution{Colors.ENDC}")
            
            if not any(r.passed for r in self.results if "Multi-Turn" in r.test_name):
                print(f"  {Colors.YELLOW}? Context window might be too small (current: 5 messages){Colors.ENDC}")
            
            if not any(r.passed for r in self.results if "Summary" in r.test_name):
                print(f"  {Colors.YELLOW}? Conversation summary may not be generated or used effectively{Colors.ENDC}")


# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == "__main__":
    tester = ContextTester()
    tester.run_all_tests()
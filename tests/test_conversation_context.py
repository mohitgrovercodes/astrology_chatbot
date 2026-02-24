# tests/test_conversation_context.py
# tests\test_conversation_context.py
"""
Test conversation context tracking.

Verifies that the chatbot maintains conversation history and correctly
interprets follow-up responses like \"yes\", \"no\", \"tell me more\", etc.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.ai.intent_classifier import LLMIntentClassifier
from src.llm.factory import create_llm


def test_conversation_context():
    """Test that intent classifier uses conversation history for context."""
    
    print("="*70)
    print("Testing Conversation Context Tracking")
    print("="*70)
    print()
    
    # Initialize classifier with LLM
    llm = create_llm(provider='openai', model='gpt-4o-mini', temperature=0.3)
    classifier = LLMIntentClassifier(llm=llm)
    
    # Test Case 1: Follow-up "yes" after a question
    print("Test 1: Follow-up 'yes' after astrology question")
    print("-"*70)
    
    conversation_history = [
        {'role': 'user', 'content': 'क्या मेरी साढ़े साती चल रही है?'},
        {'role': 'assistant', 'content': 'आपकी कुंडली में शनि मकर राशि में 9वें भाव में स्थित है। क्या आप ग्रहों की स्थिति और उनके प्रभाव के बारे में विस्तृत व्याख्या चाहते हैं?'}
    ]
    
    result = classifier.classify(
        query="हाँ",
        user_profile={'has_birth_data': True},
        conversation_history=conversation_history
    )
    
    print(f"Query: 'हाँ' (yes)")
    print(f"Previous context: Bot asked a follow-up question")
    print(f"Result: {result['intent']}")
    print(f"Confidence: {result['confidence']:.2f}")
    print(f"Reasoning: {result['reasoning']}")
    print()
    
    # Expected: Should NOT be CHITCHAT, should be RAG_WITH_CALCULATION
    if result['intent'] == 'CHITCHAT':
        print("❌ FAIL: Classified as CHITCHAT (lost context!)")
    else:
        print(f"✅ PASS: Correctly classified as {result['intent']}")
    
    print()
    print("="*70)
    
    # Test Case 2: Follow-up "tell me more" 
    print("Test 2: Follow-up 'tell me more'")
    print("-"*70)
    
    conversation_history2 = [
        {'role': 'user', 'content': 'What is Sade Sati?'},
        {'role': 'assistant', 'content': 'Sade Sati is a 7.5 year period when Saturn transits through the 12th, 1st, and 2nd houses from your Moon sign. It is considered a challenging period.'}
    ]
    
    result2 = classifier.classify(
        query="tell me more",
        user_profile={'has_birth_data': True},
        conversation_history=conversation_history2
    )
    
    print(f"Query: 'tell me more'")
    print(f"Previous context: Bot explained Sade Sati")
    print(f"Result: {result2['intent']}")
    print(f"Confidence: {result2['confidence']:.2f}")
    print(f"Reasoning: {result2['reasoning']}")
    print()
    
    if result2['intent'] == 'CHITCHAT':
        print("❌ FAIL: Classified as CHITCHAT (lost context!)")
    else:
        print(f"✅ PASS: Correctly classified as {result2['intent']}")
    
    print()
    print("="*70)
    
    # Test Case 3: No context - "yes" should be CHITCHAT
    print("Test 3: 'yes' without context")
    print("-"*70)
    
    result3 = classifier.classify(
        query="yes",
        user_profile={'has_birth_data': True},
        conversation_history=[]
    )
    
    print(f"Query: 'yes'")
    print(f"Previous context: None")
    print(f"Result: {result3['intent']}")
    print(f"Confidence: {result3['confidence']:.2f}")
    print(f"Reasoning: {result3['reasoning']}")
    print()
    
    if result3['intent'] == 'CHITCHAT':
        print("✅ PASS: Correctly classified as CHITCHAT (no context)")
    else:
        print(f"⚠️ UNEXPECTED: Classified as {result3['intent']} (expected CHITCHAT)")
    
    print()
    print("="*70)
    print("Test Complete!")
    print("="*70)


if __name__ == "__main__":
    test_conversation_context()

# test_no_greetings.py
import sys
import os
import io

# Force UTF-8 for Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Mock initialization to avoid full DB/LLM setup if possible
# But orchestrator needs real parts for graph execution, so we'll try to use the library
sys.path.append(os.getcwd())

from src.orchestration.orchestrator import create_enhanced_orchestrator
from src.ai.intent_classifier import LLMIntentClassifier
from src.locales.language_detector import LanguageDetector

class MockLLM:
    def invoke(self, messages):
        # Check if greeting instructions are present in the system prompt
        if isinstance(messages, list):
            content = " ".join([m.get('content', '') for m in messages])
        else:
            content = str(messages)
            
        if "NO greetings" in content:
            return type('obj', (object,), {'content': "I am analyzing your chart without a greeting."})
        return type('obj', (object,), {'content': "Hello! I am a chatbot."})

def test_greeting_suppression():
    print("Testing Greeting Suppression for ongoing conversations...")
    
    # 1. Simulate first turn (no history)
    history = []
    
    # We'll inspect orchestrator._build_prediction_prompt directly for instruction presence
    from src.orchestration.orchestrator import EnhancedLangGraphOrchestrator
    
    orchestrator = EnhancedLangGraphOrchestrator(
        intent_classifier=None,
        hybrid_retriever=None,
        prompt_builder=None,
        llm=MockLLM(),
        fast_llm=MockLLM()
    )
    
    # Mock data
    user_profile = {'name': 'Arjun', 'preferred_system': 'vedic'}
    chart_data = {'lagna': {'sign': 'Aries'}}
    
    print("\n[Turn 1] No history:")
    prompt_no_history = orchestrator._build_prediction_prompt(
        query="When will I marry?",
        chart_data=chart_data,
        dasha_data={},
        transit_data={},
        knowledge_chunks=[],
        user_profile=user_profile,
        conversation_history=[],
        language='en'
    )
    
    has_no_greet_instr = "NO greetings" in prompt_no_history
    print(f"Contains 'NO greetings' instruction: {has_no_greet_instr} (Expected: False for first turn if logic follows conversation context)")
    # Wait, the current implementation in _build_prediction_prompt (line 2228) adds it if history > 0.
    
    # 2. Simulate second turn (with history)
    history = [{"role": "user", "content": "Hi"}, {"role": "assistant", "content": "Hello Arjun!"}]
    
    print("\n[Turn 2] With history:")
    prompt_with_history = orchestrator._build_prediction_prompt(
        query="Tell me more.",
        chart_data=chart_data,
        dasha_data={},
        transit_data={},
        knowledge_chunks=[],
        user_profile=user_profile,
        conversation_history=history,
        language='en'
    )
    
    has_no_greet_instr_2 = "NO greetings" in prompt_with_history
    print(f"Contains 'NO greetings' instruction: {has_no_greet_instr_2} (Expected: True)")
    
    if has_no_greet_instr_2:
        print("SUCCESS: Greeting suppression instruction found in prompt.")
    else:
        print("FAILURE: Greeting suppression instruction missing.")

    # 3. Test Chitchat Greeting logic
    state = {
        'query': 'Hi',
        'user_profile': user_profile,
        'detected_language': 'en',
        'conversation_history': history, # Existing history
        'intent': 'CHITCHAT'
    }
    
    # Mock semantic router
    class MockRouter:
        def route(self, q, threshold):
            return type('obj', (object,), {'name': 'greeting', 'confidence': 0.99})
    
    orchestrator.semantic_router = MockRouter()
    
    print("\n[Chitchat] Greeting query with history:")
    result = orchestrator._handle_chitchat_node(state)
    print(f"Response: {result['answer']}")
    
    if "Yes, I'm here" in result['answer'] or "assist you further" in result['answer']:
        print("SUCCESS: Chitchat greeting was suppressed/briefed.")
    else:
        print("FAILURE: Chitchat greeting was full introduction.")

if __name__ == "__main__":
    try:
        test_greeting_suppression()
    except Exception as e:
        print(f"Error during test: {e}")
        import traceback
        traceback.print_exc()

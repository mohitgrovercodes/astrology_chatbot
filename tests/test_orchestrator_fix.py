import asyncio
from src.orchestration.orchestrator import EnhancedLangGraphOrchestrator
from langchain_google_vertexai import ChatVertexAI

def test_continuation_guard():
    print("Testing Continuation Guard...")
    # We can just test the state mutation logic in _classify_intent_node
    # Actually, the orchestrator has many heavy dependencies initialized in __init__
    # Let's see if we can instantiate it
    pass

async def run_tests():
    # Instantiate orchestrator. This might take a bit or fail if env vars are missing.
    # But let's try.
    import os
    from dotenv import load_dotenv
    load_dotenv()
    
    try:
        orchestrator = EnhancedLangGraphOrchestrator()
    except Exception as e:
        print(f"Could not instantiate Orchestrator: {e}")
        return

    # Test 1: Continuation Guard should route to RAG_WITH_CALCULATION
    print("--- Test 1: Continuation Guard ---")
    mock_state_1 = {
        "query": "iske bare me thoda aur batao",
        "user_id": "test_user1",
        "session_id": "test_sess1",
        "user_profile": {"name": "Test"},
        "conversation_history": [
            {"role": "user", "content": "When will I get married?"},
            {"role": "assistant", "content": "You will get married soon."}
        ]
    }
    
    # We can call the node directly
    result_1 = orchestrator._classify_intent_node(mock_state_1)
    print(f"Intent classified as: {result_1.get('intent')}")
    assert result_1.get('intent') == 'RAG_WITH_CALCULATION', "Continuation guard failed!"

    # Test 2: Missing birth data guard should ask for details
    print("\n--- Test 2: Missing Birth Data Guard ---")
    mock_state_2 = {
        "query": "When will I get married?",
        "user_id": "test_user2",
        "session_id": "test_sess2",
        "user_profile": {"name": "Empty User"},  # No DOB
        "intent": "RAG_WITH_CALCULATION",
        "confidence": 0.9,
    }
    
    result_2 = orchestrator._handle_rag_with_calculation_node(mock_state_2)
    print(f"Answer returned: {result_2.get('answer')}")
    assert "profile" in result_2.get('answer', '').lower(), "Birth data guard failed!"

if __name__ == "__main__":
    asyncio.run(run_tests())


import sys
import os
from unittest.mock import MagicMock

# Add src to path
sys.path.append(os.path.abspath('src'))

# Mocking modules to avoid full init
os.environ["OPENAI_API_KEY"] = "mock-key"
os.environ["REDIS_HOST"] = "localhost"

# Mock the entire semantic router and other dependencies BEFORE importing
sys.modules['src.routing.semantic_router'] = MagicMock()
sys.modules['src.rag.preprocessing.embedder'] = MagicMock()
sys.modules['src.ai.localization'] = MagicMock()


# Mock classifier slightly differently to avoid Runnable issue
import src.safety.classifier as safety_module
from src.safety.classifier import SafetyClassifier, SafetyDecision, SafetyCheckResult

def debug_safety():
    # Instantiate without LLM first to avoid chain build
    classifier = SafetyClassifier(llm=MagicMock())
    
    # Mock the chain to avoid Runnable execution
    classifier.chain = MagicMock()
    
    # Mock LLM response
    def mock_invoke(vars):
        print(f"\n[DEBUG] LLM Gate Reached for: {vars['query']}")
        return {
            "category": "SOFT_BLOCK",
            "reason": "privacy_violation",
            "should_answer": False,
            "disclaimer_type": None,
            "reframed_query": None,
            "confidence": 0.95,
            "explanation": "LLM thinks it is about someone else",
            "keywords_matched": ["jaunga"]
        }
    classifier.chain.invoke.side_effect = mock_invoke

    # Mock semantic router
    mock_router = MagicMock()
    mock_router.model = True
    classifier.semantic_router = mock_router
    
    test_queries = [
        "Main foreign country kab jaunga?",
        "When will I go abroad?",
        "Main foreign jaunga?"
    ]
    
    for query in test_queries:
        print(f"\n{'='*60}")
        print(f"Testing Query: {query}")
        print(f"{'='*60}")
        
        # We test the actual classify method
        # It should hit Gate -1 (own_data_patterns) and return SAFE
        result = classifier.classify(query)
        
        print(f"\nFINAL RESULT:")
        print(f"  Category: {result.decision.category}")
        print(f"  Reason: {result.decision.reason}")
        print(f"  Explanation: {result.decision.explanation}")
        
        expected_category = "SAFE"
        status = "PASS" if result.decision.category == expected_category else "FAIL"
        print(f"  Status: {status}")

if __name__ == "__main__":
    debug_safety()


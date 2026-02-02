# """
# Test Routing Script for V2 Architecture.
# Tests all 3 intent categories: CHITCHAT | NEEDS_CALCULATION | NEEDS_RAG
# """

# # Suppress Google Generative AI deprecation warning
# import warnings
# warnings.filterwarnings('ignore', category=FutureWarning, module='langchain_google_genai')

# import os
# from dotenv import load_dotenv
# from langchain_google_genai import ChatGoogleGenerativeAI
# from langchain_openai import OpenAIEmbeddings
# from langchain_chroma import Chroma

# load_dotenv()

# from src.ai.intent_classifier import SimplifiedIntentClassifier
# from src.ai.user_manager import get_user_manager
# from src.ai.hybrid_retriever import HybridRetriever
# from src.ai.prompt_builder import PromptBuilder
# from src.orchestration.orchestrator import create_langgraph_orchestrator
# from src.tools.calculation_tools import CALCULATION_TOOLS


# def setup_orchestrator():
#     """Initialize orchestrator for testing."""
    
#     # Components
#     mongodb_uri = os.getenv('MONGODB_URI')
#     user_manager = get_user_manager(mongodb_uri)
    
#     llm = ChatGoogleGenerativeAI(
#         model="gemini-2.5-flash",
#         temperature=0.3
#     )
    
#     embeddings = OpenAIEmbeddings(model="text-embedding-3-large")
    
#     vector_store = Chroma(
#         collection_name="astrology_knowledge",
#         embedding_function=embeddings,
#         persist_directory="./data/vectordb"
#     )
    
#     intent_classifier = SimplifiedIntentClassifier(
#         llm_provider="google",
#         use_cache=True
#     )
    
#     hybrid_retriever = HybridRetriever(
#         vector_store=vector_store,
#         llm=llm
#     )
    
#     prompt_builder = PromptBuilder()
    
#     orchestrator = create_langgraph_orchestrator(
#         intent_classifier=intent_classifier,
#         user_manager=user_manager,
#         hybrid_retriever=hybrid_retriever,
#         prompt_builder=prompt_builder,
#         calculation_tools=CALCULATION_TOOLS,
#         llm=llm,
#         mongodb_uri=mongodb_uri
#     )
    
#     return orchestrator


# def test_routing():
#     """Test all 3 routing paths."""
    
#     print("=" * 80)
#     print("NAKSHATRAAI V2 - ROUTING TEST")
#     print("=" * 80)
#     print()
#     print("Testing 3 categories: CHITCHAT | NEEDS_CALCULATION | NEEDS_RAG")
#     print()
#     print("=" * 80)
#     print()
    
#     # Setup
#     print("Initializing orchestrator...")
#     orchestrator = setup_orchestrator()
#     print("✓ Ready!\n")
    
#     # Test user
#     user_id = "user001"
    
#     # Test cases for each category
#     test_cases = {
#         "CHITCHAT": [
#             "hi",
#             "hello",
#             "who are you?",
#             "what can you do?",
#             "thanks",
#             "goodbye"
#         ],
#         "NEEDS_CALCULATION": [
#             "calculate my birth chart",
#             "show my kundali",
#             "what is my lagna?",
#             "generate my dasha periods",
#             "calculate my rashi",
#             "show current transits"
#         ],
#         "NEEDS_RAG": [
#             "what does Jupiter in 5th house mean?",
#             "when will I get married?",
#             "tell me about Saturn retrograde",
#             "is Mars placement good for career?",
#             "what is Vimshottari dasha?",
#             "explain Venus in 7th house"
#         ]
#     }
    
#     results = {
#         "CHITCHAT": {"correct": 0, "total": 0, "times": []},
#         "NEEDS_CALCULATION": {"correct": 0, "total": 0, "times": []},
#         "NEEDS_RAG": {"correct": 0, "total": 0, "times": []}
#     }
    
#     # Run tests
#     for expected_intent, queries in test_cases.items():
#         print(f"\nTesting: {expected_intent}")
#         print("-" * 80)
        
#         for query in queries:
#             print(f"\n  Query: '{query}'")
            
#             try:
#                 result = orchestrator.process_query(
#                     query=query,
#                     user_id=user_id,
#                     conversation_history=[]
#                 )
                
#                 actual_intent = result['intent']
#                 cached = result.get('cached', False)
#                 time_taken = result.get('processing_time', 0)
                
#                 # Check if correct
#                 correct = actual_intent == expected_intent
#                 status = "✓" if correct else "✗"
#                 cache_status = "[CACHED]" if cached else "[LLM]"
                
#                 print(f"  {status} Intent: {actual_intent} {cache_status}")
#                 print(f"     Time: {time_taken:.2f}s")
                
#                 if not correct:
#                     print(f"     ⚠️  Expected: {expected_intent}")
                
#                 # Update results
#                 results[expected_intent]["total"] += 1
#                 results[expected_intent]["times"].append(time_taken)
#                 if correct:
#                     results[expected_intent]["correct"] += 1
                
#             except Exception as e:
#                 print(f"  ✗ Error: {e}")
#                 results[expected_intent]["total"] += 1
    
#     # Summary
#     print("\n" + "=" * 80)
#     print("TEST SUMMARY")
#     print("=" * 80)
#     print()
    
#     total_correct = 0
#     total_tests = 0
    
#     for intent, stats in results.items():
#         correct = stats["correct"]
#         total = stats["total"]
#         accuracy = (correct / total * 100) if total > 0 else 0
#         avg_time = sum(stats["times"]) / len(stats["times"]) if stats["times"] else 0
        
#         print(f"{intent}:")
#         print(f"  Accuracy: {correct}/{total} ({accuracy:.1f}%)")
#         print(f"  Avg Time: {avg_time:.2f}s")
#         print()
        
#         total_correct += correct
#         total_tests += total
    
#     overall_accuracy = (total_correct / total_tests * 100) if total_tests > 0 else 0
    
#     print("-" * 80)
#     print(f"OVERALL: {total_correct}/{total_tests} ({overall_accuracy:.1f}%)")
#     print("=" * 80)
#     print()
    
#     # Evaluation
#     if overall_accuracy >= 90:
#         print("✅ EXCELLENT - Routing is working very well!")
#     elif overall_accuracy >= 80:
#         print("✓ GOOD - Routing is working, minor improvements possible")
#     elif overall_accuracy >= 70:
#         print("⚠️  OKAY - Some routing issues, needs tuning")
#     else:
#         print("❌ POOR - Routing needs significant work")
    
#     print()


# if __name__ == "__main__":
#     test_routing()


"""
Test Routing Script - Using Absolute Imports
No dependency on __init__.py files.
"""

import warnings
warnings.filterwarnings('ignore', category=FutureWarning, module='langchain_google_genai')

import os
import sys
from pathlib import Path

# Ensure project root is in path
project_root = Path(__file__).parent.absolute()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

# Standard imports
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma

# Direct imports from module files (bypass __init__.py)
from src.ai.intent_classifier import EnhancedIntentClassifier
from src.ai.user_manager import get_user_manager
from src.ai.hybrid_retriever import HybridRetriever
from src.ai.prompt_builder import PromptBuilder
from src.orchestration.orchestrator import create_enhanced_orchestrator
from src.tools.calculation_tools import CALCULATION_TOOLS


def setup_orchestrator():
    """Initialize orchestrator for testing."""
    
    print("Setting up orchestrator components...")
    
    # Components
    mongodb_uri = os.getenv('MONGODB_URI')
    user_manager = get_user_manager(mongodb_uri)
    
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0.3
    )
    
    embeddings = OpenAIEmbeddings(model="text-embedding-3-large")
    
    vector_store = Chroma(
        collection_name="astrology_knowledge",
        embedding_function=embeddings,
        persist_directory="./data/vectordb"
    )
    
    intent_classifier = EnhancedIntentClassifier(
        llm_provider="google",
        use_cache=True
    )
    
    hybrid_retriever = HybridRetriever(
        vector_store=vector_store,
        llm=llm
    )
    
    prompt_builder = PromptBuilder()
    
    orchestrator = create_enhanced_orchestrator(
        intent_classifier=intent_classifier,
        user_manager=user_manager,
        hybrid_retriever=hybrid_retriever,
        prompt_builder=prompt_builder,
        calculation_tools=CALCULATION_TOOLS,
        llm=llm,
        mongodb_uri=mongodb_uri
    )
    
    return orchestrator


def test_routing():
    """Test all 3 routing paths."""
    
    print("=" * 80)
    print("NAKSHATRAAI V2 - ROUTING TEST")
    print("=" * 80)
    print()
    print("Testing 3 categories: CHITCHAT | NEEDS_CALCULATION | NEEDS_RAG")
    print()
    print("=" * 80)
    print()
    
    # Setup
    print("Initializing orchestrator...")
    try:
        orchestrator = setup_orchestrator()
        print("[SUCCESS] Setup ready!\n")
    except Exception as e:
        print(f"[ERROR] Setup failed: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Test user
    user_id = "user001"
    
    # Test cases for each category
    test_cases = {
        "CHITCHAT": [
            "hi",
            "hello",
            "who are you?",
            "what can you do?",
            "thanks",
            "goodbye"
        ],
        "NEEDS_CALCULATION": [
            "calculate my birth chart",
            "show my kundali",
            "what is my lagna?",
            "generate my dasha periods",
            "calculate my rashi",
            "show current transits"
        ],
        "NEEDS_RAG": [
            "what does Jupiter in 5th house mean?",
            "when will I get married?",
            "tell me about Saturn retrograde",
            "is Mars placement good for career?",
            "what is Vimshottari dasha?",
            "explain Venus in 7th house"
        ]
    }
    
    results = {
        "CHITCHAT": {"correct": 0, "total": 0, "times": []},
        "NEEDS_CALCULATION": {"correct": 0, "total": 0, "times": []},
        "NEEDS_RAG": {"correct": 0, "total": 0, "times": []}
    }
    
    # Run tests
    for expected_intent, queries in test_cases.items():
        print(f"\nTesting: {expected_intent}")
        print("-" * 80)
        
        for query in queries:
            print(f"\n  Query: '{query}'")
            
            try:
                result = orchestrator.process_query(
                    query=query,
                    user_id=user_id,
                    conversation_history=[]
                )
                
                actual_intent = result['intent']
                cached = result.get('cached', False)
                time_taken = result.get('processing_time', 0)
                
                # Check if correct
                correct = actual_intent == expected_intent
                status = "PASS" if correct else "FAIL"
                cache_status = "[CACHED]" if cached else "[LLM]"
                
                print(f"  [{status}] Intent: {actual_intent} {cache_status}")
                print(f"     Time: {time_taken:.2f}s")
                
                if not correct:
                    print(f"     [WARNING] Expected: {expected_intent}")
                
                # Update results
                results[expected_intent]["total"] += 1
                results[expected_intent]["times"].append(time_taken)
                if correct:
                    results[expected_intent]["correct"] += 1
                
            except Exception as e:
                print(f"  [ERROR] Error: {e}")
                results[expected_intent]["total"] += 1
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print()
    
    total_correct = 0
    total_tests = 0
    
    for intent, stats in results.items():
        correct = stats["correct"]
        total = stats["total"]
        accuracy = (correct / total * 100) if total > 0 else 0
        avg_time = sum(stats["times"]) / len(stats["times"]) if stats["times"] else 0
        
        print(f"{intent}:")
        print(f"  Accuracy: {correct}/{total} ({accuracy:.1f}%)")
        print(f"  Avg Time: {avg_time:.2f}s")
        print()
        
        total_correct += correct
        total_tests += total
    
    overall_accuracy = (total_correct / total_tests * 100) if total_tests > 0 else 0
    
    print("-" * 80)
    print(f"OVERALL: {total_correct}/{total_tests} ({overall_accuracy:.1f}%)")
    print("=" * 80)
    print()
    
    # Evaluation
    if overall_accuracy >= 90:
        print("[EXCELLENT] Routing is working very well!")
    elif overall_accuracy >= 80:
        print("[GOOD] Routing is working, minor improvements possible")
    elif overall_accuracy >= 70:
        print("[OKAY] Some routing issues, needs tuning")
    else:
        print("[POOR] Routing needs significant work")
    
    print()


if __name__ == "__main__":
    test_routing()
# correct_qa_test.py
"""
Correct Q&A Test - Matches actual stream format.
Your stream yields ONE event with full 'answer', not chunked streaming.
"""

import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

print("="*80)
print("Q&A TEST (Correct Stream Format)".center(80))
print("="*80)
print()

# Use your actual database
TEST_USER_ID = "user002"  # Arjun Kumar from your DB

# Test questions
TESTS = [
    {
        'id': 1,
        'question': 'When will I get married?',
        'category': 'MARRIAGE (D9)',
        'expected': ['marriage', 'marital', 'spouse', 'partner', 'matrimon', 'wedding'],
        'min_length': 150,
    },
    {
        'id': 2,
        'question': 'What career suits me?',
        'category': 'CAREER (D10)',
        'expected': ['career'],
        'min_length': 150,
    },
    {
        'id': 3,
        'question': 'Will I have children?',
        'category': 'CHILDREN (D7)',
        'expected': ['children'],
        'min_length': 150,
    },
    {
        'id': 4,
        'question': 'Hello',
        'category': 'CHITCHAT',
        'expected': ['help', 'assist', 'NakshatraAI'],
        'min_length': 30,
    },
]

def init():
    """Initialize orchestrator."""
    
    print("Initializing...")
    
    from src.orchestration.orchestrator import create_enhanced_orchestrator
    from src.ai.intent_classifier import EnhancedIntentClassifier
    from src.ai.user_manager import get_user_manager
    from src.ai.hybrid_retriever import HybridRetriever
    from src.ai.prompt_builder import PromptBuilder
    from src.llm.factory import LLMFactory
    from langchain_openai import OpenAIEmbeddings
    from langchain_chroma import Chroma
    
    llm = LLMFactory.create(purpose="general")
    fast_llm = LLMFactory.create(purpose="classification")
    
    # Use your actual database
    user_manager = get_user_manager("data/astro.db")
    
    if not user_manager.user_exists(TEST_USER_ID):
        print(f"❌ User {TEST_USER_ID} not found in database!")
        return None, None
    
    profile = user_manager.get_user_profile(TEST_USER_ID)
    print(f"  ✓ User: {profile.name}")
    print(f"  ✓ Birth: {profile.birth_date if hasattr(profile, 'birth_date') else 'Check DB'}")
    
    embeddings = OpenAIEmbeddings(model="text-embedding-3-large", dimensions=3072)
    vector_store = Chroma(
        collection_name="vedic_astrology_books_knowledge",
        embedding_function=embeddings,
        persist_directory="./data/vectordb"
    )
    
    from src.tools.calculation_tools import CALCULATION_TOOLS
    
    retriever = HybridRetriever(vector_store=vector_store, llm=llm)
    classifier = EnhancedIntentClassifier(llm=fast_llm)
    prompt_builder = PromptBuilder()
    
    orchestrator = create_enhanced_orchestrator(
        intent_classifier=classifier,
        user_manager=user_manager,
        hybrid_retriever=retriever,
        prompt_builder=prompt_builder,
        calculation_tools=CALCULATION_TOOLS,
        llm=llm,
        fast_llm=fast_llm
    )
    
    print("  ✓ Ready")
    print()
    
    return orchestrator, user_manager, TEST_USER_ID

def run_test(orchestrator, test, user_id, session_data):
    """Run test with CORRECT stream handling."""
    
    print("-"*80)
    print(f"Test #{test['id']}: {test['category']}")
    print(f"Q: {test['question']}")
    print("-"*80)
    
    import time
    start_time = time.time()
    
    try:
        # Get stream
        result_stream = orchestrator.process_query_stream(
            query=test['question'],
            user_id=user_id,
            conversation_history=[],
            session_data=session_data
        )
        
        # Collect - YOUR STREAM YIELDS ONE EVENT WITH FULL ANSWER
        full_answer = ""
        intent = "unknown"
        event_count = 0
        
        print("Processing", end="", flush=True)
        
        for event in result_stream:
            event_count += 1
            print(".", end="", flush=True)
            
            # Your stream yields AddableValuesDict with 'answer' key
            if isinstance(event, dict) and 'answer' in event:
                full_answer = event['answer']
                intent = event.get('intent', 'unknown')
            # Or if it's the dict-like object
            elif hasattr(event, 'get'):
                full_answer = event.get('answer', '')
                intent = event.get('intent', 'unknown')
        
        print()
        
        elapsed = time.time() - start_time
        
        print(f"\n  Time: {elapsed:.1f}s")
        print(f"  Intent: {intent}")
        print(f"  Events: {event_count}")
        print(f"  Length: {len(full_answer)} chars")
        
        # Verify
        passed = True
        issues = []
        
        if not full_answer:
            passed = False
            issues.append("Empty response")
            print(f"  ✗ EMPTY")
        else:
            print(f"  ✓ Got response")
            
            # Check length
            if len(full_answer) < test['min_length']:
                issues.append(f"Short ({len(full_answer)} < {test['min_length']})")
            
            # Check expected terms (at least one)
            found = [t for t in test['expected'] if t.lower() in full_answer.lower()]
            if found:
                print(f"  ✓ Found: {found}")
            else:
                issues.append(f"Missing terms: {test['expected']}")
            
            # Preview
            preview = full_answer[:150].replace('\n', ' ')
            if len(full_answer) > 150:
                preview += "..."
            print(f"\n  Preview: {preview}")
        
        if not issues:
            print(f"\n  ✓ PASSED")
        elif len(issues) == 1 and "Short" in issues[0]:
            print(f"\n  ⚠ PASSED (short response)")
            passed = True
        else:
            print(f"\n  ✗ FAILED")
            for issue in issues:
                print(f"     • {issue}")
            passed = False
        
        return {
            'id': test['id'],
            'category': test['category'],
            'passed': passed,
            'elapsed': elapsed,
            'length': len(full_answer),
            'intent': intent,
            'issues': issues,
            'response': full_answer[:500]  # Save sample
        }
        
    except Exception as e:
        print(f"\n  ✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return {
            'id': test['id'],
            'category': test['category'],
            'passed': False,
            'error': str(e)
        }

def main():
    # Initialize
    orchestrator, user_manager, user_id = init()
    
    if not orchestrator:
        print("Cannot run tests")
        return
    
    # Build session enrichment from user profile
    profile = user_manager.get_user_profile(user_id)
    session_data = {
        "name": profile.name,
        "custom_note": "QA Test Session",
        "chart_data": None,   # Will be computed live by orchestrator
        "dasha_data": None,
        "transit_data": None,
    }
    
    print("="*80)
    print("RUNNING TESTS")
    print("="*80)
    print()
    
    results = []
    
    for test in TESTS:
        result = run_test(orchestrator, test, user_id, session_data)
        results.append(result)
        print()
        
        import time
        time.sleep(1)
    
    # Summary
    print("="*80)
    print("SUMMARY")
    print("="*80)
    print()
    
    passed = sum(1 for r in results if r['passed'])
    total = len(results)
    
    print(f"Total: {total}")
    print(f"✓ Passed: {passed}")
    print(f"✗ Failed: {total - passed}")
    print(f"Success: {passed/total*100:.0f}%")
    
    print("\nResults:")
    for r in results:
        status = "✓" if r['passed'] else "✗"
        print(f"  {status} {r['category']}: {r.get('length', 0)} chars, {r.get('elapsed', 0):.1f}s")
        
        if 'issues' in r and r['issues']:
            for issue in r['issues']:
                print(f"     ⚠ {issue}")
    
    # Save report
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    with open(f'qa_report_{timestamp}.txt', 'w', encoding='utf-8') as f:
        f.write("Q&A TEST REPORT\n")
        f.write("="*80 + "\n\n")
        f.write(f"Date: {datetime.now()}\n")
        f.write(f"Total: {total}, Passed: {passed}, Failed: {total-passed}\n\n")
        
        for r in results:
            f.write(f"Test #{r['id']}: {r['category']}\n")
            f.write(f"Status: {'PASSED' if r['passed'] else 'FAILED'}\n")
            f.write(f"Intent: {r.get('intent')}\n")
            f.write(f"Time: {r.get('elapsed', 0):.1f}s\n")
            f.write(f"Length: {r.get('length', 0)} chars\n")
            
            if 'response' in r:
                f.write(f"\nResponse:\n{r['response']}\n")
            
            if 'issues' in r:
                f.write(f"\nIssues:\n")
                for issue in r['issues']:
                    f.write(f"  • {issue}\n")
            
            f.write("\n" + "-"*80 + "\n\n")
    
    print(f"\nReport: qa_report_{timestamp}.txt")
    print()
    
    if passed == total:
        print("🎉 ALL TESTS PASSED!")
    elif passed >= total * 0.75:
        print("✅ Most tests passed!")
    else:
        print("⚠️ Review failures above")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrupted")
    except Exception as e:
        print(f"\n\nFATAL: {e}")
        import traceback
        traceback.print_exc()
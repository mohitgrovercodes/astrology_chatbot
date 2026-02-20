# quick_chatbot_test.py
"""
Quick Chatbot Test - Automated Question & Answer Verification
Tests different calculations and knowledge retrieval automatically.

Usage: python quick_chatbot_test.py
"""

import sys
import time
import re
from datetime import datetime

# ============================================================================
# CORE TEST QUESTIONS - 10 Essential Tests
# ============================================================================

QUICK_TESTS = [
    {
        'id': 1,
        'question': 'When will I get married?',
        'category': 'MARRIAGE (D9)',
        'must_have_in_response': ['D9', 'Navamsa', 'marriage', '7th', 'Venus'],
        'must_have_in_logs': ['RAG_WITH_CALCULATION', 'Retrieved', 'chunks'],
        'should_mention_dasha': True,
        'expected_charts': ['D9'],
        'description': 'Tests: D9 chart usage, marriage timing, RAG retrieval, dasha integration'
    },
    
    {
        'id': 2,
        'question': 'What career is best for me?',
        'category': 'CAREER (D10)',
        'must_have_in_response': ['D10', 'Dasamsa', 'career', '10th', 'profession'],
        'must_have_in_logs': ['RAG_WITH_CALCULATION', 'Retrieved', 'chunks'],
        'should_mention_dasha': False,
        'expected_charts': ['D10'],
        'description': 'Tests: D10 chart usage, career analysis, Saturn placement'
    },
    
    {
        'id': 3,
        'question': 'Will I have children?',
        'category': 'CHILDREN (D7)',
        'must_have_in_response': ['D7', 'Saptamsa', 'children', 'Jupiter', '5th'],
        'must_have_in_logs': ['RAG_WITH_CALCULATION', 'Retrieved', 'chunks'],
        'should_mention_dasha': False,
        'expected_charts': ['D7'],
        'description': 'Tests: D7 chart usage, children prospects, Jupiter as karaka'
    },
    
    {
        'id': 4,
        'question': 'Will I buy a house this year?',
        'category': 'PROPERTY (D4)',
        'must_have_in_response': ['D4', 'Chaturthamsa', 'property', '4th', 'house'],
        'must_have_in_logs': ['RAG_WITH_CALCULATION', 'Retrieved', 'chunks', 'property'],
        'should_mention_dasha': True,
        'expected_charts': ['D4'],
        'description': 'Tests: D4 chart usage, smart property detection, timing analysis'
    },
    
    {
        'id': 5,
        'question': 'What health issues should I watch for?',
        'category': 'HEALTH (D6)',
        'must_have_in_response': ['D6', 'Shashtamsa', 'health', '6th'],
        'must_have_in_logs': ['RAG_WITH_CALCULATION', 'Retrieved', 'chunks'],
        'should_mention_dasha': False,
        'expected_charts': ['D6'],
        'description': 'Tests: D6 chart usage, health analysis, disease indicators'
    },
    
    {
        'id': 6,
        'question': 'Will I become wealthy?',
        'category': 'WEALTH (D2)',
        'must_have_in_response': ['D2', 'Hora', 'wealth', 'Jupiter', 'Venus'],
        'must_have_in_logs': ['RAG_WITH_CALCULATION', 'Retrieved', 'chunks'],
        'should_mention_dasha': False,
        'expected_charts': ['D2'],
        'description': 'Tests: D2 chart usage, wealth yogas, dhana combinations'
    },
    
    {
        'id': 7,
        'question': 'Should I pursue higher education?',
        'category': 'EDUCATION (D24)',
        'must_have_in_response': ['D24', 'Chaturvimsamsa', 'education', 'Mercury', '4th'],
        'must_have_in_logs': ['RAG_WITH_CALCULATION', 'Retrieved', 'chunks'],
        'should_mention_dasha': False,
        'expected_charts': ['D24'],
        'description': 'Tests: D24 chart usage, education analysis, Mercury as karaka'
    },
    
    {
        'id': 8,
        'question': 'Do I have any Raja Yogas?',
        'category': 'YOGAS',
        'must_have_in_response': ['yoga', 'Raja', 'combination'],
        'must_have_in_logs': ['RAG_WITH_CALCULATION', 'Retrieved', 'chunks'],
        'should_mention_dasha': False,
        'expected_charts': [],
        'description': 'Tests: Yoga detection, classical text retrieval, BPHS references'
    },
    
    {
        'id': 9,
        'question': 'What does my current dasha indicate?',
        'category': 'DASHA ANALYSIS',
        'must_have_in_response': ['Mahadasha', 'Antardasha', 'period', 'dasha'],
        'must_have_in_logs': ['RAG_WITH_CALCULATION', 'Retrieved', 'chunks'],
        'should_mention_dasha': True,
        'expected_charts': [],
        'description': 'Tests: Dasha calculation, period analysis, timing predictions'
    },
    
    {
        'id': 10,
        'question': 'Hello, how are you?',
        'category': 'CHITCHAT',
        'must_have_in_response': ['Hello', 'help', 'astrology'],
        'must_have_in_logs': ['CHITCHAT'],
        'should_mention_dasha': False,
        'expected_charts': [],
        'description': 'Tests: Intent classification, chitchat routing (no calculations)'
    },
]

# ============================================================================
# VERIFICATION FUNCTIONS
# ============================================================================

def verify_response(test: dict, response: str, logs: str) -> dict:
    """Verify if response meets test expectations."""
    
    results = {
        'test_id': test['id'],
        'category': test['category'],
        'passed': True,
        'issues': [],
        'metrics': {}
    }
    
    # Check 1: Required terms in response
    missing_terms = []
    for term in test['must_have_in_response']:
        if term.lower() not in response.lower():
            missing_terms.append(term)
    
    if missing_terms:
        results['passed'] = False
        results['issues'].append(f"Missing in response: {', '.join(missing_terms)}")
    else:
        results['metrics']['required_terms'] = 'All present ✓'
    
    # Check 2: Required terms in logs
    missing_log_terms = []
    for term in test['must_have_in_logs']:
        if term not in logs:
            missing_log_terms.append(term)
    
    if missing_log_terms:
        results['passed'] = False
        results['issues'].append(f"Missing in logs: {', '.join(missing_log_terms)}")
    else:
        results['metrics']['log_indicators'] = 'All present ✓'
    
    # Check 3: Chunks retrieved (for RAG queries)
    if 'RAG_WITH_CALCULATION' in test['must_have_in_logs']:
        chunks_match = re.search(r'Retrieved (\d+) chunks', logs)
        if chunks_match:
            chunks = int(chunks_match.group(1))
            results['metrics']['chunks_retrieved'] = chunks
            if chunks < 5:
                results['passed'] = False
                results['issues'].append(f"Only {chunks} chunks retrieved (expected 8-10)")
        else:
            results['passed'] = False
            results['issues'].append("Chunk count not found in logs")
    
    # Check 4: Validation strength
    strength_match = re.search(r'Strength:\s*([\d.]+)\s*/\s*10', logs)
    if strength_match:
        strength = float(strength_match.group(1))
        results['metrics']['validation_strength'] = f"{strength}/10"
        if strength < 8:
            results['issues'].append(f"Low validation strength: {strength}/10")
    
    # Check 5: Dasha periods (if expected)
    if test['should_mention_dasha']:
        dasha_keywords = ['Mahadasha', 'Antardasha']
        if not any(kw in response for kw in dasha_keywords):
            results['passed'] = False
            results['issues'].append("Dasha periods not mentioned in response")
        else:
            results['metrics']['dasha_mentioned'] = 'Yes ✓'
    
    # Check 6: Expected divisional charts
    if test['expected_charts']:
        missing_charts = []
        for chart in test['expected_charts']:
            if chart not in response and chart not in logs:
                missing_charts.append(chart)
        
        if missing_charts:
            results['passed'] = False
            results['issues'].append(f"Missing divisional charts: {', '.join(missing_charts)}")
        else:
            results['metrics']['divisional_charts'] = ', '.join(test['expected_charts']) + ' ✓'
    
    # Check 7: Classical text citations
    classical_books = ['Brihat Parashara', 'BPHS', 'Phaladeepika', 'Jataka']
    found_books = [book for book in classical_books if book in response]
    if found_books and 'RAG_WITH_CALCULATION' in test['must_have_in_logs']:
        results['metrics']['classical_refs'] = ', '.join(found_books) + ' ✓'
    
    return results

# ============================================================================
# TEST RUNNER
# ============================================================================

def run_quick_test():
    """Run automated test with orchestrator."""
    
    print("="*80)
    print("QUICK CHATBOT TEST - Automated Verification".center(80))
    print("="*80)
    print()
    
    print("Initializing orchestrator...")
    
    try:
        # Import required modules
        from src.orchestration.orchestrator import create_enhanced_orchestrator
        from src.ai.intent_classifier import EnhancedIntentClassifier
        from src.ai.user_manager import get_user_manager
        from src.ai.hybrid_retriever import HybridRetriever
        from src.ai.prompt_builder import PromptBuilder
        from src.llm.factory import LLMFactory
        from langchain_openai import OpenAIEmbeddings
        from langchain_chroma import Chroma
        import io
        import contextlib
        
        # Initialize components (suppress output)
        print("  Loading LLM...")
        llm = LLMFactory.create(purpose="general")
        fast_llm = LLMFactory.create(purpose="classification")
        
        print("  Loading user manager...")
        user_manager = get_user_manager(None)
        
        print("  Loading vector database...")
        embeddings = OpenAIEmbeddings(model="text-embedding-3-large", dimensions=3072)
        vector_store = Chroma(
            collection_name="vedic_astrology_books_knowledge",
            embedding_function=embeddings,
            persist_directory="./data/vectordb"
        )
        
        print("  Loading retriever...")
        retriever = HybridRetriever(vector_store=vector_store, llm=llm)
        
        print("  Loading classifier...")
        classifier = EnhancedIntentClassifier(llm=fast_llm)
        
        print("  Building orchestrator...")
        prompt_builder = PromptBuilder()
        
        orchestrator = create_enhanced_orchestrator(
            intent_classifier=classifier,
            user_manager=user_manager,
            hybrid_retriever=retriever,
            prompt_builder=prompt_builder,
            calculation_tools={},
            llm=llm,
            fast_llm=fast_llm
        )
        
        print("✓ Orchestrator ready\n")
        
        # Run tests
        results = []
        
        for test in QUICK_TESTS:
            print("-"*80)
            print(f"Test #{test['id']}: {test['category']}")
            print(f"Question: {test['question']}")
            print(f"Purpose: {test['description']}")
            print("-"*80)
            
            # Capture logs
            log_capture = io.StringIO()
            
            start_time = time.time()
            
            try:
                with contextlib.redirect_stdout(log_capture):
                    result = orchestrator.process_query(
                        query=test['question'],
                        user_id="quick_test_user"
                    )
                
                elapsed = time.time() - start_time
                
                logs = log_capture.getvalue()
                
                # Extract response
                response_text = ""
                if hasattr(result, 'get'):
                    response_text = str(result.get('answer', '') or result.get('response', ''))
                elif hasattr(result, '__getitem__'):
                    try:
                        response_text = str(result['answer'] or result['response'])
                    except:
                        response_text = str(result)
                
                # Verify
                verification = verify_response(test, response_text, logs)
                verification['elapsed_time'] = elapsed
                
                # Display results
                if verification['passed']:
                    print(f"✓ PASSED ({elapsed:.1f}s)")
                else:
                    print(f"✗ FAILED ({elapsed:.1f}s)")
                
                if verification['metrics']:
                    print("\nMetrics:")
                    for key, value in verification['metrics'].items():
                        print(f"  • {key}: {value}")
                
                if verification['issues']:
                    print("\nIssues:")
                    for issue in verification['issues']:
                        print(f"  ✗ {issue}")
                
                # Show brief response preview
                if response_text:
                    preview = response_text[:200] + "..." if len(response_text) > 200 else response_text
                    print(f"\nResponse preview: {preview}")
                
                results.append(verification)
                
            except Exception as e:
                print(f"✗ ERROR: {e}")
                results.append({
                    'test_id': test['id'],
                    'category': test['category'],
                    'passed': False,
                    'issues': [f"Exception: {str(e)}"],
                    'metrics': {}
                })
            
            print()
            time.sleep(2)  # Brief pause between tests
        
        # Summary
        print("="*80)
        print("TEST SUMMARY".center(80))
        print("="*80)
        print()
        
        passed = sum(1 for r in results if r['passed'])
        failed = len(results) - passed
        
        print(f"Total Tests: {len(results)}")
        print(f"✓ Passed: {passed} ({passed/len(results)*100:.1f}%)")
        print(f"✗ Failed: {failed} ({failed/len(results)*100:.1f}%)")
        print()
        
        # Category breakdown
        categories = {}
        for r in results:
            cat = r['category'].split()[0]
            if cat not in categories:
                categories[cat] = {'passed': 0, 'total': 0}
            categories[cat]['total'] += 1
            if r['passed']:
                categories[cat]['passed'] += 1
        
        print("Results by Category:")
        for cat, stats in categories.items():
            status = "✓" if stats['passed'] == stats['total'] else "✗"
            print(f"  {status} {cat}: {stats['passed']}/{stats['total']}")
        
        print()
        
        # Failed tests detail
        if failed > 0:
            print("Failed Tests Detail:")
            for r in results:
                if not r['passed']:
                    print(f"\n  Test #{r['test_id']}: {r['category']}")
                    for issue in r['issues']:
                        print(f"    • {issue}")
        
        # Save detailed report
        report_file = f"quick_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write("QUICK CHATBOT TEST REPORT\n")
            f.write("="*80 + "\n\n")
            f.write(f"Date: {datetime.now()}\n")
            f.write(f"Total Tests: {len(results)}\n")
            f.write(f"Passed: {passed}\n")
            f.write(f"Failed: {failed}\n\n")
            
            for r in results:
                f.write(f"Test #{r['test_id']}: {r['category']}\n")
                f.write(f"Status: {'PASSED' if r['passed'] else 'FAILED'}\n")
                if r['metrics']:
                    f.write("Metrics:\n")
                    for k, v in r['metrics'].items():
                        f.write(f"  {k}: {v}\n")
                if r['issues']:
                    f.write("Issues:\n")
                    for issue in r['issues']:
                        f.write(f"  • {issue}\n")
                f.write("\n" + "-"*80 + "\n\n")
        
        print(f"\nDetailed report saved: {report_file}")
        
    except Exception as e:
        print(f"Failed to initialize: {e}")
        import traceback
        traceback.print_exc()

# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    run_quick_test()
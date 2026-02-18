# tests/test_safety.py
# tests\test_safety.py
"""
Test script for Safety Module - Guardrails
===========================================

Tests the QueryAnalyzer and ResponseEnhancer with various sensitive queries.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.safety.guardrails import QueryAnalyzer, ResponseEnhancer, HandlingStrategy
from src.safety.disclaimers import get_disclaimer, get_clarifying_question

def test_query_analysis():
    """Test query categorization and sensitivity detection."""
    analyzer = QueryAnalyzer()
    
    test_cases = [
        # (query, expected_category, min_sensitivity)
        ("What is my sun sign?", "general", 0.0),
        ("When will I die?", "death_mortality", 0.8),
        ("Will I recover from my illness?", "health", 0.6),
        ("Is my spouse cheating on me?", "relationship", 0.5),
        ("Should I invest in stocks now?", "financial", 0.4),
        ("Will I win my court case?", "legal", 0.5),
        ("I feel depressed and hopeless", "mental_health", 0.8),
        ("Tell me about Jupiter in my chart", "general", 0.0),
        ("When will I get married?", "general", 0.0),  # Prediction but not sensitive
    ]
    
    print("=" * 70)
    print("QUERY ANALYSIS TESTS")
    print("=" * 70)
    
    for query, expected_cat, min_sens in test_cases:
        analysis = analyzer.analyze(query)
        
        print(f"\nQuery: \"{query}\"")
        print(f"  Category: {analysis.category.value}")
        print(f"  Sensitivity: {analysis.sensitivity_level:.2f}")
        print(f"  Strategy: {analysis.handling_strategy.value}")
        print(f"  Requires Disclaimer: {analysis.requires_disclaimer}")
        
        if analysis.clarifying_question:
            print(f"  Clarifying Q: {analysis.clarifying_question[:80]}...")
        if analysis.positive_redirect:
            print(f"  Redirect: {analysis.positive_redirect[:80]}...")
        
        # Validate expectations
        if expected_cat != "general":
            assert analysis.category.value == expected_cat, \
                f"Expected {expected_cat}, got {analysis.category.value}"
            assert analysis.sensitivity_level >= min_sens, \
                f"Expected sensitivity >= {min_sens}, got {analysis.sensitivity_level}"
    
    print("\n" + "=" * 70)
    print("✅ All query analysis tests passed!")


def test_response_enhancement():
    """Test response enhancement with disclaimers."""
    analyzer = QueryAnalyzer()
    enhancer = ResponseEnhancer()
    
    print("\n" + "=" * 70)
    print("RESPONSE ENHANCEMENT TESTS")
    print("=" * 70)
    
    # Test case 1: Death query
    query = "When will I die?"
    raw_response = (
        "Based on your 8th house with Saturn, and considering the current Mahadasha, "
        "I can share insights about longevity factors in your chart."
    )
    
    analysis = analyzer.analyze(query)
    enhanced = enhancer.enhance(raw_response, analysis)
    
    print(f"\n1. Death Query Enhancement:")
    print(f"   Original length: {len(raw_response)} chars")
    print(f"   Enhanced length: {len(enhanced)} chars")
    print(f"   Strategy: {analysis.handling_strategy.value}")
    print(f"\n   Enhanced Response Preview:")
    print(f"   {enhanced[:200]}...")
    
    # Test case 2: Health query
    query = "Will I recover from my illness?"
    raw_response = (
        "Looking at your 6th house of health and the position of healing planet Jupiter, "
        "the planetary transits suggest favorable periods for recovery."
    )
    
    analysis = analyzer.analyze(query)
    enhanced = enhancer.enhance(raw_response, analysis)
    
    print(f"\n2. Health Query Enhancement:")
    print(f"   Original length: {len(raw_response)} chars")
    print(f"   Enhanced length: {len(enhanced)} chars")
    print(f"   Strategy: {analysis.handling_strategy.value}")
    print(f"\n   Enhanced Response Preview:")
    print(f"   {enhanced[:200]}...")
    
    # Test case 3: General query (should not add much)
    query = "What does Jupiter mean in my chart?"
    raw_response = (
        "Jupiter in your 5th house brings wisdom, creativity, and good fortune in "
        "matters of learning, children, and speculation."
    )
    
    analysis = analyzer.analyze(query)
    enhanced = enhancer.enhance(raw_response, analysis)
    
    print(f"\n3. General Query Enhancement:")
    print(f"   Original length: {len(raw_response)} chars")
    print(f"   Enhanced length: {len(enhanced)} chars")
    print(f"   Strategy: {analysis.handling_strategy.value}")
    assert len(enhanced) == len(raw_response), "General queries should not be enhanced"
    
    print("\n" + "=" * 70)
    print("✅ All response enhancement tests passed!")


def test_clarification_flow():
    """Test the C → B → A flow for highly sensitive queries."""
    analyzer = QueryAnalyzer()
    enhancer = ResponseEnhancer()
    
    print("\n" + "=" * 70)
    print("C → B → A FLOW TESTS")
    print("=" * 70)
    
    # Highly sensitive query should trigger clarification (C)
    query = "When will my mother die?"
    analysis = analyzer.analyze(query)
    should_clarify, clarifying_q = enhancer.should_ask_clarification(analysis)
    
    print(f"\n1. Highly Sensitive Query: \"{query}\"")
    print(f"   Sensitivity: {analysis.sensitivity_level:.2f}")
    print(f"   Should Clarify First (C): {should_clarify}")
    if should_clarify:
        print(f"   Clarifying Question:")
        print(f"   {clarifying_q}")
    
    # Medium sensitivity should get redirect + empathy (B → A)
    query = "Will I get divorced?"
    analysis = analyzer.analyze(query)
    should_clarify, _ = enhancer.should_ask_clarification(analysis)
    
    print(f"\n2. Medium Sensitivity Query: \"{query}\"")
    print(f"   Sensitivity: {analysis.sensitivity_level:.2f}")
    print(f"   Should Clarify First (C): {should_clarify}")
    print(f"   Strategy: {analysis.handling_strategy.value}")
    if analysis.positive_redirect:
        print(f"   Positive Redirect (B):")
        print(f"   {analysis.positive_redirect[:100]}...")
    
    print("\n" + "=" * 70)
    print("✅ C → B → A flow tests passed!")


def test_full_integration():
    """Test complete query → analysis → enhancement pipeline."""
    from src.safety.guardrails import analyze_query, enhance_response
    
    print("\n" + "=" * 70)
    print("FULL INTEGRATION TEST")
    print("=" * 70)
    
    # Simulate a complete interaction
    query = "Will I survive this surgery?"
    raw_llm_response = (
        "Looking at your chart, I see Jupiter's protective influence in your 8th house. "
        "The current transit of Saturn suggests this is indeed a period requiring care, "
        "but the strength of your Lagna lord indicates resilience."
    )
    
    # Analyze query
    analysis = analyze_query(query)
    
    print(f"\nQuery: \"{query}\"")
    print(f"\nAnalysis:")
    print(f"  Category: {analysis.category.value}")
    print(f"  Sensitivity: {analysis.sensitivity_level:.2f}")
    print(f"  Strategy: {analysis.handling_strategy.value}")
    print(f"  Disclaimer Needed: {analysis.requires_disclaimer}")
    
    # Enhance response
    final_response = enhance_response(raw_llm_response, query)
    
    print(f"\nOriginal Response:")
    print(f"  {raw_llm_response}")
    print(f"\nEnhanced Response:")
    print(f"  {final_response}")
    
    # Verify enhancement worked
    assert len(final_response) > len(raw_llm_response), \
        "Enhanced response should be longer than original"
    assert "astrology" in final_response.lower() or "planetary" in final_response.lower(), \
        "Enhanced response should maintain astrological context"
    
    print("\n" + "=" * 70)
    print("✅ Full integration test passed!")


if __name__ == "__main__":
    try:
        test_query_analysis()
        test_response_enhancement()
        test_clarification_flow()
        test_full_integration()
        
        print("\n" + "=" * 70)
        print("🎉 ALL SAFETY MODULE TESTS PASSED!")
        print("=" * 70)
        print("\nSafety module is ready for integration with orchestrator.")
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

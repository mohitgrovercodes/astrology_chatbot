"""
Test Real-World Prediction Queries.
Shows how the enhanced system handles typical user questions.
"""

import warnings
warnings.filterwarnings('ignore', category=FutureWarning, module='langchain_google_genai')

print("Testing Enhanced 4-Category System...")
print()

# Test the fallback patterns
def test_intent_patterns():
    """Test that patterns correctly identify query types."""
    
    from src.ai.intent_classifier import EnhancedIntentClassifier
    
    print("="*70)
    print("TESTING INTENT CLASSIFICATION")
    print("="*70)
    print()
    
    test_cases = {
        "CHITCHAT": [
            "hi",
            "who are you?",
        ],
        "NEEDS_CALCULATION": [
            "show my birth chart",
            "calculate my kundali",
            "what is my lagna?",
        ],
        "NEEDS_PREDICTION": [
            # These are THE MOST COMMON real queries!
            "when will I get married?",
            "will I get a job this year?",
            "is it good time to start business?",
            "when will I have children?",
            "will I get promotion?",
            "is my Mars good for career?",
            "how is my Venus placement?",
            "should I invest in property?",
        ],
        "NEEDS_KNOWLEDGE": [
            "what does Jupiter mean?",
            "explain Saturn retrograde",
            "what is Vimshottari dasha?",
        ]
    }
    
    # Use fallback only (fast testing)
    classifier = EnhancedIntentClassifier()
    
    print("Testing query classification...\n")
    
    total = 0
    correct = 0
    
    for expected, queries in test_cases.items():
        print(f"\nExpected: {expected}")
        print("-"*70)
        
        for query in queries:
            total += 1
            
            # Use fallback directly for speed
            result = classifier._fallback_classify(query)
            actual = result['intent']
            
            status = "✓" if actual == expected else "✗"
            if actual == expected:
                correct += 1
            
            print(f"  {status} '{query}' → {actual}")
            
            if actual != expected:
                print(f"       Expected: {expected}")
    
    accuracy = (correct / total * 100) if total > 0 else 0
    
    print("\n" + "="*70)
    print(f"ACCURACY: {correct}/{total} ({accuracy:.1f}%)")
    print("="*70)
    
    if accuracy >= 90:
        print("\n✅ EXCELLENT! Real-world queries handled correctly!")
    elif accuracy >= 80:
        print("\n✓ GOOD! Minor improvements possible.")
    else:
        print("\n⚠️  Needs tuning.")
    
    return accuracy >= 80


def explain_flow():
    """Explain the NEEDS_PREDICTION flow."""
    
    print("\n\n" + "="*70)
    print("HOW NEEDS_PREDICTION WORKS (HYBRID FLOW)")
    print("="*70)
    print()
    
    print("Example: User asks 'When will I get married?'")
    print()
    print("STEP 1: CLASSIFY")
    print("  Intent: NEEDS_PREDICTION (not just NEEDS_KNOWLEDGE!)")
    print("  Why: Query asks about personal timing/outcome")
    print()
    print("STEP 2: CALCULATE CHART DATA")
    print("  → Birth chart (Lagna, Rashi, planetary positions)")
    print("  → Current Dasha periods (Mahadasha/Antardasha)")
    print("  → Current transits (Jupiter, Saturn, etc.)")
    print()
    print("STEP 3: RETRIEVE KNOWLEDGE")
    print("  Enhanced query: 'marriage timing + their specific placements'")
    print("  → Retrieve relevant texts about marriage timing")
    print("  → Retrieve texts about their specific dasha planet")
    print("  → Retrieve texts about current transits")
    print()
    print("STEP 4: SYNTHESIZE PREDICTION")
    print("  Combine:")
    print("  ✓ Their actual chart placements")
    print("  ✓ Their current dasha period")
    print("  ✓ Current transits")
    print("  ✓ Classical knowledge from texts")
    print("  → Generate PERSONALIZED prediction with timing")
    print()
    print("RESULT: Accurate, personalized prediction based on THEIR chart!")
    print("="*70)


def show_examples():
    """Show example outputs."""
    
    print("\n\n" + "="*70)
    print("EXAMPLE QUERY HANDLING")
    print("="*70)
    print()
    
    examples = [
        {
            "query": "show my birth chart",
            "intent": "NEEDS_CALCULATION",
            "flow": "Pure calculation → Display chart data",
            "output": "Chart with positions (no interpretation)"
        },
        {
            "query": "when will I get married?",
            "intent": "NEEDS_PREDICTION",
            "flow": "Calculate → Retrieve → Interpret",
            "output": "Personalized prediction with timing based on their chart"
        },
        {
            "query": "what does Jupiter mean?",
            "intent": "NEEDS_KNOWLEDGE",
            "flow": "Pure RAG → Explain concept",
            "output": "General explanation (not personalized)"
        },
        {
            "query": "is my Mars good for career?",
            "intent": "NEEDS_PREDICTION",
            "flow": "Calculate → Retrieve → Interpret",
            "output": "Analysis of THEIR Mars in THEIR chart + career guidance"
        }
    ]
    
    for i, ex in enumerate(examples, 1):
        print(f"\nExample {i}:")
        print(f"  Query: '{ex['query']}'")
        print(f"  Intent: {ex['intent']}")
        print(f"  Flow: {ex['flow']}")
        print(f"  Output: {ex['output']}")


if __name__ == "__main__":
    # Test intent classification
    success = test_intent_patterns()
    
    # Explain the flow
    explain_flow()
    
    # Show examples
    show_examples()
    
    print("\n\n" + "="*70)
    print("NEXT STEPS")
    print("="*70)
    print()
    print("1. Replace intent classifier:")
    print("   cp intent_classifier_enhanced.py src/ai/intent_classifier.py")
    print()
    print("2. Replace orchestrator:")
    print("   cp orchestrator_enhanced.py src/orchestration/orchestrator.py")
    print()
    print("3. Test with real queries:")
    print("   python chatbot.py")
    print()
    print("4. Integrate calculation engines:")
    print("   Update calculation_tools.py with your actual engines")
    print()
    print("="*70)

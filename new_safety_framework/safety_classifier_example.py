"""
Example Usage of Safety Classifier

Demonstrates how to use the safety classifier and handle different query types.

Usage:
    python examples/safety_classifier_example.py
"""

from src.safety import (
    create_safety_classifier,
    get_template,
    format_reframe_response,
    BlockReasons,
)


def demonstrate_safety_classifier():
    """Demonstrate safety classifier with various query types"""
    
    print("=" * 80)
    print("SAFETY CLASSIFIER DEMONSTRATION")
    print("=" * 80)
    print()
    
    # Create classifier
    print("Creating safety classifier...")
    classifier = create_safety_classifier()
    print("✓ Classifier initialized\n")
    
    # Test queries
    test_queries = [
        "When will I die?",
        "What health issues might I face with Mars in 6th house?",
        "Will I get rich?",
        "Is my boss going to get fired?",
        "What does Jupiter in 7th house mean?",
        "Should I invest in Bitcoin now?",
        "Which lottery numbers should I pick?",
        "When does my Venus Mahadasha start?",
        "Do I have cancer based on my chart?",
        "Why is God punishing me with bad luck?",
    ]
    
    # Classify each query
    for i, query in enumerate(test_queries, 1):
        print(f"\n{'=' * 80}")
        print(f"QUERY {i}: {query}")
        print(f"{'=' * 80}")
        
        # Classify
        result = classifier.classify(query)
        decision = result.decision
        
        # Display classification
        print(f"\n📊 CLASSIFICATION:")
        print(f"   Category:        {decision.category}")
        print(f"   Reason:          {decision.reason}")
        print(f"   Should Answer:   {decision.should_answer}")
        print(f"   Confidence:      {decision.confidence:.2f}")
        
        if decision.disclaimer_type:
            print(f"   Disclaimer:      {decision.disclaimer_type}")
        
        if decision.reframed_query:
            print(f"   Reframed Query:  {decision.reframed_query}")
        
        if result.requires_human_review:
            print(f"   ⚠️  FLAGGED FOR HUMAN REVIEW")
        
        # Display response
        print(f"\n💬 RESPONSE:")
        response = generate_response(result)
        print(f"{response}")
    
    print(f"\n{'=' * 80}")
    print("DEMONSTRATION COMPLETE")
    print(f"{'=' * 80}\n")


def generate_response(result) -> str:
    """Generate appropriate response based on safety check result"""
    
    decision = result.decision
    
    # Case 1: Hard or Soft Block
    if not result.should_proceed:
        template_key = result.get_template_key()
        return get_template(template_key)
    
    # Case 2: Reframe
    if decision.reframed_query:
        reframe_intro = format_reframe_response(
            original_query=result.original_query,
            reframed_query=decision.reframed_query
        )
        # In real system, this would be followed by the actual answer
        return reframe_intro + "\n\n[Answer would follow based on reframed query...]"
    
    # Case 3: Conditional (with disclaimer)
    if result.needs_disclaimer:
        # In real system, this would be the actual answer + disclaimer
        disclaimer = get_template(f"DISCLAIMER_{decision.disclaimer_type}")
        return f"[Answer would be provided here...]\n{disclaimer}"
    
    # Case 4: Safe - normal response
    return "[Normal astrological answer would be provided here...]"


def demonstrate_batch_classification():
    """Demonstrate batch classification"""
    
    print("\n" + "=" * 80)
    print("BATCH CLASSIFICATION DEMONSTRATION")
    print("=" * 80 + "\n")
    
    classifier = create_safety_classifier()
    
    queries = [
        "What does Saturn in 1st house mean?",
        "When will my father die?",
        "Is this a good time to start a business?",
    ]
    
    print(f"Classifying {len(queries)} queries in batch...\n")
    
    results = classifier.batch_classify(queries)
    
    # Summary table
    print("RESULTS SUMMARY:")
    print("-" * 80)
    print(f"{'Query':<40} {'Category':<15} {'Should Answer'}")
    print("-" * 80)
    
    for query, result in zip(queries, results):
        query_short = query[:37] + "..." if len(query) > 40 else query
        should_answer = "✓ Yes" if result.should_proceed else "✗ No"
        print(f"{query_short:<40} {result.decision.category:<15} {should_answer}")
    
    print("-" * 80)


def demonstrate_confidence_filtering():
    """Demonstrate queries flagged for human review"""
    
    print("\n" + "=" * 80)
    print("CONFIDENCE FILTERING DEMONSTRATION")
    print("=" * 80 + "\n")
    
    classifier = create_safety_classifier(confidence_threshold=0.8)
    
    # These queries might have lower confidence
    edge_cases = [
        "My doctor suggested surgery. What does my chart say about timing?",
        "When will my terminally ill parent pass peacefully?",
        "Should I marry him? His mother is very controlling.",
    ]
    
    print("Classifying edge cases that might need human review...\n")
    
    for query in edge_cases:
        result = classifier.classify(query)
        
        print(f"Query: {query}")
        print(f"  Category: {result.decision.category}")
        print(f"  Confidence: {result.decision.confidence:.2f}")
        
        if result.requires_human_review:
            print(f"  ⚠️  FLAGGED FOR HUMAN REVIEW (confidence < 0.8)")
        else:
            print(f"  ✓ No review needed")
        
        print()


if __name__ == "__main__":
    # Run demonstrations
    demonstrate_safety_classifier()
    demonstrate_batch_classification()
    demonstrate_confidence_filtering()
    
    print("\n✨ All demonstrations complete!\n")

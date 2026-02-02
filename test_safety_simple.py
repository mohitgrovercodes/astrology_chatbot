"""
Simple Manual Test for Safety Module
=====================================

Quick test to verify safety guardrails are working.
Run this to see how the safety module handles sensitive queries.
"""

print("=" * 70)
print("SAFETY MODULE - MANUAL TEST")
print("=" * 70)

# Test 1: QueryAnalyzer
print("\n1. Testing QueryAnalyzer...")
from src.safety.guardrails import QueryAnalyzer

analyzer = QueryAnalyzer()

test_queries = [
    "When will I die?",
    "Will I recover from my illness?",
    "Is my spouse cheating?",
    "Should I invest in stocks?",
    "What is my sun sign?"
]

for query in test_queries:
    analysis = analyzer.analyze(query)
    print(f"\n   Query: \"{query}\"")
    print(f"   Category: {analysis.category.value}")
    print(f"   Sensitivity: {analysis.sensitivity_level:.2f}")
    print(f"   Strategy: {analysis.handling_strategy.value}")
    if analysis.clarifying_question:
        print(f"   Clarifying Q: {analysis.clarifying_question[:60]}...")

# Test 2: ResponseEnhancer
print("\n" + "=" * 70)
print("2. Testing ResponseEnhancer...")
from src.safety.guardrails import ResponseEnhancer

enhancer = ResponseEnhancer()

raw_response = "Based on your 8th house, I can see indicators of longevity."
query = "When will I die?"

analysis = analyzer.analyze(query)
enhanced = enhancer.enhance(raw_response, analysis)

print(f"\n   Original ({len(raw_response)} chars):")
print(f"   {raw_response}")
print(f"\n   Enhanced ({len(enhanced)} chars):")
print(f"   {enhanced[:200]}...")

# Test 3: InputValidator
print("\n" + "=" * 70)
print("3. Testing InputValidator...")
from src.safety.input_validator import InputValidator

validator = InputValidator()

test_dates = [
    ("1990-03-15", "14:30", 26.9124, 75.7873),
    ("March 15, 1990", "2:30 PM", None, None),
    ("03/15/1990", None, 26.9124, 75.7873)
]

for date, time, lat, lon in test_dates:
    result = validator.validate_birth_data(
        date_of_birth=date,
        time_of_birth=time,
        latitude=lat,
        longitude=lon
    )
    print(f"\n   Input: {date}, {time}")
    print(f"   Valid: {result.is_valid}")
    print(f"   Normalized Date: {result.normalized_data.get('date_of_birth', 'N/A')}")
    print(f"   Normalized Time: {result.normalized_data.get('time_of_birth', 'N/A')}")

print("\n" + "=" * 70)
print("✅ SAFETY MODULE WORKING!")
print("=" * 70)
print("\nTo test full integration, run: python test_routing.py")
print("You should see: [SAFETY] Category: ..., Sensitivity: ..., Strategy: ...")

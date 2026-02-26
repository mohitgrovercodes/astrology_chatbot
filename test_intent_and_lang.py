# test_intent_and_lang.py
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))

# Fix Windows console encoding for Hindi characters
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from src.ai.intent_classifier import LLMIntentClassifier
from src.locales.language_detector import LanguageDetector

def test_intent():
    print("\n--- Testing Intent Classification ---")
    classifier = LLMIntentClassifier(use_cache=True)
    
    # Test cases that previously failed due to punctuation
    test_cases = [
        "When will I get married?",
        "When will I get married",
        "How is my career?",
        "How is my career"
    ]
    
    for q in test_cases:
        result = classifier.classify(q, {'date_of_birth': '1990-01-01'})
        print(f"Query: '{q}' -> Intent: {result['intent']} (Reason: {result['reasoning']})")
        
        if result['intent'] != "RAG_WITH_CALCULATION":
            print(f"FAILED: Expected RAG_WITH_CALCULATION for '{q}'")

def test_language():
    print("\n--- Testing Language Detection ---")
    detector = LanguageDetector()
    
    test_cases = [
        ("Meri shaadi kab hogi?", "hi-lat", "Hinglish with punctuation"),
        ("Mera career kaisa rahega", "hi-lat", "Hinglish without punctuation"),
        ("मेरा करियर कैसा रहेगा", "hi", "Native Hindi"),
        ("kab tak job milegi", "hi-lat", "New Hinglish markers")
    ]
    
    for text, expected, note in test_cases:
        got, conf = detector.detect_with_confidence(text)
        status = "PASS" if got == expected else "FAIL"
        print(f"[{status}] '{text}' ({note}) -> Got: {got}, Expected: {expected}, Conf: {conf:.2f}")

if __name__ == "__main__":
    test_intent()
    test_language()

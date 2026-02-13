# tests\test_language_switching.py
"""
Integration test for dynamic language switching within a conversation.

Tests that the chatbot can:
1. Detect different languages across multiple turns
2. Preserve conversation context when switching languages
3. Respond appropriately in the detected language
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from src.locales.language_detector import LanguageDetector


class TestDynamicLanguageSwitching:
    """Test language switching within the same conversation."""
    
    def test_english_to_hindi_switch(self):
        """Test switching from English to Hindi mid-conversation."""
        detector = LanguageDetector()
        
        # Turn 1: English
        query1 = "What is my moon sign?"
        lang1 = detector.detect(query1)
        assert lang1 == "en"
        
        # Turn 2: Switch to Hindi
        query2 = "Mere graha kaise hain?"
        lang2 = detector.detect(query2)
        assert lang2 == "hi-lat"
        
        # Verify each query is detected independently
        assert lang1 != lang2
    
    def test_hindi_to_tamil_switch(self):
        """Test switching from Hindi to Tamil."""
        detector = LanguageDetector()
        
        # Turn 1: Hindi
        query1 = "Mera kundli dekho"
        lang1 = detector.detect(query1)
        assert lang1 == "hi-lat"
        
        # Turn 2: Switch to Tamil
        query2 = "Enna rashi sollunga"
        lang2 = detector.detect(query2)
        assert lang2 == "ta-lat"
        
        assert lang1 != lang2
    
    def test_multilingual_conversation_flow(self):
        """Test a realistic multi-turn conversation with language switches."""
        detector = LanguageDetector()
        
        conversation = [
            ("What is my moon sign?", "en"),
            ("Mere sun sign kya hai?", "hi-lat"),
            ("Enna graha nilai?", "ta-lat"),
            ("Can you explain in English?", "en"),
            ("Aur dasha kaisi hai?", "hi-lat"),
        ]
        
        for query, expected_lang in conversation:
            detected = detector.detect(query)
            assert detected in [expected_lang, expected_lang.split('-')[0]], \
                f"Query: '{query}' expected {expected_lang}, got {detected}"
    
    def test_code_switching_within_query(self):
        """Test queries that mix languages (code-switching)."""
        detector = LanguageDetector()
        
        # Hindi-English mix (Hinglish)
        mixed_queries = [
            "Mera moon sign kya hai?",  # Hindi + English term
            "What is my rashi?",  # English + Hindi term
            "Batao my birth chart",  # Hindi + English
        ]
        
        for query in mixed_queries:
            lang = detector.detect(query)
            # Should detect as either Hindi or English (both acceptable)
            assert lang in ["hi-lat", "hi", "en"], \
                f"Mixed query '{query}' got unexpected language: {lang}"
    
    def test_language_detection_consistency(self):
        """Test that same query in same language is detected consistently."""
        detector = LanguageDetector()
        
        query = "Namaste, kaise ho aap?"
        
        # Detect same query multiple times
        detections = [detector.detect(query) for _ in range(5)]
        
        # All detections should be the same
        assert len(set(detections)) == 1, \
            f"Inconsistent detection: {detections}"
        assert detections[0] == "hi-lat"
    
    def test_short_query_after_long_query(self):
        """Test that short follow-up queries work after longer queries."""
        detector = LanguageDetector()
        
        # Turn 1: Long query in Hindi
        query1 = "Mera kundli dekho aur batao ki mere graha kaise hain"
        lang1 = detector.detect(query1)
        assert lang1 == "hi-lat"
        
        # Turn 2: Short follow-up (ambiguous)
        query2 = "Aur?"  # "And?" in Hindi
        lang2 = detector.detect(query2)
        # May detect as Hindi or default to English (both acceptable)
        assert lang2 in ["hi-lat", "hi", "en"]
    
    def test_native_script_to_romanized_switch(self):
        """Test switching from native script to romanized form."""
        detector = LanguageDetector()
        
        # Turn 1: Hindi in Devanagari
        query1 = "नमस्ते, कैसे हैं आप?"
        lang1 = detector.detect(query1)
        assert lang1 == "hi"
        
        # Turn 2: Hindi in Roman script
        query2 = "Acha theek hai, batao"
        lang2 = detector.detect(query2)
        assert lang2 == "hi-lat"
        
        # Both are Hindi, but different scripts
        assert lang1.startswith("hi") and lang2.startswith("hi")
    
    def test_romanized_to_native_script_switch(self):
        """Test switching from romanized to native script."""
        detector = LanguageDetector()
        
        # Turn 1: Tamil romanized
        query1 = "Vanakkam, epdi irukinga?"
        lang1 = detector.detect(query1)
        assert lang1 == "ta-lat"
        
        # Turn 2: Tamil native script
        query2 = "வணக்கம், நன்றி"
        lang2 = detector.detect(query2)
        assert lang2 == "ta"
        
        # Both are Tamil
        assert lang1.startswith("ta") and lang2.startswith("ta")
    
    def test_multiple_indian_languages_in_conversation(self):
        """Test switching between multiple Indian languages."""
        detector = LanguageDetector()
        
        queries = [
            ("Namaste, kaise ho?", "hi-lat"),  # Hindi
            ("Vanakkam, epdi irukku?", "ta-lat"),  # Tamil
            ("Ela unnaru meeru?", "te-lat"),  # Telugu
            ("Tame kem cho?", "gu-lat"),  # Gujarati
            ("Tumi kemon acho?", "bn-lat"),  # Bengali
        ]
        
        for query, expected_lang in queries:
            detected = detector.detect(query)
            assert detected == expected_lang, \
                f"Query: '{query}' expected {expected_lang}, got {detected}"
    
    def test_language_name_retrieval_for_switched_languages(self):
        """Test getting language names for switched languages."""
        detector = LanguageDetector()
        
        # Simulate conversation with switches
        languages = ["en", "hi-lat", "ta-lat", "te-lat", "en"]
        
        expected_names = [
            "English",
            "Hindi (Romanized)",
            "Tamil (Romanized)",
            "Telugu (Romanized)",
            "English"
        ]
        
        for lang, expected_name in zip(languages, expected_names):
            name = detector.get_language_name(lang)
            assert name == expected_name


class TestConversationContextPreservation:
    """Test that conversation context is preserved across language switches."""
    
    def test_language_independence_of_context(self):
        """Verify that language detection doesn't affect context storage."""
        detector = LanguageDetector()
        
        # Simulate conversation history structure
        conversation_history = []
        
        # Turn 1: English
        query1 = "What is my moon sign?"
        lang1 = detector.detect(query1)
        conversation_history.append({
            "role": "user",
            "content": query1,
            "detected_language": lang1
        })
        conversation_history.append({
            "role": "assistant",
            "content": "Your moon sign is Taurus.",
            "language": lang1
        })
        
        # Turn 2: Hindi
        query2 = "Mere graha kaise hain?"
        lang2 = detector.detect(query2)
        conversation_history.append({
            "role": "user",
            "content": query2,
            "detected_language": lang2
        })
        
        # Verify history is preserved
        assert len(conversation_history) == 3
        assert conversation_history[0]["detected_language"] == "en"
        assert conversation_history[2]["detected_language"] == "hi-lat"
        
        # Verify we can access previous context regardless of language
        previous_query = conversation_history[0]["content"]
        assert "moon sign" in previous_query


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

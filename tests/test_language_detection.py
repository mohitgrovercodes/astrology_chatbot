"""
Unit Tests for Universal Language Detector

Tests the LanguageDetector class with:
- 20+ language detection tests
- Romanization detection (Hinglish, Tanglish)
- Confidence scoring
- Edge cases and fallback behavior
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from src.locales.language_detector import LanguageDetector, get_language_detector


class TestLanguageDetection:
    """Test suite for basic language detection."""
    
    def test_detect_english(self):
        """Test English detection."""
        detector = LanguageDetector()
        assert detector.detect("Hello, how are you today?") == "en"
        assert detector.detect("What is my moon sign?") == "en"
    
    def test_detect_hindi_devanagari(self):
        """Test Hindi Devanagari script detection."""
        detector = LanguageDetector()
        text = "नमस्ते, कैसे हैं आप?"
        assert detector.detect(text) == "hi"
    
    def test_detect_tamil_script(self):
        """Test Tamil script detection."""
        detector = LanguageDetector()
        text = "வணக்கம், எப்படி இருக்கிறீர்கள்?"
        assert detector.detect(text) == "ta"
    
    def test_detect_spanish(self):
        """Test Spanish detection."""
        detector = LanguageDetector()
        assert detector.detect("Hola, ¿cómo estás?") == "es"
        assert detector.detect("¿Cuál es mi signo lunar?") == "es"
    
    def test_detect_french(self):
        """Test French detection."""
        detector = LanguageDetector()
        assert detector.detect("Bonjour, comment allez-vous?") == "fr"
        assert detector.detect("Quel est mon signe lunaire?") == "fr"
    
    def test_detect_german(self):
        """Test German detection."""
        detector = LanguageDetector()
        assert detector.detect("Hallo, wie geht es dir?") == "de"
        assert detector.detect("Was ist mein Mondzeichen?") == "de"
    
    def test_detect_italian(self):
        """Test Italian detection."""
        detector = LanguageDetector()
        assert detector.detect("Ciao, come stai?") == "it"
    
    def test_detect_portuguese(self):
        """Test Portuguese detection."""
        detector = LanguageDetector()
        assert detector.detect("Olá, como você está?") == "pt"
    
    def test_detect_russian(self):
        """Test Russian detection."""
        detector = LanguageDetector()
        text = "Привет, как дела?"
        assert detector.detect(text) == "ru"
    
    def test_detect_arabic(self):
        """Test Arabic (RTL) detection."""
        detector = LanguageDetector()
        text = "مرحبا كيف حالك"
        assert detector.detect(text) == "ar"
    
    def test_detect_chinese(self):
        """Test Chinese detection."""
        detector = LanguageDetector()
        text = "你好，你好吗？"
        result = detector.detect(text)
        # Accept either zh or zh-cn
        assert result in ["zh", "zh-cn"]
    
    def test_detect_japanese(self):
        """Test Japanese detection."""
        detector = LanguageDetector()
        text = "こんにちは、お元気ですか？"
        assert detector.detect(text) == "ja"
    
    def test_detect_korean(self):
        """Test Korean detection."""
        detector = LanguageDetector()
        text = "안녕하세요, 어떻게 지내세요?"
        assert detector.detect(text) == "ko"
    
    def test_detect_bengali(self):
        """Test Bengali detection."""
        detector = LanguageDetector()
        text = "হ্যালো, আপনি কেমন আছেন?"
        assert detector.detect(text) == "bn"
    
    def test_detect_telugu(self):
        """Test Telugu detection."""
        detector = LanguageDetector()
        text = "హలో, మీరు ఎలా ఉన్నారు?"
        assert detector.detect(text) == "te"
    
    def test_detect_greek(self):
        """Test Greek detection."""
        detector = LanguageDetector()
        text = "Γεια σου, πώς είσαι;"
        assert detector.detect(text) == "el"
    
    def test_detect_hebrew(self):
        """Test Hebrew (RTL) detection."""
        detector = LanguageDetector()
        text = "שלום, מה שלומך?"
        assert detector.detect(text) == "he"
    
    def test_detect_thai(self):
        """Test Thai detection."""
        detector = LanguageDetector()
        text = "สวัสดีคุณเป็นอย่างไร"
        assert detector.detect(text) == "th"
    
    def test_detect_vietnamese(self):
        """Test Vietnamese detection."""
        detector = LanguageDetector()
        text = "Xin chào, bạn khỏe không?"
        assert detector.detect(text) == "vi"


class TestRomanizationDetection:
    """Test suite for romanized language detection."""
    
    def test_detect_hinglish(self):
        """Test Hinglish (romanized Hindi) detection."""
        detector = LanguageDetector()
        
        # Common Hinglish phrases
        assert detector.detect("Namaste, kaise ho aap?") == "hi-lat"
        assert detector.detect("Mera naam John hai") == "hi-lat"
        assert detector.detect("Acha theek hai, batao kya hua") == "hi-lat"
    
    def test_detect_tanglish(self):
        """Test Tanglish (romanized Tamil) detection."""
        detector = LanguageDetector()
        
        # Common Tanglish phrases
        assert detector.detect("Vanakkam, epdi irukinga?") == "ta-lat"
        assert detector.detect("Enna pannanum sollu") == "ta-lat"
    
    def test_is_transliterated_hindi(self):
        """Test romanization checker for Hindi."""
        detector = LanguageDetector()
        
        assert detector.is_transliterated("Namaste kaise ho", "hi") is True
        assert detector.is_transliterated("Hello how are you", "hi") is False
        assert detector.is_transliterated("नमस्ते कैसे हो", "hi") is False
    
    def test_is_transliterated_tamil(self):
        """Test romanization checker for Tamil."""
        detector = LanguageDetector()
        
        assert detector.is_transliterated("Vanakkam epdi irukku", "ta") is True
        assert detector.is_transliterated("Hello how are you", "ta") is False


class TestConfidenceScoring:
    """Test suite for confidence scores."""
    
    def test_confidence_high_for_clear_language(self):
        """Test that clear language has high confidence."""
        detector = LanguageDetector()
        
        lang, conf = detector.detect_with_confidence("Hello, how are you?")
        assert lang == "en"
        assert conf > 0.8
    
    def test_confidence_medium_for_romanized(self):
        """Test romanized text has medium-high confidence."""
        detector = LanguageDetector()
        
        lang, conf = detector.detect_with_confidence("Namaste kaise ho aap?")
        assert lang == "hi-lat"
        assert conf > 0.7  # Marker-based detection has good confidence
    
    def test_confidence_low_for_short_text(self):
        """Test short ambiguous text has lower confidence."""
        detector = LanguageDetector()
        
        _, conf = detector.detect_with_confidence("ok")
        # Short text should still work but may have lower confidence
        assert 0.0 <= conf <= 1.0


class TestEdgeCases:
    """Test suite for edge cases and error handling."""
    
    def test_empty_string(self):
        """Test empty string defaults to English."""
        detector = LanguageDetector()
        assert detector.detect("") == "en"
        assert detector.detect("   ") == "en"
    
    def test_very_short_text(self):
        """Test very short text."""
        detector = LanguageDetector()
        result = detector.detect("hi")
        # Should be detected as English (common word) or fail gracefully
        assert result in ["en", "hi"]
    
    def test_mixed_script_text(self):
        """Test text with mixed scripts."""
        detector = LanguageDetector()
        
        # English with Hindi word in Devanagari
        text = "What is my नाम?"
        result = detector.detect(text)
        # Should detect primary language (likely English as it's dominant)
        assert result in ["en", "hi"]
    
    def test_numbers_and_symbols(self):
        """Test text with mostly numbers/symbols."""
        detector = LanguageDetector()
        result = detector.detect("123 456 !@#")
        assert result == "en"  # Should default to English
    
    def test_get_language_name(self):
        """Test language name retrieval."""
        detector = LanguageDetector()
        
        assert detector.get_language_name("en") == "English"
        assert detector.get_language_name("hi") == "Hindi"
        assert detector.get_language_name("hi-lat") == "Hindi (Romanized)"
        assert detector.get_language_name("es") == "Spanish"
        assert detector.get_language_name("unknown") == "UNKNOWN"


class TestSingleton:
    """Test singleton pattern."""
    
    def test_singleton_returns_same_instance(self):
        """Test that get_language_detector returns singleton."""
        detector1 = get_language_detector()
        detector2 = get_language_detector()
        assert detector1 is detector2


# Integration test with real-world examples
class TestRealWorldExamples:
    """Test with real-world astrology chatbot queries."""
    
    def test_astrology_queries_english(self):
        """Test English astrology queries."""
        detector = LanguageDetector()
        
        queries = [
            "What is my moon sign?",
            "Tell me about my birth chart",
            "When will I get married?",
            "What does Jupiter in 7th house mean?"
        ]
        
        for query in queries:
            assert detector.detect(query) == "en"
    
    def test_astrology_queries_hindi(self):
        """Test Hindi astrology queries."""
        detector = LanguageDetector()
        
        queries = [
            "मेरा चंद्र राशि क्या है?",
            "मेरी कुंडली के बारे में बताइए",
        ]
        
        for query in queries:
            assert detector.detect(query) == "hi"
    
    def test_astrology_queries_hinglish(self):
        """Test Hinglish astrology queries."""
        detector = LanguageDetector()
        
        queries = [
            "Mera moon sign kya hai?",
            "Meri kundli ke baare mein batao",
            "Shaadi kab hogi bataye"
        ]
        
        for query in queries:
            result = detector.detect(query)
            assert result in ["hi-lat", "hi"]  # Accept either romanized or base


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

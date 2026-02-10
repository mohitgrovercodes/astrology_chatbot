"""
Additional tests for Indian languages (native scripts and romanized)
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from src.locales.language_detector import LanguageDetector


class TestIndianLanguagesNativeScript:
    """Test detection of Indian languages in their native scripts."""
    
    def test_detect_hindi_devanagari(self):
        """Test Hindi in Devanagari script."""
        detector = LanguageDetector()
        assert detector.detect("नमस्ते, कैसे हैं आप?") == "hi"
        assert detector.detect("मेरा चंद्र राशि क्या है?") == "hi"
    
    def test_detect_bengali_script(self):
        """Test Bengali in Bengali script."""
        detector = LanguageDetector()
        text = "হ্যালো, আপনি কেমন আছেন?"
        assert detector.detect(text) == "bn"
    
    def test_detect_tamil_script(self):
        """Test Tamil in Tamil script."""
        detector = LanguageDetector()
        text = "வணக்கம், எப்படி இருக்கிறீர்கள்?"
        assert detector.detect(text) == "ta"
    
    def test_detect_telugu_script(self):
        """Test Telugu in Telugu script."""
        detector = LanguageDetector()
        text = "హలో, మీరు ఎలా ఉన్నారు?"
        assert detector.detect(text) == "te"
    
    def test_detect_gujarati_script(self):
        """Test Gujarati in Gujarati script."""
        detector = LanguageDetector()
        text = "નમસ્તે, તમે કેમ છો?"
        assert detector.detect(text) == "gu"
    
    def test_detect_kannada_script(self):
        """Test Kannada in Kannada script."""
        detector = LanguageDetector()
        text = "ನಮಸ್ಕಾರ, ನೀವು ಹೇಗಿದ್ದೀರಿ?"
        assert detector.detect(text) == "kn"
    
    def test_detect_malayalam_script(self):
        """Test Malayalam in Malayalam script."""
        detector = LanguageDetector()
        text = "ഹലോ, നിങ്ങൾ എങ്ങനെയുണ്ട്?"
        assert detector.detect(text) == "ml"
    
    def test_detect_punjabi_gurmukhi(self):
        """Test Punjabi in Gurmukhi script."""
        detector = LanguageDetector()
        text = "ਸਤ ਸ੍ਰੀ ਅਕਾਲ, ਤੁਸੀਂ ਕਿਵੇਂ ਹੋ?"
        assert detector.detect(text) == "pa"
    
    def test_detect_marathi_devanagari(self):
        """Test Marathi in Devanagari script."""
        detector = LanguageDetector()
        text = "नमस्कार, तुम्ही कसे आहात?"
        assert detector.detect(text) == "mr"
    
    def test_detect_urdu_script(self):
        """Test Urdu in Perso-Arabic script."""
        detector = LanguageDetector()
        text = "السلام علیکم، آپ کیسے ہیں؟"
        assert detector.detect(text) == "ur"


class TestIndianLanguagesRomanized:
    """Test detection of romanized Indian languages."""
    
    def test_detect_hinglish(self):
        """Test Hinglish (romanized Hindi)."""
        detector = LanguageDetector()
        
        queries = [
            "Namaste, kaise ho aap?",
            "Mera naam John hai",
            "Acha theek hai, batao kya hua",
            "Meri kundli dekho",
            "Mere graha kaise hain?"
        ]
        
        for query in queries:
            result = detector.detect(query)
            assert result == "hi-lat", f"Failed for: {query}, got {result}"
    
    def test_detect_tanglish(self):
        """Test Tanglish (romanized Tamil)."""
        detector = LanguageDetector()
        
        queries = [
            "Vanakkam, epdi irukinga?",
            "Enna pannanum sollu",
            "Naan romba nalla irukken",
            "Paaru enna nadakkudhu"
        ]
        
        for query in queries:
            result = detector.detect(query)
            assert result == "ta-lat", f"Failed for: {query}, got {result}"
    
    def test_detect_tenglish(self):
        """Test Tenglish (romanized Telugu)."""
        detector = LanguageDetector()
        
        queries = [
            "Ela unnaru meeru?",
            "Naaku cheppandi",
            "Chaala baagundi",
            "Enti chesthe undhi?"
        ]
        
        for query in queries:
            result = detector.detect(query)
            assert result == "te-lat", f"Failed for: {query}, got {result}"
    
    def test_detect_romanized_marathi(self):
        """Test romanized Marathi."""
        detector = LanguageDetector()
        
        queries = [
            "Kay mhanas tu?",
            "Mala sang kay zala",
            "Mi kasa aahe?",
            "Tumhi kuthey aahat?"
        ]
        
        for query in queries:
            result = detector.detect(query)
            assert result == "mr-lat", f"Failed for: {query}, got {result}"
    
    def test_detect_romanized_bengali(self):
        """Test romanized Bengali."""
        detector = LanguageDetector()
        
        queries = [
            "Tumi kemon acho?",
            "Ami bhalo achi",
            "Bolo ki hoyeche",
            "Amar naam ki?"
        ]
        
        for query in queries:
            result = detector.detect(query)
            assert result == "bn-lat", f"Failed for: {query}, got {result}"
    
    def test_detect_romanized_gujarati(self):
        """Test romanized Gujarati."""
        detector = LanguageDetector()
        
        queries = [
            "Tame kem cho?",
            "Hun saras chhu",
            "Kaho shu thayun",
            "Mane jovo"
        ]
        
        for query in queries:
            result = detector.detect(query)
            assert result == "gu-lat", f"Failed for: {query}, got {result}"
    
    def test_detect_romanized_kannada(self):
        """Test romanized Kannada."""
        detector = LanguageDetector()
        
        queries = [
            "Nivu hege iddeeri?",
            "Nanage heli",
            "Thumba chennagi ide",
            "Yenu maadthiri?"
        ]
        
        for query in queries:
            result = detector.detect(query)
            assert result == "kn-lat", f"Failed for: {query}, got {result}"
    
    def test_detect_romanized_malayalam(self):
        """Test romanized Malayalam (Manglish)."""
        detector = LanguageDetector()
        
        queries = [
            "Ningal engane undu?",
            "Enikku parayoo",
            "Valare nannaayi",
            "Enthu cheyyum?"
        ]
        
        for query in queries:
            result = detector.detect(query)
            assert result == "ml-lat", f"Failed for: {query}, got {result}"
    
    def test_detect_romanized_punjabi(self):
        """Test romanized Punjabi (Punglish)."""
        detector = LanguageDetector()
        
        queries = [
            "Tusi kiven ho?",
            "Main theek haan",
            "Dass ki hoya",
            "Menu sun"
        ]
        
        for query in queries:
            result = detector.detect(query)
            assert result == "pa-lat", f"Failed for: {query}, got {result}"
    
    def test_detect_romanized_urdu(self):
        """Test romanized Urdu."""
        detector = LanguageDetector()
        
        queries = [
            "Aap kaise hain?",
            "Mujhe bataiye",
            "Bilkul theek hai",
            "Dekhiye kya hua"
        ]
        
        for query in queries:
            result = detector.detect(query)
            assert result == "ur-lat", f"Failed for: {query}, got {result}"


class TestIndianLanguageAstrologyQueries:
    """Test with real-world Indian language astrology queries."""
    
    def test_hindi_astrology_queries(self):
        """Test Hindi astrology queries."""
        detector = LanguageDetector()
        
        queries = [
            "Mera moon sign kya hai?",
            "Meri kundli ke baare mein batao",
            "Shaadi kab hogi bataye",
            "Mere graha kaise hain?",
            "Dasha kaisi chal rahi hai?"
        ]
        
        for query in queries:
            result = detector.detect(query)
            assert result in ["hi-lat", "hi"], f"Failed for: {query}, got {result}"
    
    def test_tamil_astrology_queries(self):
        """Test Tamil astrology queries."""
        detector = LanguageDetector()
        
        queries = [
            "Enna rasi sollunga",
            "Eppadi irukku en jathagam",
            "Kalyanam eppo nadakkum",
            "Graha nilai enna"
        ]
        
        for query in queries:
            result = detector.detect(query)
            assert result in ["ta-lat", "ta"], f"Failed for: {query}, got {result}"
    
    def test_telugu_astrology_queries(self):
        """Test Telugu astrology queries."""
        detector = LanguageDetector()
        
        queries = [
            "Naa rasi enti?",
            "Naa jathakam ela undi?",
            "Pelli eppudu avuthundi?",
            "Graha sthithi cheppandi"
        ]
        
        for query in queries:
            result = detector.detect(query)
            assert result in ["te-lat", "te"], f"Failed for: {query}, got {result}"


class TestLanguageNameMapping:
    """Test language name retrieval for Indian languages."""
    
    def test_indian_language_names(self):
        """Test that all Indian languages have proper names."""
        detector = LanguageDetector()
        
        indian_langs = {
            'hi': 'Hindi',
            'bn': 'Bengali',
            'te': 'Telugu',
            'mr': 'Marathi',
            'ta': 'Tamil',
            'ur': 'Urdu',
            'gu': 'Gujarati',
            'kn': 'Kannada',
            'ml': 'Malayalam',
            'pa': 'Punjabi',
        }
        
        for code, expected_name in indian_langs.items():
            assert detector.get_language_name(code) == expected_name
    
    def test_romanized_indian_language_names(self):
        """Test romanized variant names."""
        detector = LanguageDetector()
        
        assert detector.get_language_name('hi-lat') == 'Hindi (Romanized)'
        assert detector.get_language_name('ta-lat') == 'Tamil (Romanized)'
        assert detector.get_language_name('te-lat') == 'Telugu (Romanized)'
        assert detector.get_language_name('bn-lat') == 'Bengali (Romanized)'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

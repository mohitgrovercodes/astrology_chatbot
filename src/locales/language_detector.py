# src/locales/language_detector.py
"""
Language Detection Module

Supports 7 Indian languages + English, each with native and romanized scripts.
Default: English (en)
"""

import re
from typing import Optional, Tuple, Dict
from langdetect import detect, detect_langs, LangDetectException


class LanguageDetector:
    """
    Language detector for NakshatraAI.
    Default language: English (en)
    """
    
    # Supported languages
    LANGUAGE_NAMES = {
        'en': 'English',
        'hi': 'Hindi',
        'mr': 'Marathi',
        'pa': 'Punjabi',
        'ta': 'Tamil',
        'te': 'Telugu',
        'ml': 'Malayalam',
        # Romanized Variants
        'hi-lat': 'Hinglish',
        'mr-lat': 'Marathi (Romanized)',
        'pa-lat': 'Punjabi (Romanized)',
        'ta-lat': 'Tanglish',
        'te-lat': 'Telugu (Romanized)',
        'ml-lat': 'Malayalam (Romanized)'
    }

    ALLOWED_CODES = set(LANGUAGE_NAMES.keys())

    # Common English greetings and phrases (return English, not default)
    ENGLISH_GREETINGS = {
        'hello', 'hi', 'hey', 'good morning', 'good afternoon', 'good evening',
        'thanks', 'thank you', 'please', 'help', 'bye', 'goodbye'
    }
    
    # Strong English indicators
    ENGLISH_KEYWORDS = {
        'what', 'when', 'where', 'why', 'how', 'will', 'can', 'could',
        'would', 'should', 'about', 'house', 'planet', 'chart', 'birth',
        'marriage', 'career', 'money', 'health', 'children', 'the', 'is',
        'are', 'my', 'me', 'you', 'your', 'get', 'have', 'do', 'does'
    }

    # Romanized Indian language markers
    ROMANIZATION_MARKERS = {
        'hi': [
            'namaste', 'namaskar', 'kaise', 'batao', 'bataye',
            'hai', 'hoon', 'hain', 'tha', 'thi', 'the',
            'kya', 'kyun', 'kab', 'kahan', 'kaun',
            'mera', 'meri', 'mere', 'tera', 'teri', 'apka', 'apki',
            'nahi', 'nahin', 'karo', 'kariye',
            'acha', 'theek', 'thik', 'bas', 'phir',
            'yeh', 'woh', 'yahan', 'wahan',
            'kundli', 'graha', 'rashi', 'nakshatra', 'dasha', 'jyotish'
        ],
        'ta': [
            'vanakkam', 'epdi', 'eppadi', 'enna', 'eppo',
            'naan', 'nee', 'avan', 'aval',
            'enakku', 'unakku', 'irukku', 'pannanum',
            'illa', 'illai', 'aama', 'romba', 'rasi'
        ],
        'te': [
            'namaskaram', 'ela', 'eppudu', 'ekkada', 'evaru',
            'nenu', 'meeru', 'vaadu', 'aame',
            'naaku', 'neeku', 'cheppu', 'undhi',
            'kaadu', 'ledhu', 'avunu', 'chaala', 'jathakam'
        ],
        'mr': [
            'namaskar', 'kay', 'kasa', 'kon',
            'mi', 'tu', 'to', 'ti', 'tumhi',
            'mala', 'tula', 'sang', 'kar',
            'nahi', 'hoy', 'bara', 'khup', 'patrika'
        ],
        'ml': [
            'namaskaram', 'entha', 'engane', 'eppol', 'evide',
            'njan', 'nee', 'ningal', 'avan', 'aval',
            'enikku', 'ninakku', 'parayoo', 'illa', 'valare'
        ],
        'pa': [
            'sat', 'sri', 'akal', 'kiven', 'kado', 'kithe',
            'main', 'tu', 'tusi', 'oh',
            'menu', 'tenu', 'dass', 'karo',
            'nahi', 'haan', 'theek', 'changa', 'bahut'
        ],
    }

    # Global exclusion (words that appear in both English and Indian languages)
    GLOBAL_EXCLUSION = {
        'to', 'is', 'me', 'do', 'we', 'us', 'an', 'at', 'by', 'he', 'so', 'it', 'or', 'as'
    }
    
    def __init__(self, llm=None, default_language: str = 'en'):
        """
        Initialize detector.
        
        Args:
            llm: Optional LLM for fallback detection
            default_language: Default language code (default: 'en' for English)
        """
        self.llm = llm
        self.default_language = default_language
        print(f"[LANG] Initialized with default language: {self.LANGUAGE_NAMES.get(default_language, default_language)}")
        
    def detect(self, text: str) -> str:
        """
        Detect language with multi-stage approach.
        
        Priority:
        1. English detection (strong keywords)
        2. Romanization detection (Indian languages)
        3. Library detection
        4. Fallback to default (English)
        """
        if not text or len(text.strip()) < 2:
            return self.default_language
        
        text_lower = text.lower().strip()
        words = set(re.findall(r'\w+', text_lower))
        
        # STEP 1: Strong English detection
        if self._is_english(text_lower, words):
            return 'en'
        
        # STEP 2: Romanized Indian language detection
        romanized_lang = self._detect_romanization(text)
        if romanized_lang:
            lat_code = f"{romanized_lang}-lat"
            if lat_code in self.ALLOWED_CODES:
                return lat_code
            if romanized_lang in self.ALLOWED_CODES:
                return romanized_lang
        
        # STEP 3: Library detection
        try:
            lang_code = detect(text)
            normalized = self._normalize_code(lang_code)
            
            if normalized in self.ALLOWED_CODES:
                return normalized
            
            # Unsupported language detected - fallback to default
            return self.default_language
            
        except LangDetectException:
            # STEP 4: LLM fallback
            if self.llm:
                try:
                    detected = self._llm_detect(text)
                    if detected in self.ALLOWED_CODES:
                        return detected
                except:
                    pass
            
            return self.default_language
    
    def detect_with_confidence(self, text: str) -> Tuple[str, float]:
        """
        Detect language with confidence score.
        
        Args:
            text: Text to detect language for
            
        Returns:
            Tuple of (language_code, confidence_score)
            
        Example:
            >>> detector.detect_with_confidence("hello")
            ('en', 0.9)
            >>> detector.detect_with_confidence("Meri shaadi kab hogi?")
            ('hi-lat', 0.85)
        """
        if not text or len(text.strip()) < 2:
            return (self.default_language, 0.5)
        
        text_lower = text.lower().strip()
        words = set(re.findall(r'\w+', text_lower))
        
        # STEP 1: Strong English detection
        if self._is_english(text_lower, words):
            return ('en', 0.9)
        
        # STEP 2: Romanized Indian language detection
        romanized_lang = self._detect_romanization(text)
        if romanized_lang:
            lat_code = f"{romanized_lang}-lat"
            if lat_code in self.ALLOWED_CODES:
                return (lat_code, 0.85)
            if romanized_lang in self.ALLOWED_CODES:
                return (romanized_lang, 0.85)
        
        # STEP 3: Library detection with confidence
        try:
            langs = detect_langs(text)
            if langs:
                top_lang = langs[0]
                code = self._normalize_code(top_lang.lang)
                confidence = top_lang.prob
                
                if code in self.ALLOWED_CODES:
                    return (code, confidence)
                
                # Unsupported language - return default
                return (self.default_language, 0.3)
            
        except LangDetectException:
            # Library failed, try LLM
            if self.llm:
                try:
                    detected = self._llm_detect(text)
                    if detected in self.ALLOWED_CODES:
                        return (detected, 0.7)
                except:
                    pass
        
        # STEP 4: Fallback to default with low confidence
        return (self.default_language, 0.3)

    def _is_english(self, text_lower: str, words: set) -> bool:
        """
        Detect if text is English with high confidence.
        
        Returns True if:
        - Contains English greetings, OR
        - >40% of words are strong English keywords
        """
        # Check for English greetings
        if any(greeting in text_lower for greeting in self.ENGLISH_GREETINGS):
            # Make sure it's not mixed with strong Indian markers
            has_indian_markers = any(
                marker in text_lower 
                for markers in self.ROMANIZATION_MARKERS.values() 
                for marker in markers[:5]  # Check first 5 markers of each language
            )
            if not has_indian_markers:
                return True
        
        # Check English keyword density
        if len(words) > 0:
            english_count = sum(1 for w in words if w in self.ENGLISH_KEYWORDS)
            ratio = english_count / len(words)
            
            # If >40% English keywords, it's English
            if ratio > 0.4:
                return True
        
        return False
    
    def _detect_romanization(self, text: str) -> Optional[str]:
        """
        Detect romanized Indian language.
        
        Returns base language code if romanization detected.
        """
        if not re.search(r'[a-zA-Z]', text):
            return None
        
        text_lower = text.lower()
        match_counts: Dict[str, int] = {}
        
        for lang_code, markers in self.ROMANIZATION_MARKERS.items():
            count = sum(
                1 for marker in markers 
                if marker not in self.GLOBAL_EXCLUSION 
                and re.search(r'\b' + marker + r'\b', text_lower)
            )
            if count > 0:
                match_counts[lang_code] = count
        
        if match_counts:
            best_lang = max(match_counts.items(), key=lambda x: x[1])
            if best_lang[1] >= 1:
                return best_lang[0]
        
        return None
    
    def _normalize_code(self, lang_code: str) -> str:
        """Normalize language code to ISO 639-1."""
        normalized = lang_code.lower()
        return normalized[:2] if len(normalized) > 2 and '-' not in normalized else normalized
    
    def _llm_detect(self, text: str) -> str:
        """Use LLM for edge cases."""
        if not self.llm:
            return self.default_language
        
        prompt = f"""Identify the PRIMARY language of the following text.
RESTRICT your answer to one of these codes: {', '.join(sorted(self.LANGUAGE_NAMES.keys()))}.

If the text is an Indian language written in ROMAN SCRIPT, append '-lat' (e.g., 'hi-lat', 'ta-lat').

Text: "{text}"

Language code:"""
        
        try:
            response = self.llm.invoke(prompt)
            detected = response.content.strip().lower() if hasattr(response, 'content') else str(response).strip().lower()
            detected = detected.split()[0].split('\n')[0].replace('"', '').replace("'", "")
            
            if detected in self.ALLOWED_CODES:
                return detected
            
            return self.default_language
            
        except:
            return self.default_language
    
    def get_language_name(self, lang_code: str) -> str:
        """Get human-readable language name."""
        return self.LANGUAGE_NAMES.get(lang_code, lang_code.upper())


# Singleton instance
_detector_instance = None


def get_language_detector(llm=None, default_language: str = 'en') -> LanguageDetector:
    """Get singleton LanguageDetector instance."""
    global _detector_instance
    if _detector_instance is None:
        _detector_instance = LanguageDetector(llm=llm, default_language=default_language)
    return _detector_instance


if __name__ == "__main__":
    """Test the language detector."""
    print("=" * 70)
    print("LANGUAGE DETECTOR TEST")
    print("=" * 70)
    
    detector = LanguageDetector(default_language='en')
    
    test_cases = [
        ("hello", "en"),
        ("hi", "en"),
        ("When will I get married?", "en"),
        ("What is my birth chart?", "en"),
        ("How are you?", "en"),
        ("Meri shaadi kab hogi?", "hi-lat"),
        ("Mera career kaisa hai?", "hi-lat"),
        ("Kundli dekhiye", "hi-lat"),
        ("मेरी शादी कब होगी?", "hi"),
        ("En thirumanam eppodhu?", "ta-lat"),
    ]
    
    print("\nTest Results:\n")
    passed = 0
    failed = 0
    
    for text, expected in test_cases:
        detected = detector.detect(text)
        status = "✅" if detected == expected else "❌"
        if detected == expected:
            passed += 1
        else:
            failed += 1
        print(f"{status} '{text[:40]:<40}' → {detected:<8} (expected: {expected})")
    
    print(f"\n{passed} passed, {failed} failed")
    print("=" * 70)
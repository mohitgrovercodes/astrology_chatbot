# src/locales/language_detector.py
"""
Universal Language Detection Module

Provides robust language detection using:
1. Fast library-based detection (langdetect) for 8 supported languages
2. LLM fallback for ambiguous cases (code-switching, transliteration)
3. Romanization detection (Hinglish, Tanglish, etc.)

Supports ONLY 8 languages: English, Hindi, Marathi, Punjabi, Tamil, Telugu, Malayalam
Each with native and romanized variants.

Default language: hi-lat (Hinglish)
"""

import re
from typing import Optional, Tuple, Dict
from langdetect import detect, detect_langs, LangDetectException


class LanguageDetector:
    """
    Production-grade language detector with library + LLM hybrid approach.
    Fixed to support only 8 languages with default Hinglish.
    """
    
    # THE 8 FIXED SUPPORTED LANGUAGES (AS PER ARCHITECTURAL REQUIREMENT)
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

    # Internal whitelist for allowed ISO-639 codes (plus romanized variants)
    ALLOWED_CODES = set(LANGUAGE_NAMES.keys())

    # Common English phrases that are often mis-detected by langdetect
    # These will return Hinglish (default) instead of English
    ENGLISH_BYPASS = {
        'ok', 'okay', 'yes', 'no', 'thanks', 'thank you', 'hello', 'hi',
        'tell me', 'more', 'detail', 'explain', 'suggest', 'what', 'how',
        'where', 'when', 'who', 'why', 'please', 'help', 'bye', 'goodbye'
    }

    # Global Exclusion List: Words that should NEVER be counted as Indian markers
    GLOBAL_EXCLUSION = {
        'to', 'is', 'me', 'do', 'we', 'us', 'an', 'at', 'by', 'he', 'so', 'it', 'or', 'as'
    }
    
    # Romanization markers for Indian languages
    ROMANIZATION_MARKERS = {
        # Hindi/Hindustani (most common romanized Indian language)
        'hi': [
            'namaste', 'namaskar', 'shubh', 'kaise', 'batao', 'bataye',
            'hai', 'hein', 'hoon', 'hain', 'ho', 'tha', 'thi', 'the', 'thee',
            'kya', 'kyun', 'kaise', 'kab', 'kahan', 'kaun', 'koi',
            'mera', 'meri', 'mere', 'tera', 'teri', 'tere', 'apka', 'apki', 'apke',
            'nahi', 'nahin', 'mat', 'karo', 'kariye', 'karna', 'karte',
            'acha', 'achha', 'theek', 'thik', 'bas', 'phir', 'kabhi',
            'yeh', 'woh', 'yahan', 'wahan', 'jab', 'tab',
            'kundli', 'graha', 'rashi', 'nakshatra', 'dasha', 'bhava', 'jyotish'
        ],
        # Tamil
        'ta': [
            'vanakkam', 'wanakkam', 'wadakkam', 'namaskaram', 'epdi', 'eppadi',
            'enna', 'eppo', 'enga', 'yaar', 'yaaru',
            'naan', 'nee', 'neenu', 'avan', 'aval', 'avanga',
            'enakku', 'unakku', 'avanukkku', 'avalukku',
            'vandhu', 'vanthu', 'irukku', 'irukkum', 'irundha',
            'pannanum', 'pannum', 'panna', 'sollu', 'sollanum', 'paaru', 'paarunga',
            'illa', 'illai', 'aama', 'sari', 'nalla', 'romba', 'rasi'
        ],
        # Telugu
        'te': [
            'namaskaram', 'namaskaramulu', 'enti', 'ela', 'elaa', 'eppudu', 'ekkada', 'evaru',
            'nenu', 'neenu', 'meeru', 'vaadu', 'aame', 'vaalla',
            'naaku', 'neeku', 'meeruku', 'vaadiki', 'aameki',
            'cheppu', 'cheppandi', 'choodandi', 'vinu', 'vinandi',
            'chesthe', 'chesthanu', 'cheyandi', 'undhi', 'undi', 'unnaru',
            'kaadu', 'ledhu', 'avunu', 'sare', 'baagundi', 'chaala', 'jathakam'
        ],
        # Marathi
        'mr': [
            'namaskar', 'kay', 'kasa', 'kasaa', 'kuthey', 'kon', 'konacha',
            'mi', 'tu', 'to', 'ti', 'tumhi', 'aamhi',
            'mala', 'tula', 'tyala', 'tila', 'tumhala',
            'sang', 'sanga', 'sangaa', 'kar', 'kara', 'bagh', 'bagha',
            'nahi', 'naahi', 'hoy', 'hoay', 'bara', 'chaan', 'khup', 'patrika'
        ],
        # Malayalam
        'ml': [
            'namaskaram', 'entha', 'enthu', 'engane', 'eppol', 'evide', 'aar', 'aarude',
            'njan', 'njaan', 'nee', 'ningal', 'avan', 'aval', 'avar',
            'enikku', 'ninakku', 'ningalkku', 'avannu', 'avalkkku',
            'parayoo', 'cheyyoo', 'nokku', 'kelkku', 'varoo',
            'illa', 'alle', 'athe', 'sheriyaanu', 'nannaayi', 'valare',
            'sugamano', 'vishesham', 'kore', 'naalu', 'aayi', 'poda', 'podam'
        ],
        # Punjabi
        'pa': [
            'sat', 'sri', 'akal', 'ki', 'kiven', 'kive', 'kado', 'kithe', 'kaun', 'kida',
            'main', 'tu', 'tusi', 'oh', 'ohna', 'assi',
            'menu', 'tenu', 'tussi', 'ohnu', 'ohna',
            'dass', 'dassi', 'karo', 'dekho', 'sun', 'suno',
            'nahi', 'nahin', 'haan', 'theek', 'changa', 'bahut'
        ],
    }

    
    def __init__(self, llm=None):
        """
        Initialize detector with optional LLM for ambiguous cases.
        
        Args:
            llm: LangChain LLM instance for fallback detection
        """
        self.llm = llm
        print("[LANG] Initialized with default language: hi-lat (Hinglish)")
        
    def detect(self, text: str) -> str:
        """
        Detect language and return one of the 8 fixed ISO codes.
        Default: hi-lat (Hinglish)
        
        Args:
            text: Input text to detect language for
            
        Returns:
            Language code from ALLOWED_CODES
        """
        if not text or len(text.strip()) < 2:
            return 'hi-lat'  # Default to Hinglish for empty/very short text

        q_clean = text.lower().strip()
        
        # STEP 1: Greeting Detection (FIXES "hello" → "fi" bug)
        # If it's just a greeting, return Hinglish immediately
        if q_clean in self.ENGLISH_BYPASS:
            print(f"[LANG] Greeting detected: '{text}' → hi-lat (default)")
            return 'hi-lat'
        
        # Check if it's a short phrase with greeting words
        words = set(re.findall(r'\w+', q_clean))
        if len(words) <= 3 and words.intersection(self.ENGLISH_BYPASS):
            print(f"[LANG] Short greeting phrase → hi-lat (default)")
            return 'hi-lat'

        try:
            # STEP 2: Romanization Check (HIGHEST PRIORITY for Indian languages)
            romanized_lang = self._detect_romanization(text)
            if romanized_lang:
                # Map base code to -lat variant
                lat_code = f"{romanized_lang}-lat"
                if lat_code in self.ALLOWED_CODES:
                    print(f"[LANG] Romanization detected: {lat_code}")
                    return lat_code
                
                # Fallback: if -lat variant not in allowed codes
                if romanized_lang in self.ALLOWED_CODES:
                    return romanized_lang
            
            # STEP 3: Library Detection (langdetect)
            lang_code = detect(text)
            normalized = self._normalize_code(lang_code)
            
            # CRITICAL FIX: Only return if it's in our allowed list
            if normalized in self.ALLOWED_CODES:
                print(f"[LANG] Library detected: {normalized}")
                return normalized
            
            # Unsupported language detected (like 'fi', 'fr', 'es', etc.)
            # This fixes the "hello" → "fi" bug
            print(f"[LANG] Unsupported language '{normalized}' detected → defaulting to hi-lat")
            return 'hi-lat'
            
        except LangDetectException:
            print(f"[LANG] Detection failed → defaulting to hi-lat")
            
            # STEP 4: Fallback to LLM (if enabled)
            if self.llm:
                try:
                    detected = self._llm_detect(text)
                    if detected in self.ALLOWED_CODES:
                        print(f"[LANG] LLM detected: {detected}")
                        return detected
                except Exception as e:
                    print(f"[LANG] LLM detection error: {e}")
            
            return 'hi-lat'
    
    def detect_with_confidence(self, text: str) -> Tuple[str, float]:
        """
        Detect language with confidence score.
        
        Args:
            text: Text to detect language for
            
        Returns:
            Tuple of (language_code, confidence_score)
        """
        if not text or len(text.strip()) < 3:
            return ('hi-lat', 0.5)
            
        try:
            # Check romanization first (high confidence)
            romanized_lang = self._detect_romanization(text)
            if romanized_lang:
                return (f"{romanized_lang}-lat", 0.85)
            
            # Get probabilities from library
            langs = detect_langs(text)
            if langs:
                top_lang = langs[0]
                code = self._normalize_code(top_lang.lang)
                confidence = top_lang.prob
                
                # Only return if it's a supported language
                if code in self.ALLOWED_CODES:
                    return (code, confidence)
            
        except LangDetectException:
            pass
        
        # Fallback to Hinglish
        return ('hi-lat', 0.3)
    
    def is_transliterated(self, text: str, lang_code: str) -> bool:
        """
        Check if text is romanized/transliterated version of a language.
        
        Args:
            text: Text to check
            lang_code: Base language code (e.g., 'hi', 'ta')
            
        Returns:
            True if text appears to be romanized
        """
        if lang_code not in self.ROMANIZATION_MARKERS:
            return False
            
        text_lower = text.lower()
        markers = self.ROMANIZATION_MARKERS[lang_code]
        
        # Check if text contains romanization markers
        for marker in markers:
            if re.search(r'\b' + marker + r'\b', text_lower):
                return True
                
        return False
    
    def _detect_romanization(self, text: str) -> Optional[str]:
        """
        Detect if text is romanized version of an Indian language.
        
        Returns:
            Base language code if romanization detected, None otherwise
        """
        # Only check if text is primarily Latin script
        if not re.search(r'[a-zA-Z]', text):
            return None
            
        text_lower = text.lower()
        
        # Count matches for each language
        match_counts: Dict[str, int] = {}
        for lang_code, markers in self.ROMANIZATION_MARKERS.items():
            count = sum(1 for marker in markers 
                       if marker not in self.GLOBAL_EXCLUSION 
                       and re.search(r'\b' + marker + r'\b', text_lower))
            if count > 0:
                match_counts[lang_code] = count
        
        # Return language with most marker matches
        if match_counts:
            best_lang = max(match_counts.items(), key=lambda x: x[1])
            # Require at least 1 marker for detection
            if best_lang[1] >= 1:
                return best_lang[0]
                
        return None
    
    def _normalize_code(self, lang_code: str) -> str:
        """
        Normalize language code to ISO 639-1 standard.
        
        Args:
            lang_code: Raw language code from library
            
        Returns:
            Normalized ISO 639-1 code
        """
        # Just take first 2 characters for standard codes
        normalized = lang_code.lower()
        return normalized[:2] if len(normalized) > 2 and '-' not in normalized else normalized
    
    def _llm_detect(self, text: str) -> str:
        """
        Use LLM for edge cases, restricted to the 8 supported languages.
        
        Args:
            text: Text to detect
            
        Returns:
            Language code from ALLOWED_CODES
        """
        if not self.llm:
            return 'hi-lat'
            
        prompt = f"""Identify the PRIMARY language of the following text.
RESTRICT your answer to one of these codes ONLY: {', '.join(sorted(self.LANGUAGE_NAMES.keys()))}.

IMPORTANT RULES:
- If the text is an Indian language written in ROMAN SCRIPT (English alphabet), use the '-lat' suffix
  Example: Hindi in Roman script = 'hi-lat', Tamil in Roman = 'ta-lat'
- If just a greeting like "hello", "hi", return: hi-lat
- For pure English queries about astrology, return: en
- For Indian language queries in Roman script, return: XX-lat (where XX is the language code)

Text: "{text}"

Respond with ONLY the language code, nothing else:"""
        
        try:
            response = self.llm.invoke(prompt)
            detected = response.content.strip().lower() if hasattr(response, 'content') else str(response).strip().lower()
            # Clean up response (remove quotes, newlines, etc.)
            detected = detected.split()[0].split('\n')[0].replace('"', '').replace("'", "")
            
            # Validate it's in allowed codes
            if detected in self.ALLOWED_CODES:
                return detected
            
            print(f"[LANG] LLM returned unsupported code '{detected}' → defaulting to hi-lat")
            return 'hi-lat'
            
        except Exception as e:
            print(f"[LANG] LLM detection error: {e} → defaulting to hi-lat")
            return 'hi-lat'
    
    def get_language_name(self, lang_code: str) -> str:
        """
        Get human-readable language name from code.
        
        Args:
            lang_code: ISO 639-1 code (e.g., 'en', 'hi-lat')
            
        Returns:
            Language name (e.g., 'English', 'Hinglish')
        """
        return self.LANGUAGE_NAMES.get(lang_code, lang_code.upper())


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

_detector_instance = None


def get_language_detector(llm=None) -> LanguageDetector:
    """
    Get singleton LanguageDetector instance.
    
    Args:
        llm: LLM instance (only used on first call)
        
    Returns:
        LanguageDetector singleton
    """
    global _detector_instance
    if _detector_instance is None:
        _detector_instance = LanguageDetector(llm=llm)
    return _detector_instance


# ============================================================================
# TESTING
# ============================================================================

if __name__ == "__main__":
    """Test the language detector"""
    print("=" * 70)
    print("LANGUAGE DETECTOR TEST")
    print("=" * 70)
    
    detector = LanguageDetector()
    
    test_cases = [
        # Greetings (should return hi-lat, NOT fi or other)
        ("hello", "hi-lat"),
        ("hi", "hi-lat"),
        ("namaste", "hi-lat"),
        ("good morning", "hi-lat"),
        
        # English
        ("What is my birth chart?", "en"),
        ("When will I get married?", "en"),
        
        # Hinglish (Roman Hindi)
        ("Meri shaadi kab hogi?", "hi-lat"),
        ("Mera career kaisa hai?", "hi-lat"),
        ("Kundli dekhiye", "hi-lat"),
        
        # Hindi (Devanagari)
        ("मेरी शादी कब होगी?", "hi"),
        
        # Tamil (Native)
        ("என் திருமணம் எப்போது?", "ta"),
        
        # Tamil (Romanized)
        ("En thirumanam eppodhu?", "ta-lat"),
        
        # Mixed
        ("hello, meri shaadi kab hogi?", "hi-lat")
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
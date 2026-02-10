"""
Universal Language Detection Module

Provides robust language detection using:
1. Fast library-based detection (langdetect) for 50+ languages
2. LLM fallback for ambiguous cases (code-switching, transliteration)
3. Romanization detection (Hinglish, Tanglish, etc.)

This replaces the manual heuristic system with a scalable approach.
"""

import re
from typing import Optional, Tuple, Dict
from langdetect import detect, detect_langs, LangDetectException


class LanguageDetector:
    """
    Production-grade language detector with library + LLM hybrid approach.
    """
    
    # ISO 639-1 to full language name mapping
    LANGUAGE_NAMES = {
        'en': 'English',
        # Major Indian Languages (22 Scheduled Languages)
        'hi': 'Hindi',
        'bn': 'Bengali',
        'te': 'Telugu',
        'mr': 'Marathi',
        'ta': 'Tamil',
        'ur': 'Urdu',
        'gu': 'Gujarati',
        'kn': 'Kannada',
        'ml': 'Malayalam',
        'or': 'Odia',
        'pa': 'Punjabi',
        'as': 'Assamese',
        'mai': 'Maithili',
        'sa': 'Sanskrit',
        'ks': 'Kashmiri',
        'ne': 'Nepali',
        'sd': 'Sindhi',
        'kok': 'Konkani',
        'mni': 'Manipuri',
        'doi': 'Dogri',
        'sat': 'Santali',
        'bo': 'Bodo',
        # Other major languages
        'es': 'Spanish',
        'fr': 'French',
        'de': 'German',
        'it': 'Italian',
        'pt': 'Portuguese',
        'ru': 'Russian',
        'ar': 'Arabic',
        'zh-cn': 'Chinese (Simplified)',
        'zh-tw': 'Chinese (Traditional)',
        'ja': 'Japanese',
        'ko': 'Korean',
        'vi': 'Vietnamese',
        'th': 'Thai',
        'id': 'Indonesian',
        'ms': 'Malay',
        'tr': 'Turkish',
        'nl': 'Dutch',
        'pl': 'Polish',
        'sv': 'Swedish',
        'no': 'Norwegian',
        'da': 'Danish',
        'fi': 'Finnish',
        'el': 'Greek',
        'he': 'Hebrew',
        'fa': 'Persian',
    }
    
    # Romanization markers for Indian languages
    # These are common words/particles that indicate romanized Indian language text
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
        # Bengali
        'bn': [
            'nomoshkar', 'namaskar', 'ki', 'kemon', 'kemone', 'kothay', 'ke', 'kara',
            'ami', 'tumi', 'apni', 'se', 'tara', 'ora',
            'amar', 'tomar', 'apnar', 'tar', 'oder',
            'bolo', 'bolun', 'dekho', 'dekhun', 'shuno', 'shunun',
            'koro', 'korun', 'ache', 'achhe', 'chhilo', 'hobe',
            'na', 'naa', 'haan', 'thik', 'bhalo', 'khub', 'kushthi'
        ],
        # Gujarati
        'gu': [
            'namaste', 'kem', 'cho', 'shu', 'kevi', 'kyare', 'kyan', 'kon', 'kona',
            'hun', 'tu', 'tame', 'te', 'teo', 'ame',
            'mane', 'tane', 'tamne', 'tene', 'amne',
            'kaho', 'karo', 'juo', 'jovo', 'sambhalo',
            'nathi', 'na', 'haa', 'thik', 'saras', 'khub'
        ],
        # Kannada
        'kn': [
            'namaskara', 'yenu', 'hege', 'yaavaga', 'elli', 'yaaru', 'yavanu',
            'naanu', 'ninu', 'nivu', 'avanu', 'avalu', 'avaru',
            'nanage', 'ninage', 'nivige', 'avanige', 'avalige',
            'heli', 'helri', 'nodi', 'keli', 'kelri', 'maadi', 'maadri',
            'illa', 'howdu', 'sari', 'chennagi', 'thumba'
        ],
        # Malayalam
        'ml': [
            'namaskaram', 'enthu', 'engane', 'eppol', 'evide', 'aar', 'aarude',
            'njan', 'njaan', 'nee', 'ningal', 'avan', 'aval', 'avar',
            'enikku', 'ninakku', 'ningalkku', 'avannu', 'avalkkku',
            'parayoo', 'cheyyoo', 'nokku', 'kelkku', 'varoo',
            'illa', 'alle', 'athe', 'sheriyaanu', 'nannaayi', 'valare'
        ],
        # Punjabi
        'pa': [
            'sat', 'sri', 'akal', 'ki', 'kiven', 'kive', 'kado', 'kithe', 'kaun', 'kida',
            'main', 'tu', 'tusi', 'oh', 'ohna', 'assi',
            'menu', 'tenu', 'tussi', 'ohnu', 'ohna',
            'dass', 'dassi', 'karo', 'dekho', 'sun', 'suno',
            'nahi', 'nahin', 'haan', 'theek', 'changa', 'bahut'
        ],
        # Urdu (shares many markers with Hindi but has some distinct ones)
        'ur': [
            'kya', 'kaise', 'kab', 'kahan', 'kaun',
            'main', 'tum', 'aap', 'woh', 'yeh',
            'mera', 'tumhara', 'aapka', 'uska',
            'bataiye', 'dekhiye', 'suniye', 'kijiye',
            'nahin', 'haan', 'bilkul', 'theek', 'bahut', 'bohot'
        ],
    }

    
    def __init__(self, llm=None):
        """
        Initialize detector with optional LLM for ambiguous cases.
        
        Args:
            llm: LangChain LLM instance for fallback detection
        """
        self.llm = llm
        
    def detect(self, text: str) -> str:
        """
        Detect language and return ISO 639-1 code.
        
        Args:
            text: Text to detect language for
            
        Returns:
            ISO 639-1 language code (e.g., 'en', 'hi', 'es')
            Returns 'en' as safe default on failure
        """
        if not text or len(text.strip()) < 3:
            return 'en'
            
        try:
            # CRITICAL: Check romanization FIRST before library
            # Library may misdetect romanized text as other Latin-script languages
            romanized_lang = self._detect_romanization(text)
            if romanized_lang:
                return f"{romanized_lang}-lat"
            
            # Step 2: Use library-based detection
            lang_code = detect(text)
            return self._normalize_code(lang_code)
            
        except LangDetectException:
            # Step 3: Fallback to LLM for ambiguous cases
            if self.llm:
                print("[LANG_DETECTOR] Library detection failed, using LLM fallback...")
                return self._llm_detect(text)
            
            # Final fallback
            print("[LANG_DETECTOR] [WARN] Detection failed, defaulting to 'en'")
            return 'en'
    
    def detect_with_confidence(self, text: str) -> Tuple[str, float]:
        """
        Detect language with confidence score.
        
        Args:
            text: Text to detect language for
            
        Returns:
            Tuple of (language_code, confidence_score)
        """
        if not text or len(text.strip()) < 3:
            return ('en', 0.5)
            
        try:
            # Check romanization first
            romanized_lang = self._detect_romanization(text)
            if romanized_lang:
                return (f"{romanized_lang}-lat", 0.85)  # High confidence for marker-based
            
            # Get probabilities from library
            langs = detect_langs(text)
            if langs:
                top_lang = langs[0]
                code = self._normalize_code(top_lang.lang)
                confidence = top_lang.prob
                return (code, confidence)
            
        except LangDetectException:
            pass
        
        # Fallback
        return ('en', 0.3)
    
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
        Detect if text is romanized version of a language.
        
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
                       if re.search(r'\b' + marker + r'\b', text_lower))
            if count > 0:
                match_counts[lang_code] = count
        
        # Return language with most marker matches (need at least 1 marker for short phrases)
        if match_counts:
            best_lang = max(match_counts.items(), key=lambda x: x[1])
            if best_lang[1] >= 1:  # Lowered from 2 to 1 for better short-phrase detection
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
        # Handle common variations
        code_map = {
            'zh-cn': 'zh-cn',
            'zh-tw': 'zh-tw',
            'zh': 'zh-cn',  # Default to simplified
        }
        
        normalized = code_map.get(lang_code.lower(), lang_code.lower())
        return normalized[:2] if len(normalized) > 2 and '-' not in normalized else normalized
    
    def _llm_detect(self, text: str) -> str:
        """
        Use LLM for edge cases like code-switching and ambiguous text.
        
        Args:
            text: Text to detect
            
        Returns:
            ISO 639-1 language code
        """
        if not self.llm:
            return 'en'
            
        prompt = f"""Identify the PRIMARY language of the following text.
If the text mixes languages (e.g., Hinglish), identify the DOMINANT language.

Return ONLY the ISO 639-1 code (2-letter code like 'en', 'hi', 'ta', 'es', 'fr', etc.).
If the text uses Roman script for a non-Latin language (e.g., "Namaste kaise ho"), 
append '-lat' (e.g., 'hi-lat').

Text: "{text}"

Language code:"""
        
        try:
            response = self.llm.invoke(prompt)
            detected = response.content.strip().lower() if hasattr(response, 'content') else str(response).strip().lower()
            
            # Clean up response (sometimes LLM adds explanation)
            detected = detected.split()[0].split('\n')[0]
            
            # Validate it's a reasonable code
            if len(detected) >= 2 and len(detected) <= 6:
                return detected
                
        except Exception as e:
            print(f"[LANG_DETECTOR] LLM detection error: {e}")
            
        return 'en'
    
    def get_language_name(self, lang_code: str) -> str:
        """
        Get human-readable language name from code.
        
        Args:
            lang_code: ISO 639-1 code (e.g., 'en', 'hi-lat')
            
        Returns:
            Language name (e.g., 'English', 'Hindi (Romanized)')
        """
        # Handle romanized variants
        if '-lat' in lang_code:
            base_code = lang_code.replace('-lat', '')
            base_name = self.LANGUAGE_NAMES.get(base_code, base_code.upper())
            return f"{base_name} (Romanized)"
            
        return self.LANGUAGE_NAMES.get(lang_code, lang_code.upper())


# Singleton for convenience
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

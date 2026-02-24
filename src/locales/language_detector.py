# src/locales/language_detector.py
"""
Language Detection Module — 4-Stage Deterministic-First Pipeline

Supports 13 language codes:
  Native script : en, hi, ta, te, ml, mr, pa
  Romanized     : hi-lat, ta-lat, te-lat, ml-lat, mr-lat, pa-lat

Detection order (most deterministic first):
  Stage 1 — Unicode block analysis     (native script, ~0% error)
  Stage 2 — Romanized marker scoring   (expanded weighted lists)
  Stage 3 — langdetect library         (pure-Latin fallback)
  Stage 4 — LLM confirmation           (genuinely ambiguous edge cases)

Default language: English (en)
"""

import re
import unicodedata
from typing import Optional, Tuple, Dict, List
from langdetect import detect, detect_langs, LangDetectException


# ---------------------------------------------------------------------------
# Unicode block character-range helpers
# ---------------------------------------------------------------------------

def _count_in_range(text: str, lo: int, hi: int) -> int:
    """Count characters in text whose Unicode codepoint is in [lo, hi]."""
    return sum(1 for ch in text if lo <= ord(ch) <= hi)


# Unicode block ranges for Indian scripts
_UNICODE_BLOCKS: List[Tuple[str, int, int]] = [
    # (base_language_code, lo, hi)
    ("hi",  0x0900, 0x097F),   # Devanagari  → Hindi / Marathi
    ("ta",  0x0B80, 0x0BFF),   # Tamil
    ("te",  0x0C00, 0x0C7F),   # Telugu
    ("ml",  0x0D00, 0x0D7F),   # Malayalam
    ("pa",  0x0A00, 0x0A7F),   # Gurmukhi   → Punjabi
    ("mr",  0x0900, 0x097F),   # Marathi shares Devanagari — disambiguated below
]

# Marathi-specific words (Devanagari script) to disambiguate from Hindi
_MARATHI_NATIVE_MARKERS = {
    "माझ", "मला", "तुम्ही", "आहे", "जाऊ", "करा", "येतो", "घर",
    "आई", "बाबा", "मुलगा", "मुलगी", "कधी", "लग्न", "पत्रिका",
}


class LanguageDetector:
    """
    Multi-stage language detector for NakshatraAI.

    Stage 1 — Unicode block analysis  (native-script, deterministic)
    Stage 2 — Romanized marker scoring (weighted, expanded lists)
    Stage 3 — langdetect library      (pure-Latin fallback)
    Stage 4 — LLM confirmation        (edge cases only)
    """

    # ------------------------------------------------------------------
    # Supported language map
    # ------------------------------------------------------------------
    LANGUAGE_NAMES: Dict[str, str] = {
        "en":     "English",
        "hi":     "Hindi",
        "mr":     "Marathi",
        "pa":     "Punjabi",
        "ta":     "Tamil",
        "te":     "Telugu",
        "ml":     "Malayalam",
        "hi-lat": "Hinglish",
        "mr-lat": "Marathi (Romanized)",
        "pa-lat": "Punjabi (Romanized)",
        "ta-lat": "Tanglish",
        "te-lat": "Telugu (Romanized)",
        "ml-lat": "Malayalam (Romanized)",
    }

    ALLOWED_CODES = set(LANGUAGE_NAMES.keys())

    # ------------------------------------------------------------------
    # English indicators
    # ------------------------------------------------------------------
    # Pure English greetings — map directly to 'en' (unless Indian marker found)
    ENGLISH_GREETINGS = {
        "hello", "hey", "good morning", "good afternoon", "good evening",
        "thanks", "thank you", "please", "goodbye", "bye",
    }

    # Strong English-only content words (NOT shared with Indian romanized)
    ENGLISH_STRONG = {
        "what", "when", "where", "why", "how", "will", "would", "could",
        "should", "about", "because", "although", "therefore", "however",
        "planet", "birth", "chart", "marriage", "career", "money", "health",
        "children", "house", "sign", "ascendant", "transit", "horoscope",
        "prediction", "forecast", "moon", "sun", "jupiter", "saturn", "mars",
        "venus", "mercury", "rahu", "ketu",
        # Functional English words that rarely appear in transliterated Indian text
        "the", "are", "was", "were", "been", "being", "have", "has", "had",
        "does", "did", "get", "got", "make", "made", "take", "think",
        "know", "tell", "show", "give", "need",
    }

    # ------------------------------------------------------------------
    # Romanized (Latin-script) Indian language markers — weighted
    # Weight 3 = highly distinctive (very unlikely in other languages)
    # Weight 1 = common — require score ≥ 3 so single matches don't win
    # ------------------------------------------------------------------
    ROMANIZED_MARKERS: Dict[str, Dict[str, int]] = {
        "hi": {
            # Weight-3 distinctive
            "namaste": 3, "namaskar": 3, "kundli": 3, "jyotish": 3,
            "nakshatra": 3, "graha": 3, "rashi": 3, "lagna": 3,
            "dasha": 3, "antardasha": 3, "mahadasha": 3,
            "bhagya": 3, "karma": 3, "mangal": 3, "shani": 3,
            "guru": 3, "shukra": 3, "budh": 3, "ketu": 3, "rahu": 3,
            # Weight-2 common Hindi
            "kaise": 2, "kyun": 2, "kahan": 2, "kaun": 2, "kab": 2,
            "mera": 2, "meri": 2, "mere": 2, "tera": 2, "teri": 2,
            "apka": 2, "apki": 2, "aapka": 2, "aapki": 2,
            "yeh": 2, "woh": 2, "yahan": 2, "wahan": 2,
            "acha": 2, "theek": 2, "phir": 2, "bas": 2,
            "hoga": 2, "hogi": 2, "kaisa": 2, "batao": 2, "bataye": 2,
            "chahiye": 2, "milega": 2, "milegi": 2,
            # Weight-1 (need cumulative ≥ 3)
            "kya": 1, "hai": 1, "hoon": 1, "hain": 1, "tha": 1, "thi": 1,
            "nahi": 1, "nahin": 1, "aur": 1, "par": 1, "se": 1,
            "ko": 1, "ka": 1, "ki": 1, "ke": 1, "mein": 1,
        },
        "ta": {
            "vanakkam": 3, "epdi": 3, "eppadi": 3, "enna": 3, "eppo": 3,
            "thirumanam": 3, "jathagam": 3, "rasi": 3,
            "naan": 2, "enakku": 2, "unakku": 2, "pannanum": 2,
            "irukku": 2, "sollungal": 2, "romba": 2,
            "nee": 1, "avan": 1, "aval": 1, "illa": 1, "illai": 1,
            "aama": 1, "paakalam": 1, "thevai": 1,
            "eppodhu": 2, "ethu": 2, "yaar": 2, "evvalavu": 2,
        },
        "te": {
            "namaskaram": 3, "ela": 3, "eppudu": 3, "ekkada": 3, "evaru": 3,
            "jathakam": 3, "vivaaham": 3, "udyogam": 3,
            "nenu": 2, "meeru": 2, "naaku": 2, "neeku": 2,
            "cheppu": 2, "undhi": 2, "avunu": 2, "chaala": 2,
            "kadhu": 2, "ledu": 2, "chesaru": 2, "velutundi": 2,
            "vaadu": 1, "aame": 1, "okadu": 1, "okati": 1,
        },
        "mr": {
            "namaskar": 3, "majha": 3, "maza": 3, "mala": 3, "tumhi": 3,
            "aahe": 3, "ahe": 3, "patrika": 3, "lagn": 3, "lagna": 2,
            "nakshatra": 2, "zale": 3, "aahet": 3, "naste": 3,
            "kay": 2, "kasa": 2, "con": 2, "kuthun": 2, "kadhi": 3,
            "mi": 2, "amhi": 2, "tyala": 3, "tila": 3,
            "hoy": 2, "bara": 2, "khup": 3, "jar": 1,
            "sang": 2, "jato": 2, "yeto": 3, "jait": 2,
        },
        "ml": {
            "namaskaram": 3, "engane": 3, "eppol": 3, "evide": 3,
            "vivaham": 3, "jathakam": 3, "rasiyil": 3,
            "njan": 3, "ningal": 3, "enikku": 3, "ninakku": 3,
            "ente": 3, "vivaaham": 3, "parayoo": 3, "parayan": 3,
            "valare": 2, "undoo": 2, "illaa": 2, "annu": 2,
            "aanu": 2, "athinu": 2, "entha": 2, "enthu": 2,
            "eppozhanu": 3, "kurichu": 2, "cheyyanam": 2,
            "nee": 1, "avan": 1, "aval": 1, "illa": 1,
        },
        "pa": {
            "waheguru": 3, "punjabi": 3, "gurmukhi": 3,
            "tusi": 3, "kiven": 3, "kithe": 3, "kado": 3,
            "kaddon": 3, "vivaah": 3, "vivah": 3, "rishta": 2,
            "main": 2, "menu": 2, "tenu": 2, "dass": 2,
            "haan": 2, "changa": 2, "bahut": 2, "ohna": 2,
            "akkal": 2, "gal": 2, "puchho": 2, "thoda": 2,
            "langar": 3, "ardas": 3, "grihast": 2, "dasam": 3,
            "nahi": 1, "hon": 1, "oh": 1,
        },
    }

    # Words to exclude from marker matching (too ambiguous / English overlap)
    GLOBAL_EXCLUSION = {
        "to", "is", "me", "do", "we", "us", "an", "at", "by",
        "he", "so", "it", "or", "as", "no", "on", "in", "if",
        "oh", "ko", "ka", "ki", "ke",
    }

    # langdetect codes that are commonly wrong for our target languages
    LANGDETECT_REMAP = {
        "id": "en",   # Indonesian often returned for short English
        "no": "en",   # Norwegian false positive
        "da": "en",   # Danish false positive
        "sv": "en",   # Swedish false positive
        "nl": "en",   # Dutch false positive
        "af": "en",   # Afrikaans false positive
        "cy": "en",   # Welsh false positive
        "tl": "en",   # Filipino/Tagalog false positive for Hinglish
        "so": "en",   # Somali false positive
    }

    # ------------------------------------------------------------------
    def __init__(self, llm=None, default_language: str = "en"):
        self.llm = llm
        self.default_language = default_language
        print(f"[LANG] Detector ready — default: {self.LANGUAGE_NAMES.get(default_language, default_language)}")

    # ==================================================================
    # PUBLIC API
    # ==================================================================

    def detect(self, text: str) -> str:
        """Detect language code. Returns one of the 13 ALLOWED_CODES."""
        code, _ = self.detect_with_confidence(text)
        return code

    def detect_with_confidence(self, text: str) -> Tuple[str, float]:
        """
        Detect language with confidence score.

        Returns:
            (language_code, confidence)  where confidence ∈ [0.0, 1.0]
        """
        if not text or len(text.strip()) < 2:
            return (self.default_language, 0.5)

        text_stripped = text.strip()

        # ── STAGE 1: Unicode block analysis ──────────────────────────────────
        result = self._stage1_unicode(text_stripped)
        if result:
            return result

        # ── STAGE 2: Romanized marker scoring ────────────────────────────────
        result = self._stage2_romanized(text_stripped)
        if result:
            return result

        # ── English detection (after Indian romanized to prevent misfires) ────
        result = self._check_english(text_stripped)
        if result:
            return result

        # ── STAGE 3: langdetect library ──────────────────────────────────────
        result = self._stage3_langdetect(text_stripped)
        if result:
            return result

        # ── STAGE 4: LLM fallback ────────────────────────────────────────────
        if self.llm:
            result = self._stage4_llm(text_stripped)
            if result:
                return result

        return (self.default_language, 0.3)

    def get_language_name(self, lang_code: str) -> str:
        """Get human-readable language name."""
        return self.LANGUAGE_NAMES.get(lang_code, lang_code.upper())

    # ==================================================================
    # PRIVATE — Stage implementations
    # ==================================================================

    def _stage1_unicode(self, text: str) -> Optional[Tuple[str, float]]:
        """
        Stage 1: Unicode block analysis.
        Counts characters in Indian script Unicode ranges.
        Returns result if ≥ 15% of non-whitespace chars are in a block.
        """
        clean = re.sub(r"\s+", "", text)
        total = len(clean)
        if total == 0:
            return None

        # Count per block (skip 'mr' entry — shared with 'hi')
        blocks_to_check = [
            ("hi", 0x0900, 0x097F),
            ("ta", 0x0B80, 0x0BFF),
            ("te", 0x0C00, 0x0C7F),
            ("ml", 0x0D00, 0x0D7F),
            ("pa", 0x0A00, 0x0A7F),
        ]

        scores: Dict[str, float] = {}
        for code, lo, hi in blocks_to_check:
            count = _count_in_range(text, lo, hi)
            ratio = count / total
            if ratio > 0:
                scores[code] = ratio

        if not scores:
            return None

        best_code, best_ratio = max(scores.items(), key=lambda x: x[1])

        if best_ratio >= 0.15:
            # Devanagari is shared by Hindi and Marathi — disambiguate
            if best_code == "hi":
                best_code = self._disambiguate_devanagari(text)
            return (best_code, min(0.99, 0.85 + best_ratio * 0.15))

        return None

    def _disambiguate_devanagari(self, text: str) -> str:
        """Disambiguate Hindi vs Marathi for Devanagari text."""
        for marker in _MARATHI_NATIVE_MARKERS:
            if marker in text:
                return "mr"
        return "hi"

    def _stage2_romanized(self, text: str) -> Optional[Tuple[str, float]]:
        """
        Stage 2: Romanized marker scoring.
        Uses weighted word lists. Threshold: cumulative score ≥ 3.
        Returns (-lat) code for the winning language if threshold met.
        """
        # Only applies to Latin-script text
        if not re.search(r"[a-zA-Z]", text):
            return None

        text_lower = text.lower()
        lang_scores: Dict[str, int] = {}

        for lang_code, markers in self.ROMANIZED_MARKERS.items():
            score = 0
            for word, weight in markers.items():
                if word in self.GLOBAL_EXCLUSION:
                    continue
                # Whole-word match
                if re.search(r"\b" + re.escape(word) + r"\b", text_lower):
                    score += weight
            if score > 0:
                lang_scores[lang_code] = score

        if not lang_scores:
            return None

        best_lang, best_score = max(lang_scores.items(), key=lambda x: x[1])

        if best_score >= 3:
            lat_code = f"{best_lang}-lat"
            # Normalise confidence: score 3→0.75, score 6→0.9, score 10→0.95
            confidence = min(0.97, 0.70 + best_score * 0.025)
            return (lat_code, confidence)

        return None

    def _check_english(self, text: str) -> Optional[Tuple[str, float]]:
        """
        Check for English AFTER Indian romanized detection to prevent:
        'mera career kaisa hai' → en  (should be hi-lat)
        """
        text_lower = text.lower().strip()
        words = set(re.findall(r"\b[a-z]+\b", text_lower))

        # Single-word English greetings
        if text_lower in self.ENGLISH_GREETINGS or words <= {"hi", "hello", "hey"}:
            return ("en", 0.95)

        # English greeting phrase (no Indian markers in sentence)
        for greeting in self.ENGLISH_GREETINGS:
            if greeting in text_lower:
                # Make sure no Indian marker overrules this
                any_indian = any(
                    re.search(r"\b" + re.escape(w) + r"\b", text_lower)
                    for lang_markers in self.ROMANIZED_MARKERS.values()
                    for w, weight in lang_markers.items()
                    if weight >= 2 and w not in self.GLOBAL_EXCLUSION
                )
                if not any_indian:
                    return ("en", 0.90)

        # English keyword density with a higher bar (60%) to prevent misfires
        if words:
            strong_count = sum(1 for w in words if w in self.ENGLISH_STRONG)
            ratio = strong_count / len(words)
            if ratio >= 0.55:
                return ("en", 0.70 + ratio * 0.25)

        return None

    def _stage3_langdetect(self, text: str) -> Optional[Tuple[str, float]]:
        """
        Stage 3: langdetect library.
        Applied only to Latin-script text not resolved above.
        Common false positives are remapped to 'en'.
        """
        try:
            langs = detect_langs(text)
            if not langs:
                return None

            top = langs[0]
            raw_code = top.lang.lower()
            confidence = float(top.prob)

            # Remap common false positives
            remapped = self.LANGDETECT_REMAP.get(raw_code, raw_code)

            # Normalise to 2-char code (strip sub-region suffixes)
            base = remapped[:2] if len(remapped) > 2 and "-" not in remapped else remapped

            if base in self.ALLOWED_CODES and confidence >= 0.4:
                return (base, confidence)

        except LangDetectException:
            pass

        return None

    def _stage4_llm(self, text: str) -> Optional[Tuple[str, float]]:
        """
        Stage 4: LLM confirmation for genuinely ambiguous edge cases.
        Only called when all deterministic stages fail.
        """
        if not self.llm:
            return None

        codes_str = ", ".join(sorted(self.ALLOWED_CODES))
        prompt = f"""Identify the PRIMARY language of the following text.

ALLOWED CODES: {codes_str}

Rules:
- If the text is in an Indian language written in ROMAN SCRIPT (transliterated), append '-lat' (e.g., 'hi-lat', 'ta-lat').
- If the text is in an Indian language written in NATIVE SCRIPT, use the bare code (e.g., 'hi', 'ta').
- If the language is not in the allowed list, return 'en'.
- Return ONLY the language code — no explanation.

Text: "{text}"

Language code:"""

        try:
            response = self.llm.invoke(prompt)
            raw = response.content.strip().lower() if hasattr(response, "content") else str(response).strip().lower()
            # Extract first token, strip punctuation
            detected = raw.split()[0].split("\n")[0].strip("\"'.,()")
            if detected in self.ALLOWED_CODES:
                return (detected, 0.70)
        except Exception:
            pass

        return None


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_detector_instance: Optional[LanguageDetector] = None


def get_language_detector(llm=None, default_language: str = "en") -> LanguageDetector:
    """
    Get the singleton LanguageDetector.
    If llm is passed and the instance already exists, the LLM reference is updated.
    """
    global _detector_instance
    if _detector_instance is None:
        _detector_instance = LanguageDetector(llm=llm, default_language=default_language)
    elif llm is not None:
        # Update LLM reference so Stage 4 always has the latest model
        _detector_instance.llm = llm
    return _detector_instance


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 72)
    print("LANGUAGE DETECTOR — 4-STAGE PIPELINE TEST")
    print("=" * 72)

    detector = LanguageDetector(default_language="en")

    test_cases = [
        # Native scripts
        ("मेरी शादी कब होगी?",          "hi",     "Devanagari Hindi"),
        ("माझे लग्न कधी होईल?",          "mr",     "Devanagari Marathi"),
        ("என் திருமணம் எப்போது?",         "ta",     "Tamil native"),
        ("నా వివాహం ఎప్పుడు?",           "te",     "Telugu native"),
        ("എന്റെ വിവാഹം എന്ന്?",           "ml",     "Malayalam native"),
        ("ਮੇਰਾ ਵਿਆਹ ਕਦੋਂ ਹੋਵੇਗਾ?",       "pa",     "Gurmukhi Punjabi"),
        # Romanized
        ("Meri shaadi kab hogi?",        "hi-lat", "Hinglish classic"),
        ("Mera career kaisa hai?",       "hi-lat", "Hinglish mixed EN"),
        ("my kundli batao",              "hi-lat", "Hinglish mixed EN 2"),
        ("kundli dekhiye",               "hi-lat", "Hinglish short"),
        ("En thirumanam eppodhu?",       "ta-lat", "Tanglish"),
        ("Naa vivaaham eppudu?",         "te-lat", "Telugu romanized"),
        ("Ente vivaaham eppo?",          "ml-lat", "Malayalam romanized"),
        ("Maza lagna kadhi?",            "mr-lat", "Marathi romanized"),
        ("Mera vivaah kaddon?",          "pa-lat", "Punjabi romanized"),
        # English — must not misfire
        ("When will I get married?",     "en",     "Pure English"),
        ("What is my birth chart?",      "en",     "Pure English 2"),
        ("hello",                        "en",     "English greeting"),
        ("hi",                           "en",     "English single word"),
        ("Tell me about my moon sign",   "en",     "English astrology"),
        ("How is my career in 2026?",    "en",     "English career"),
        # Edge cases
        ("mera naam kya hai",            "hi-lat", "Hinglish name query"),
        ("meri DOB kya hai",             "hi-lat", "Hinglish DOB query"),
        ("namaste, mera lagna kya hai",  "hi-lat", "Hinglish with greeting"),
        ("vanakkam, en rasi enna?",      "ta-lat", "Tanglish with greeting"),
    ]

    passed = 0
    failed = 0
    print(f"\n{'Text':<42} {'Expected':<10} {'Got':<10} {'Conf':>5}  Status  Note")
    print("-" * 90)
    for text, expected, note in test_cases:
        got, conf = detector.detect_with_confidence(text)
        ok = got == expected
        if ok:
            passed += 1
        else:
            failed += 1
        icon = "PASS" if ok else "FAIL"
        print(f"{icon} {text[:40]:<40} {expected:<10} {got:<10} {conf:>5.2f}  {note}")

    print("-" * 90)
    print(f"\n{passed}/{passed+failed} passed   ({100*passed/(passed+failed):.0f}%)")
    print("=" * 72)
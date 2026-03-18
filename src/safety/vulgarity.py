"""
Shared vulgarity detection helpers.

This module centralizes:
- fast keyword-based vulgarity detection
- astrological safe-word detection (for LLM-check skip)
- LLM fallback vulgarity check prompt + fail-open behavior

Used by both API pre-gate and safety classifier to avoid logic drift.
"""

from typing import Optional


# Fast keyword gate for explicit vulgar / abusive / sexual content.
VULGAR_KEYWORDS = {
    # English
    "fuck", "shit", "bitch", "asshole", "bastard", "motherfucker",
    "dick", "pussy", "cock", "cunt", "whore", "slut", "nude", "porn",
    "pornography", "masturbat", "sex position", "sexual position",
    # Hindi / Hinglish (transliterated)
    "chutiya", "madarchod", "bhosdike", "bhosdika", "randi", "harami",
    "gaandu", "gandu", "lund", "chut", "bhenchod", "behenchod",
    "maderchod", "saala", "kamina", "kutte", "kamine", "haramzada",
    "haramkhor", "madarjaat", "lavde", "lavda",
    # Tamil (transliterated)
    "punda", "pundai", "sunni", "thevidiya", "ootha", "koothi",
    "baadu", "paiyan", "oombu",
    # Telugu (transliterated)
    "dengey", "dengudi", "pukku", "modda", "lanja", "lanjakodaka",
    "pooku", "gudda",
    # Marathi (transliterated)
    "zavnya", "zavad", "bhadva", "aai zavadya", "ghanta", "zadya",
    # Punjabi (transliterated)
    "bhen di", "teri maa", "phudu", "phuddu", "maa di",
    # Malayalam (transliterated)
    "theetta", "myre", "kunna", "pooru", "poori", "ammaye",
    # Urdu (transliterated)
    "haraamzada", "gaand", "khanki", "madar", "sala kutta",
    # Native scripts (high-frequency)
    "चुतिया", "मादरचोद", "भड़वा", "रंडी", "हरामी", "लंड", "भोसड़ी",
    "புண்டை", "சுன்னி", "தேவிடியா",
    "పుక్కు", "మొద్ద", "లంజ",
    "झवाड", "भडवा", "लवडा",
    "ਭੈਣ ਦੀ", "ਫੁੱਡੂ",
    "കുണ്ണ", "പൂറ്",
}


# Astrological terms used to skip costly vulgarity LLM fallback
# for clearly on-topic astrology messages.
ASTRO_SAFE_WORDS = frozenset({
    "kundli", "kundali", "horoscope", "rashi", "lagna", "nakshatra", "dasha",
    "antardasha", "mahadasha", "graha", "planet", "saturn", "jupiter", "venus",
    "mars", "mercury", "moon", "sun", "rahu", "ketu", "shani", "mangal",
    "budh", "brihaspati", "shukra", "surya", "chandra", "transit", "gochar",
    "chart", "birth chart", "vedic", "jyotish", "yoga", "bhava", "house",
    "marriage", "shaadi", "career", "naukri", "health", "money", "dhan",
    "foreign", "videsh", "child", "bachha", "santan", "property", "ghar",
})


def contains_vulgar_keyword(text: str) -> bool:
    """Return True when text contains explicit vulgarity keywords."""
    q = (text or "").lower()
    return any(kw in q for kw in VULGAR_KEYWORDS)


def is_clearly_astrological_query(text: str) -> bool:
    """
    Return True if query clearly contains astrology-safe words.

    This is intentionally simple and fast because it runs on hot path.
    """
    words = set((text or "").lower().split())
    return bool(words & ASTRO_SAFE_WORDS)


def llm_vulgarity_check(query: str, llm, strict_prompt: bool = False) -> bool:
    """
    LLM fallback check for vulgarity missed by keyword scan.

    Returns True if vulgar/abusive/explicit.
    Fails open (False) on any exception to avoid blocking on infra errors.
    """
    if llm is None:
        return False

    if strict_prompt:
        prompt = (
            "You are a content moderator for a professional astrology chatbot. "
            "Does the following message contain profanity, sexual explicitness, "
            "verbal abuse, sexual harassment, or vulgar insults in ANY language "
            "(including abbreviations like 'bc', 'mc', 'lc', creative spellings, "
            "or mixed-language abuse)?\n\n"
            f'Message: "{query}"\n\n'
            "Reply with exactly one word: YES or NO."
        )
    else:
        prompt = (
            "You are a content moderator for a professional astrology chatbot. "
            "Decide ONLY whether the user message below contains: profanity, sexual explicitness, "
            "verbal abuse, sexual harassment, or vulgar insults — in ANY language "
            "(English, Hindi, Tamil, Telugu, Marathi, Punjabi, Malayalam, Urdu, Hinglish, or any mix).\n\n"
            f'User message: "{query}"\n\n'
            "Reply with exactly one word: YES (if vulgar/abusive/explicit) or NO (if not)."
        )

    try:
        response = llm.invoke(prompt)
        answer = (response.content if hasattr(response, "content") else str(response)).strip().upper()
        return answer.startswith("YES")
    except Exception:
        return False

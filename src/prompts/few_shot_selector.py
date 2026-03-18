"""
Few-shot example selector for synthesis prompts.

Loads data/golden_scenarios.yaml at startup and picks the 2 most relevant
golden examples based on domain, language, and response mode.

Usage:
    from src.prompts.few_shot_selector import get_few_shot_block

    block = get_few_shot_block(
        query="meri shaadi kab hogi?",
        language_code="hi-lat",
        domain="marriage",
        response_mode="initial",
    )
    # Inject `block` just before the user query in the synthesis prompt.
"""

from __future__ import annotations

import re
import logging
from pathlib import Path
from typing import Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_SCENARIOS_PATH = (
    Path(__file__).parent.parent.parent / "data" / "golden_scenarios.yaml"
)

# ---------------------------------------------------------------------------
# Module-level cache (loaded once)
# ---------------------------------------------------------------------------

_scenarios: Optional[List[Dict]] = None


def _load_scenarios() -> List[Dict]:
    global _scenarios
    if _scenarios is not None:
        return _scenarios
    try:
        with open(_SCENARIOS_PATH, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        _scenarios = [s for s in data.get("scenarios", []) if s.get("chart_context")]
        logger.info(f"[FewShot] Loaded {len(_scenarios)} golden scenarios from {_SCENARIOS_PATH}")
    except Exception as exc:
        logger.warning(f"[FewShot] Could not load golden scenarios: {exc}")
        _scenarios = []
    return _scenarios


# ---------------------------------------------------------------------------
# Domain keyword mapping
# ---------------------------------------------------------------------------

_DOMAIN_KEYWORDS: Dict[str, List[str]] = {
    "career": [
        "career", "job", "naukri", "profession", "work", "promotion",
        "growth", "employment", "office", "business", "salary", "kaam",
    ],
    "marriage": [
        "marriage", "shaadi", "wedding", "partner", "rishta", "vivah",
        "spouse", "married", "shadi", "life partner",
    ],
    "relationship": [
        "relationship", "boyfriend", "girlfriend", "love", "breakup",
        "divorce", "separation", "pyaar", "couple",
    ],
    "finance": [
        "finance", "money", "paisa", "financial", "wealth", "income",
        "salary", "invest", "loan", "debt", "savings",
    ],
    "health": [
        "health", "sehat", "sick", "illness", "disease", "body",
        "medical", "bimari", "hospital", "treatment",
    ],
    "education": [
        "education", "study", "exam", "college", "degree", "padhai",
        "school", "university", "admission", "competitive",
    ],
    "foreign": [
        "abroad", "foreign", "visa", "settle", "migrate", "videsh",
        "bahar", "immigration", "overseas", "US", "UK", "Canada",
    ],
    "children": [
        "child", "baby", "pregnant", "conception", "kids", "baccha",
        "beta", "beti", "progeny", "santaan",
    ],
}


def _detect_domain(query: str, provided_domain: Optional[str] = None) -> Optional[str]:
    """Return domain string, preferring provided_domain if given."""
    if provided_domain:
        return provided_domain.lower()
    q = query.lower()
    for domain, keywords in _DOMAIN_KEYWORDS.items():
        if any(k in q for k in keywords):
            return domain
    return None


# ---------------------------------------------------------------------------
# Language detection
# ---------------------------------------------------------------------------

# Unicode script ranges → language tag
_SCRIPT_RANGES: List[tuple] = [
    (r"[\u0900-\u097F]", "hindi"),       # Devanagari → Hindi / Marathi
    (r"[\u0B80-\u0BFF]", "tamil"),       # Tamil script
    (r"[\u0C00-\u0C7F]", "telugu"),      # Telugu script
    (r"[\u0D00-\u0D7F]", "malayalam"),   # Malayalam script
    (r"[\u0A00-\u0A7F]", "punjabi"),     # Gurmukhi → Punjabi
]

# Language code → scenario tag
# -lat suffix = Roman/Latin transliteration of that language
_LANG_CODE_TO_TAG: Dict[str, str] = {
    "en":     "english",
    "hi":     "hindi",
    "hi-lat": "hinglish",
    "hi-Latn":"hinglish",
    "hi-IN":  "hindi",
    "ta":     "tamil",
    "ta-lat": "tamil",
    "te":     "telugu",
    "te-lat": "telugu",
    "ml":     "malayalam",
    "ml-lat": "malayalam",
    "mr":     "marathi",
    "mr-lat": "marathi",
    "pa":     "punjabi",
    "pa-lat": "punjabi",
}

# Roman-script word markers per language (used when language_code is unavailable)
_ROMAN_MARKERS: Dict[str, set] = {
    "hinglish": {"kab", "meri", "mera", "mujhe", "kya", "bahut", "hai",
                 "hoga", "hogi", "mein", "toh", "aur", "nahi", "hain"},
    "tamil":    {"eppo", "eppoday", "unga", "naan", "enna", "romba",
                 "sollungaen", "paakkaena", "theriyum"},
    "telugu":   {"eppudu", "naaku", "meeru", "kaani", "chustey",
                 "cheppandi", "ayindi", "avutundi"},
    "malayalam":{"eppol", "entey", "ningal", "undo", "aakum",
                 "parayan", "cheriyatha", "aarum"},
    "marathi":  {"kadhi", "majhya", "tumchi", "aahe", "hoeel",
                 "sangaa", "vatata", "pan"},
    "punjabi":  {"kado", "meri", "tuhada", "karo", "hovegi",
                 "dassan", "channga", "teri"},
}

# Marathi Devanagari words that distinguish it from Hindi
_MARATHI_MARKERS = {"तुमच्या", "माझ्या", "होईल", "आहे", "सांगा", "करा", "पण", "कधी"}


def _detect_language(query: str, language_code: str) -> str:
    """
    Map language_code + query text to a scenario language tag.

    Priority:
    1. Unicode script range in query text (most reliable)
    2. Language code lookup table
    3. Roman-script keyword heuristics
    4. Fallback: english
    """
    # --- 1. Script detection from query text ---
    for pattern, lang_tag in _SCRIPT_RANGES:
        if re.search(pattern, query):
            # Distinguish Marathi from Hindi (both use Devanagari)
            if lang_tag == "hindi":
                words = set(query.split())
                if words & _MARATHI_MARKERS or language_code in ("mr", "mr-lat"):
                    return "marathi"
            return lang_tag

    # --- 2. Language code lookup ---
    tag = _LANG_CODE_TO_TAG.get(language_code)
    if tag:
        return tag

    # --- 3. Roman-script keyword heuristics ---
    words = set(re.split(r"\W+", query.lower()))
    for lang_tag, markers in _ROMAN_MARKERS.items():
        if words & markers:
            return lang_tag

    return "english"


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def _score_scenario(
    scenario: Dict,
    domain: Optional[str],
    language: str,
    response_mode: str,
) -> int:
    tags: List[str] = scenario.get("tags", [])
    score = 0

    # Domain match is most important
    if domain and domain in tags:
        score += 4
    # Partial domain match (e.g. "relationship" scenario for "marriage" query)
    elif domain in ("marriage", "relationship") and any(t in tags for t in ("marriage", "relationship")):
        score += 2

    # Language match
    # Exact match: highest score
    if language in tags:
        score += 3
    # Close relatives: Devanagari languages understand each other's style
    elif language == "marathi" and "hindi" in tags:
        score += 2
    elif language == "hindi" and "marathi" in tags:
        score += 2
    elif language == "hinglish" and "hindi" in tags:
        score += 1
    # Roman-script variants of any language get partial credit from English
    elif language in ("tamil", "telugu", "malayalam", "punjabi") and "english" in tags:
        score += 1

    # Response mode match
    if response_mode == "detailed" and "detailed" in tags:
        score += 2
    elif response_mode in ("initial", "default", "followup") and "initial" in tags:
        score += 1

    # Prefer non-sensitive topics as first example (sensitive ones are good too, just ranked lower)
    if "sensitive" not in tags:
        score += 1

    return score


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def select_examples(
    query: str,
    language_code: str,
    domain: Optional[str] = None,
    response_mode: str = "initial",
    n: int = 2,
) -> List[Dict]:
    """Return up to n most relevant golden scenarios for the given context."""
    scenarios = _load_scenarios()
    if not scenarios:
        return []

    lang = _detect_language(query, language_code)
    dom = _detect_domain(query, domain)

    scored = sorted(
        scenarios,
        key=lambda s: _score_scenario(s, dom, lang, response_mode),
        reverse=True,
    )
    return scored[:n]


def format_examples_for_prompt(examples: List[Dict]) -> str:
    """
    Format selected golden examples as a few-shot block.

    The block is designed to be injected directly before the user's query
    so the LLM reads it immediately before generating its response.
    """
    if not examples:
        return ""

    parts: List[str] = [
        "## RESPONSE QUALITY EXAMPLES",
        "",
        "Study the examples below for STYLE and TONE only.",
        "⚠ WARNING: The chart facts in these examples (planet dignities, house positions, timing) belong",
        "to DIFFERENT users. Do NOT copy them. Your response must use ONLY the chart data above.",
        "",
        "Quality markers to match:",
        "• Warm, personal opener grounded in the user's specific situation — NOT generic affirmations",
        "• Two astrological factors from THIS user's chart, explained conversationally",
        "• A timing window derived from the dasha data shown above (month-year format)",
        "• One honest nuance referencing a SPECIFIC planet by name",
        "• A natural follow-up offer to go deeper into the chart",
        "",
        "─" * 60,
    ]

    for i, scenario in enumerate(examples, 1):
        conv = scenario.get("conversation", [])

        user_turn = next(
            (t["text"].strip() for t in conv if t["role"] == "user"), ""
        )
        # Skip placeholder "(previous...)" turns used in detail scenarios
        assistant_turns = [
            t["text"].strip()
            for t in conv
            if t["role"] == "assistant" and not t["text"].strip().startswith("(previous")
        ]
        if not user_turn or not assistant_turns:
            continue

        # For detailed scenarios, use the detailed turn (last one)
        assistant_text = assistant_turns[-1]

        parts += [
            f"EXAMPLE {i}:",
            f"User said: {user_turn}",
            "",
            f"Ideal response:",
            assistant_text,
            "",
            "─" * 60,
        ]

    parts += [
        "",
        "Now write a response of the same quality for the actual user question below.",
        "CRITICAL: Copy only the STYLE and TONE from the examples above — NOT the chart facts.",
        "The examples show DIFFERENT users with DIFFERENT charts. Their planetary positions,",
        "dignities ('exalted', 'own sign', 'debilitated'), houses, and timing windows are",
        "SPECIFIC to those example users and MUST NOT appear in your response.",
        "Use ONLY the COMPUTED CHART DATA section above for all planetary facts and timing.",
        "BANNED PHRASES FROM EXAMPLES (do not copy these unless the computed data confirms them):",
        "  • 'apne hi sign mein' — only use if computed chart explicitly shows a planet in own sign",
        "  • 'Navamsa mein Venus apne hi sign mein' — only use if D9 data confirms this",
        "  • 'Jupiter bhi 7th house ko support karega' — only use if transit data shows Jupiter aspecting 7th",
        "  • Any vague 'positive hai' or 'strong hai' for Navamsa — state the specific dignity or house position",
        "  • Any specific month-year window from the examples (those are for different charts)",
        "",
    ]

    return "\n".join(parts)


def get_few_shot_block(
    query: str,
    language_code: str,
    domain: Optional[str] = None,
    response_mode: str = "initial",
    n: int = 2,
) -> str:
    """
    One-call convenience: select examples and format them as a prompt block.

    Returns an empty string if golden scenarios cannot be loaded (safe fallback).
    """
    examples = select_examples(
        query=query,
        language_code=language_code,
        domain=domain,
        response_mode=response_mode,
        n=n,
    )
    return format_examples_for_prompt(examples)

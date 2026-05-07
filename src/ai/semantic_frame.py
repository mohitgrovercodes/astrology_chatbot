# src/ai/semantic_frame.py
"""
Unified Semantic Frame for NakshatraAI.

Single source of truth for "what is the user asking right now". Built once per
turn and consumed everywhere (orchestrator routing, validation engine, synthesis,
prompt builder, post-processing).

Replaces three previously-separate detectors:
  - LLMIntentClassifier.classify          (route — CHITCHAT/RAG/etc.)
  - ContextManager.analyze_message_intent (intent_type + domain + question_mode + polarity)
  - orchestrator_validation_helpers.detect_query_type (validation query_type)

Resolution order (cheapest first, single LLM call as last resort):
  1. nonsense / empty             → CHITCHAT, no LLM
  2. exact pattern cache          → route fixed, no LLM
  3. keyword pre-router           → CALCULATION_ONLY chart-lookup fast-path, no LLM
  4. semantic chitchat router     → CHITCHAT subtype, no LLM
  5. ambiguity heuristic          → AMBIGUOUS (asks for clarification), no LLM
  6. unified LLM call             → fills route + intent_type + domain + question_mode
                                    + polarity + referenced_topic in ONE Gemini Flash call

Why one call instead of three:
  - Latency: 1 LLM RT instead of 2-3.
  - Consistency: route, domain, and intent_type are decided from the same context,
    eliminating "route says RAG_WITH_CALCULATION but domain says general" mismatches.
  - Cost: one Flash call (~$0.0001) replaces two-three.

Backward compatibility:
  - to_legacy_intent_analysis() returns the dict shape that older code reads via
    session_data['intent_analysis'] so the migration can be staged.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, asdict, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Vocabulary
# ──────────────────────────────────────────────────────────────────────────────

ROUTE_CHITCHAT = "CHITCHAT"
ROUTE_CALCULATION_ONLY = "CALCULATION_ONLY"
ROUTE_RAG_WITH_CALCULATION = "RAG_WITH_CALCULATION"
ROUTE_RAG_ONLY = "RAG_ONLY"
ROUTE_AMBIGUOUS = "AMBIGUOUS"

VALID_ROUTES = {
    ROUTE_CHITCHAT,
    ROUTE_CALCULATION_ONLY,
    ROUTE_RAG_WITH_CALCULATION,
    ROUTE_RAG_ONLY,
    ROUTE_AMBIGUOUS,
}

INTENT_CONTINUATION = "CONTINUATION"
INTENT_NEW_TOPIC = "NEW_TOPIC"
INTENT_CLARIFICATION = "CLARIFICATION"

VALID_INTENT_TYPES = {INTENT_CONTINUATION, INTENT_NEW_TOPIC, INTENT_CLARIFICATION}

VALID_DOMAINS = {
    "marriage", "divorce", "career", "finance", "health", "children",
    "foreign", "home", "education", "spirituality", "general",
}

VALID_QUESTION_MODES = {"timing", "qualities", "advice", "summary"}
VALID_POLARITIES = {"positive", "negative", "mixed"}

# Map rich semantic domain → validation engine query_type.
# Validation engine only knows {marriage, career, finance, health, children, foreign, general}.
# This keeps frame.domain expressive while frame.validation_query_type stays compatible.
DOMAIN_TO_VALIDATION_QUERY_TYPE = {
    "marriage": "marriage",
    "divorce": "marriage",        # divorce uses 7th-house/Venus rules, same pool as marriage
    "career": "career",
    "finance": "finance",
    "health": "health",
    "children": "children",
    "foreign": "foreign",
    "foreign_travel": "foreign",  # alias seen elsewhere in the codebase
    "home": "general",            # no dedicated home rules
    "education": "general",
    "spirituality": "general",
    "general": "general",
}

# Sources for provenance (useful for logs / future evals)
SOURCE_CACHE = "cache"
SOURCE_KEYWORD = "keyword"
SOURCE_SEMANTIC = "semantic_router"
SOURCE_LLM = "llm"
SOURCE_FALLBACK = "fallback"
SOURCE_NONSENSE = "nonsense"
SOURCE_AMBIGUITY_HEURISTIC = "ambiguity_heuristic"


# ──────────────────────────────────────────────────────────────────────────────
# Pattern dictionaries (lifted from intent_classifier and orchestrator so the
# frame builder is self-contained — same coverage, deduplicated).
# ──────────────────────────────────────────────────────────────────────────────

# Exact-match pattern cache (route fixed without any LLM call).
SAFE_PATTERN_CACHE: Dict[str, str] = {
    # CHITCHAT
    "hi": ROUTE_CHITCHAT, "hello": ROUTE_CHITCHAT, "hey": ROUTE_CHITCHAT,
    "namaste": ROUTE_CHITCHAT, "good morning": ROUTE_CHITCHAT,
    "good evening": ROUTE_CHITCHAT, "thanks": ROUTE_CHITCHAT,
    "thank you": ROUTE_CHITCHAT, "bye": ROUTE_CHITCHAT, "goodbye": ROUTE_CHITCHAT,

    # CALCULATION_ONLY
    "show my birth chart": ROUTE_CALCULATION_ONLY,
    "show my kundali": ROUTE_CALCULATION_ONLY,
    "show my chart": ROUTE_CALCULATION_ONLY,
    "what is my lagna": ROUTE_CALCULATION_ONLY,
    "what is my ascendant": ROUTE_CALCULATION_ONLY,
    "what is my moon sign": ROUTE_CALCULATION_ONLY,
    "what is my sun sign": ROUTE_CALCULATION_ONLY,
    "what are my current dashas": ROUTE_CALCULATION_ONLY,
    "show my dashas": ROUTE_CALCULATION_ONLY,
    "display my chart": ROUTE_CALCULATION_ONLY,
    "give me my chart": ROUTE_CALCULATION_ONLY,
    "meri rashi kya hai": ROUTE_CALCULATION_ONLY,
    "mera lagna kya hai": ROUTE_CALCULATION_ONLY,
    "what is my rashi": ROUTE_CALCULATION_ONLY,
    "meri kundali dikhao": ROUTE_CALCULATION_ONLY,

    # RAG_ONLY
    "what are panapara houses": ROUTE_RAG_ONLY,
    "what are kendra houses": ROUTE_RAG_ONLY,
    "what is a raj yoga": ROUTE_RAG_ONLY,
    "what is raj yoga": ROUTE_RAG_ONLY,
    "explain the 10th house": ROUTE_RAG_ONLY,
    "explain the 7th house": ROUTE_RAG_ONLY,
    "what does mars in 7th house mean": ROUTE_RAG_ONLY,
    "what does jupiter in 10th house mean": ROUTE_RAG_ONLY,
    "define mahadasha": ROUTE_RAG_ONLY,
    "what is antardasha": ROUTE_RAG_ONLY,
    "what is vimshottari dasha": ROUTE_RAG_ONLY,
    "explain saturn return": ROUTE_RAG_ONLY,

    # RAG_WITH_CALCULATION
    "when will i get married": ROUTE_RAG_WITH_CALCULATION,
    "when will i get a job": ROUTE_RAG_WITH_CALCULATION,
    "when will i have children": ROUTE_RAG_WITH_CALCULATION,
    "when will i buy a house": ROUTE_RAG_WITH_CALCULATION,
    "how is my career": ROUTE_RAG_WITH_CALCULATION,
    "how is my health": ROUTE_RAG_WITH_CALCULATION,
    "how is my marriage": ROUTE_RAG_WITH_CALCULATION,
    "predict my future": ROUTE_RAG_WITH_CALCULATION,
    "main foreign jaunga": ROUTE_RAG_WITH_CALCULATION,
    "videsh yatra": ROUTE_RAG_WITH_CALCULATION,
    "kab jaunga videsh": ROUTE_RAG_WITH_CALCULATION,
    "foreign yatra": ROUTE_RAG_WITH_CALCULATION,
    "abroad travel": ROUTE_RAG_WITH_CALCULATION,
    "when will i go abroad": ROUTE_RAG_WITH_CALCULATION,
}

# Keyword pre-router for CALCULATION_ONLY (catches phrasing variations).
# Ported verbatim from LLMIntentClassifier._CALC_ONLY_TRIGGERS so behaviour is identical.
_CALC_ONLY_TRIGGERS: List[str] = [
    r"\bwhat is my (sun sign|moon sign|lagna|ascendant|rashi|nakshatra|rising sign|birth chart|kundali|kundli|d1|d9|navamsha|atma karaka|amatyakaraka|darakaraka|arudha|chart|planetary position|planets)\b",
    r"\bwhat\'s my (sun sign|moon sign|lagna|ascendant|rashi|nakshatra|rising sign|birth chart|kundali|kundli|d1|d9|navamsha|chart|planetary position|planets)\b",
    r"\bwhen (is|will be) my .*(dasha|mahadasha|antardasha|bhukti)\b",
    r"\b(show|display|give me|dikhao|batao) my (chart|kundali|kundli|dashas|birth chart|navamsha|d9)\b",
    r"\b(mera|meri|mere) (lagna|rashi|nakshatra|kundali|kundli|janam kundali|sun sign|moon sign|ascendant) (kya hai|dikhao|batao|hai)\b",
    r"\b(mera|meri) lagna kya hai\b",
    r"\b(mera|meri) rashi kya hai\b",
    r"\bmeri? kundali? (dikhao|batao)\b",
    r"\bcurrent dasha\b",
    r"\bwhat are my (current )?dashas\b",
    r"\bmy dasha (period|timeline|sequence)\b",
]

# Keyword chitchat triggers (covers single-word multilingual greetings the
# semantic router sometimes misses due to vector dilution).
_CHITCHAT_KEYWORD_ROUTES: Dict[str, str] = {
    # greeting
    "hi": "greeting", "hello": "greeting", "hey": "greeting",
    "namaste": "greeting", "namaskaram": "greeting", "vanakkam": "greeting",
    "hola": "greeting", "howdy": "greeting", "wassup": "greeting",
    "sup": "greeting", "yo": "greeting", "greetings": "greeting",
    "salaam": "greeting", "bonjour": "greeting",
    "good morning": "greeting", "good evening": "greeting", "good afternoon": "greeting",
    # gratitude
    "thanks": "gratitude", "thank you": "gratitude", "thankyou": "gratitude",
    "appreciate it": "gratitude", "grateful": "gratitude",
    "dhanyavad": "gratitude", "shukriya": "gratitude",
    "dhanyawad": "gratitude", "shukriya-ji": "gratitude",
    # wellbeing
    "how are you": "wellbeing", "how's it going": "wellbeing",
    "what's up": "wellbeing", "how do you do": "wellbeing",
    "kaise ho": "wellbeing", "kya haal hai": "wellbeing", "all good": "wellbeing",
    # farewell
    "bye": "farewell", "goodbye": "farewell", "see you": "farewell",
    "talk later": "farewell", "take care": "farewell",
    "alvida": "farewell", "khuda hafiz": "farewell", "catch you later": "farewell",
    # closure
    "ok": "closure", "okay": "closure", "got it": "closure",
    "understood": "closure", "alright": "closure", "sure": "closure",
    "theek hai": "closure", "samajh gaya": "closure", "thik hai": "closure",
    "achha": "closure", "fine": "closure", "makes sense": "closure",
}

# Bare-term ambiguity patterns: when birth data is on file, these are 50/50
# between theory (RAG_ONLY) and personal interpretation (RAG_WITH_CALCULATION).
_AMBIGUOUS_PATTERNS: List[str] = [
    r"\btell me about (jupiter|venus|mars|saturn|mercury|sun|moon|rahu|ketu)\b",
    r"\bwhat (is|are) (the )?(1st|2nd|3rd|4th|5th|6th|7th|8th|9th|10th|11th|12th) house\b",
    r"\bexplain (jupiter|venus|mars|saturn|mercury|sun|moon|rahu|ketu)\b",
    r"\b(jupiter|venus|mars|saturn|mercury|sun|moon|rahu|ketu) in astrology\b",
    r"\btell me about (the )?(1st|2nd|3rd|4th|5th|6th|7th|8th|9th|10th|11th|12th) house\b",
]
_AMBIGUITY_THEORY_MARKERS = (
    "in general", "generally", "what is", "what are", "define",
    "meaning of", "significance of", "in vedic astrology",
    "according to", "classical", "traditional",
)
_AMBIGUITY_PERSONAL_MARKERS = (
    "for me", " my ", " mine", "in my chart", "in my life",
    "will i", "am i", "do i", "should i", "when will i",
    " main ", " mera ", " meri ", " mere ", " mujhe ", " jaunga", " kab ",
)

# Divorce overrides — query phrasing that must override LLM "marriage" classification.
# Standalone break-verb tokens are included so that natural speech with intervening
# words (e.g. "shaadi kab tootegi") is still caught even without an adjacent compound.
_DIVORCE_KEYWORDS = (
    "divorce", "separation", "talaq", "breakup", "break-up",
    "judicial separation", "relationship end", "marriage end",
    # Compound Hindi/Hinglish phrases
    "shaadi tootegi", "shaadi toot jayegi", "shaadi tootega",
    "shaadi toot jayega", "shaadi khatam",
    "rishta tootega", "rishta toot jayega", "rishta khatam",
    "relationship khatam",
    # Standalone break-verb tokens (cover "shaadi kab tootegi", "rishta kab tootega" etc.)
    "tootegi", "tootega", "toot jayegi", "toot jayega",
    "toot gayi", "toot gaya", "tutegi", "tutega",
)


# ──────────────────────────────────────────────────────────────────────────────
# Frame
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class SemanticFrame:
    """Structured snapshot of what the user is asking, computed once per turn."""

    # Routing — which orchestrator pipeline handles this query.
    route: str = ROUTE_RAG_WITH_CALCULATION
    route_confidence: float = 0.5

    # Conversation continuity — how this turn relates to history.
    intent_type: str = INTENT_NEW_TOPIC
    referenced_topic: Optional[str] = None
    requires_context: bool = False

    # Semantic content — the life area the user is asking about.
    domain: str = "general"
    question_mode: str = "summary"
    polarity: str = "mixed"

    # Provenance.
    confidence: float = 0.5
    reasoning: str = ""
    source: str = SOURCE_FALLBACK

    # Subtype hints used by chitchat handler (greeting/identity/...).
    chitchat_subtype: Optional[str] = None

    # Raw artifacts for debugging.
    raw_llm_response: Optional[str] = None
    fast_path_match: Optional[str] = None  # which pattern fired, if any

    # ─── Derived properties ────────────────────────────────────────────────

    @property
    def validation_query_type(self) -> str:
        """Map domain to validation engine's allowed query_type."""
        return DOMAIN_TO_VALIDATION_QUERY_TYPE.get(
            (self.domain or "general").lower(),
            "general",
        )

    @property
    def is_chitchat(self) -> bool:
        return self.route == ROUTE_CHITCHAT

    @property
    def needs_chart(self) -> bool:
        return self.route in {ROUTE_CALCULATION_ONLY, ROUTE_RAG_WITH_CALCULATION}

    # ─── Serialization ─────────────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        # Augment with derived fields so downstream consumers don't need the class
        d["validation_query_type"] = self.validation_query_type
        return d

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> Optional["SemanticFrame"]:
        if not data:
            return None
        # Drop derived fields — dataclass init doesn't accept them
        clean = {k: v for k, v in data.items() if k != "validation_query_type"}
        try:
            return cls(**clean)
        except TypeError as e:
            logger.warning(f"[FRAME] from_dict failed ({e}); reconstructing best-effort")
            allowed = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
            return cls(**{k: v for k, v in clean.items() if k in allowed})

    def to_legacy_intent_analysis(self) -> Dict[str, Any]:
        """Backward-compat shape consumed by older code reading session_data['intent_analysis']."""
        return {
            "intent_type": self.intent_type,
            "domain": self.domain,
            "question_mode": self.question_mode,
            "polarity": self.polarity,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "referenced_topic": self.referenced_topic,
            "requires_context": self.requires_context,
        }


# ──────────────────────────────────────────────────────────────────────────────
# Builder
# ──────────────────────────────────────────────────────────────────────────────

UNIFIED_PROMPT = """You are a query analyzer for a Vedic astrology chatbot. The user always has birth details on file. The query may be in English, Hindi, Hinglish, or any mix.

CONVERSATION SUMMARY:
{summary}

RECENT CONVERSATION:
{history}

CURRENT USER MESSAGE:
"{query}"

Analyze the message on FIVE axes simultaneously and return a single JSON object.

────────────────────────────────────────────────────────────────────
1) ROUTE — which pipeline must handle this:

   - CHITCHAT: greetings, thanks, identity, wellbeing, farewell, closure
       e.g. "hi", "thanks", "who are you", "kaise ho"

   - CALCULATION_ONLY: a raw factual lookup directly from the chart
       e.g. "what is my lagna", "show my kundali", "when is my Saturn dasha"
       NOTE: dasha date lookups are CALCULATION_ONLY, not predictions.

   - RAG_WITH_CALCULATION: a prediction, interpretation, or advice about THIS user's life
       e.g. "when will I get married", "how is my career", "will I go abroad",
            "what does my Saturn placement mean for me"

   - RAG_ONLY: general theory not tied to the user's chart (no "my", "me", "I")
       e.g. "what is raj yoga", "explain 10th house", "what does Mars in 7th mean"

   - AMBIGUOUS: a bare planet/house mention with NO clear intent
       e.g. "Jupiter", "7th house" (alone, no context)

────────────────────────────────────────────────────────────────────
2) INTENT_TYPE — relative to the recent conversation:

   - CONTINUATION: same topic as the bot's previous reply
   - NEW_TOPIC:   a different life area
   - CLARIFICATION: asking what something the bot said means

────────────────────────────────────────────────────────────────────
3) DOMAIN — the LIFE AREA the question is really about. Be specific.

   Allowed values: marriage | divorce | career | finance | health | children
                 | foreign | home | education | spirituality | general

   Disambiguation rules (read carefully):
   - "Meri shaadi kab tootegi" / "rishta khatam hoga" / "talaq"  → divorce  (NOT marriage)
   - "Meri shaadi kab hogi" / "kaisi hogi" / "partner kaisa hoga" → marriage
   - "Foreign settle hounga" / "videsh yatra"                     → foreign
   - "Property kab kharidunga" / "ghar"                           → home
   - "Padhai" / "exam" / "studies"                                → education
   - Use general only when no specific life area is implied.

────────────────────────────────────────────────────────────────────
4) QUESTION_MODE — what kind of answer the user expects:

   - timing:    when / kab / which year / kitne saal mein
   - qualities: kaisa / kaisi / what kind of / nature of
   - advice:    should I / kya karoon / what should I do
   - summary:   tell me about / general overview

────────────────────────────────────────────────────────────────────
5) POLARITY — emotional framing of the question:

   - positive: hopeful, looking forward
   - negative: anxious, worried, asking about loss/end/break
   - mixed:    factual or neutral

────────────────────────────────────────────────────────────────────
Also extract:

  - referenced_topic: if CONTINUATION/CLARIFICATION, name the topic specifically
                     (e.g. "Pisces moon sign", "career change"). Else null.
  - requires_context: true if the message uses pronouns or terse follow-ups
                     ("tell me more", "why?", "and?")
  - confidence:       0.0–1.0 for the overall analysis
  - reasoning:        ONE short sentence explaining the call

Respond with ONLY this JSON, no markdown fences, no extra text:
{{
  "route": "...",
  "route_confidence": 0.95,
  "intent_type": "...",
  "domain": "...",
  "question_mode": "...",
  "polarity": "...",
  "referenced_topic": null,
  "requires_context": false,
  "confidence": 0.9,
  "reasoning": "..."
}}
"""


class SemanticFrameBuilder:
    """Builds a SemanticFrame from query + history using fast paths first, then LLM.

    Stateless — safe to construct as a singleton or per-request.
    """

    def __init__(self, fast_llm=None, semantic_router=None):
        self.fast_llm = fast_llm
        self.semantic_router = semantic_router  # optional — used for chitchat subtype detection
        # Cache built frames by (normalized_query, history_signature) to skip
        # repeat work on identical replays. Tiny cache; prevents accidental thrash.
        self._cache: Dict[str, SemanticFrame] = {}

    def set_llm(self, fast_llm) -> None:
        self.fast_llm = fast_llm

    # ─── Public API ────────────────────────────────────────────────────────

    def build(
        self,
        query: str,
        conversation_history: Optional[List[Dict]] = None,
        conversation_summary: Optional[str] = None,
        user_profile: Optional[Dict] = None,
    ) -> SemanticFrame:
        """Compute the full SemanticFrame for this turn."""
        history = conversation_history or []
        q_raw = (query or "").strip()
        q_normalized = q_raw.lower().rstrip("?!.,")

        # 1) Nonsense / empty
        if self._is_nonsensical(q_raw):
            logger.info("[FRAME] nonsense input → CHITCHAT")
            return SemanticFrame(
                route=ROUTE_CHITCHAT, route_confidence=0.95,
                intent_type=INTENT_NEW_TOPIC,
                confidence=0.95, reasoning="Nonsense or empty input",
                source=SOURCE_NONSENSE, fast_path_match="nonsense",
            )

        # 2) Exact pattern cache
        cached_route = SAFE_PATTERN_CACHE.get(q_normalized)
        if cached_route:
            logger.info(f"[FRAME] pattern cache hit → {cached_route}")
            return self._frame_from_route(
                route=cached_route,
                source=SOURCE_CACHE,
                fast_path_match=q_normalized,
                confidence=0.98,
                reasoning=f"Exact pattern match: {cached_route}",
                domain=self._infer_domain_from_query(q_raw),
                question_mode=self._infer_question_mode_from_query(q_raw),
                history=history,
            )

        # 3) Keyword chitchat (multilingual single-word greeting etc.)
        chitchat_subtype = _CHITCHAT_KEYWORD_ROUTES.get(q_normalized)
        if chitchat_subtype:
            logger.info(f"[FRAME] keyword chitchat → {chitchat_subtype}")
            return SemanticFrame(
                route=ROUTE_CHITCHAT, route_confidence=1.0,
                intent_type=INTENT_NEW_TOPIC, confidence=1.0,
                reasoning=f"Keyword chitchat match: {chitchat_subtype}",
                source=SOURCE_KEYWORD, fast_path_match=q_normalized,
                chitchat_subtype=chitchat_subtype,
                domain="general", question_mode="summary",
            )

        # 4) Keyword pre-router for CALCULATION_ONLY (chart fact lookups)
        for pat in _CALC_ONLY_TRIGGERS:
            if re.search(pat, q_normalized):
                logger.info("[FRAME] keyword pre-router → CALCULATION_ONLY")
                return self._frame_from_route(
                    route=ROUTE_CALCULATION_ONLY,
                    source=SOURCE_KEYWORD,
                    fast_path_match=pat,
                    confidence=0.97,
                    reasoning="Keyword pre-router: chart-lookup pattern",
                    domain=self._infer_domain_from_query(q_raw),
                    question_mode="summary",
                    history=history,
                )

        # 5) Semantic chitchat router (catches phrasing variants the keyword
        # cache misses, e.g. "what's your name", "namaskaram ji").
        if self.semantic_router and getattr(self.semantic_router, "model", None):
            try:
                match = self.semantic_router.route(query, threshold=0.7)
                if match and match.name in {
                    "greeting", "identity", "personal_profile_query",
                    "gratitude", "wellbeing", "farewell", "closure",
                    "chitchat",
                }:
                    logger.info(f"[FRAME] semantic router → CHITCHAT ({match.name}, {match.confidence:.2f})")
                    return SemanticFrame(
                        route=ROUTE_CHITCHAT, route_confidence=float(match.confidence),
                        intent_type=INTENT_NEW_TOPIC,
                        confidence=float(match.confidence),
                        reasoning=f"Semantic chitchat match: {match.name}",
                        source=SOURCE_SEMANTIC, fast_path_match=match.name,
                        chitchat_subtype=match.name,
                    )
            except Exception as e:
                logger.debug(f"[FRAME] semantic router error: {e}")

        # 6) Ambiguity heuristic — bare planet/house with no clear intent
        if user_profile and user_profile.get("date_of_birth") and self._is_ambiguous(q_normalized):
            logger.info("[FRAME] ambiguity heuristic → AMBIGUOUS")
            return SemanticFrame(
                route=ROUTE_AMBIGUOUS, route_confidence=0.9,
                intent_type=INTENT_NEW_TOPIC,
                confidence=0.9,
                reasoning="Bare planet/house mention; needs clarification",
                source=SOURCE_AMBIGUITY_HEURISTIC,
                domain="general", question_mode="summary",
            )

        # 7) Unified LLM call — fills route + intent_type + domain + question_mode + polarity
        if self.fast_llm is not None:
            llm_frame = self._llm_classify(
                query=q_raw,
                history=history,
                conversation_summary=conversation_summary,
            )
            if llm_frame is not None:
                # Apply divorce override after LLM (the prompt covers it but defense in depth).
                self._apply_divorce_override(llm_frame, q_raw)
                return llm_frame

        # 8) Fallback (LLM unavailable or failed) — best-effort heuristic.
        logger.info("[FRAME] LLM unavailable / failed → heuristic fallback")
        fallback = self._heuristic_fallback(q_raw, history)
        # Apply domain inference + divorce override to fallback the same way
        # the LLM path does — otherwise Hinglish divorce queries land on domain="general".
        if fallback.domain == "general":
            fallback.domain = self._infer_domain_from_query(q_raw)
        self._apply_divorce_override(fallback, q_raw)
        return fallback

    # ─── Step helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _is_nonsensical(query: str) -> bool:
        q = query.strip()
        if not q or len(q) < 2:
            return True
        if len(q) > 4 and not any(v in q.lower() for v in "aeiouy"):
            common = ("krish", "hmm", "hmmm", "kk")
            if not any(c in q.lower() for c in common):
                return True
        return False

    @staticmethod
    def _is_ambiguous(query_lower: str) -> bool:
        for pat in _AMBIGUOUS_PATTERNS:
            if re.search(pat, query_lower):
                if any(m in query_lower for m in _AMBIGUITY_THEORY_MARKERS):
                    return False
                if any(m in f" {query_lower} " for m in _AMBIGUITY_PERSONAL_MARKERS):
                    return False
                return True
        return False

    def _llm_classify(
        self,
        query: str,
        history: List[Dict],
        conversation_summary: Optional[str],
    ) -> Optional[SemanticFrame]:
        """One LLM call producing the full frame. Returns None on failure."""
        try:
            prompt = UNIFIED_PROMPT.format(
                summary=conversation_summary or "No summary yet — early conversation.",
                history=self._format_history(history) or "No previous messages.",
                query=query,
            )
            response = self.fast_llm.invoke(prompt)
            raw = response.content if hasattr(response, "content") else str(response)
            parsed = self._parse_llm_json(raw)
            if not parsed:
                logger.warning("[FRAME] LLM returned unparseable JSON — falling back")
                return None

            frame = SemanticFrame(
                route=self._coerce_route(parsed.get("route")),
                route_confidence=self._coerce_float(parsed.get("route_confidence"), 0.8),
                intent_type=self._coerce_intent_type(parsed.get("intent_type")),
                domain=self._coerce_domain(parsed.get("domain")),
                question_mode=self._coerce_question_mode(parsed.get("question_mode")),
                polarity=self._coerce_polarity(parsed.get("polarity")),
                referenced_topic=parsed.get("referenced_topic") or None,
                requires_context=bool(parsed.get("requires_context", False)),
                confidence=self._coerce_float(parsed.get("confidence"), 0.7),
                reasoning=str(parsed.get("reasoning") or "")[:300],
                source=SOURCE_LLM,
                raw_llm_response=raw[:500],
            )
            logger.info(
                f"[FRAME] LLM → route={frame.route} domain={frame.domain} "
                f"intent_type={frame.intent_type} qmode={frame.question_mode} "
                f"polarity={frame.polarity} conf={frame.confidence:.2f}"
            )
            return frame
        except Exception as e:
            logger.warning(f"[FRAME] LLM call failed: {e}")
            return None

    @staticmethod
    def _heuristic_fallback(query: str, history: List[Dict]) -> SemanticFrame:
        """Cheap pattern fallback when the LLM is unavailable."""
        q = query.lower().strip()
        # CHITCHAT
        if any(p in q for p in ("hi", "hello", "thanks", "thank you", "namaste", "bye", "who are you")):
            return SemanticFrame(
                route=ROUTE_CHITCHAT, route_confidence=0.7,
                intent_type=INTENT_NEW_TOPIC, confidence=0.7,
                reasoning="Heuristic fallback: conversational pattern",
                source=SOURCE_FALLBACK,
            )

        # RAG_ONLY (general theory)
        is_theory = any(m in q for m in ("what is", "what does", "explain", "define", "tell me about"))
        is_personal = " my " in f" {q} " or " mera " in f" {q} " or "i " in q.split()[:2] if q.split() else False
        if is_theory and not is_personal:
            return SemanticFrame(
                route=ROUTE_RAG_ONLY, route_confidence=0.65,
                intent_type=INTENT_NEW_TOPIC, confidence=0.65,
                reasoning="Heuristic fallback: theory pattern",
                source=SOURCE_FALLBACK,
            )

        # Default to RAG_WITH_CALCULATION (most common for personal queries)
        return SemanticFrame(
            route=ROUTE_RAG_WITH_CALCULATION, route_confidence=0.6,
            intent_type=INTENT_CONTINUATION if history else INTENT_NEW_TOPIC,
            confidence=0.6,
            reasoning="Heuristic fallback: default to personalized prediction",
            source=SOURCE_FALLBACK,
        )

    # ─── Coercion / parsing ────────────────────────────────────────────────

    @staticmethod
    def _coerce_route(value: Any) -> str:
        s = str(value or "").upper().strip()
        return s if s in VALID_ROUTES else ROUTE_RAG_WITH_CALCULATION

    @staticmethod
    def _coerce_intent_type(value: Any) -> str:
        s = str(value or "").upper().strip()
        return s if s in VALID_INTENT_TYPES else INTENT_NEW_TOPIC

    @staticmethod
    def _coerce_domain(value: Any) -> str:
        s = str(value or "").lower().strip()
        if s == "foreign_travel":  # alias the LLM sometimes emits
            return "foreign"
        return s if s in VALID_DOMAINS else "general"

    @staticmethod
    def _coerce_question_mode(value: Any) -> str:
        s = str(value or "").lower().strip()
        return s if s in VALID_QUESTION_MODES else "summary"

    @staticmethod
    def _coerce_polarity(value: Any) -> str:
        s = str(value or "").lower().strip()
        return s if s in VALID_POLARITIES else "mixed"

    @staticmethod
    def _coerce_float(value: Any, default: float) -> float:
        try:
            f = float(value)
            if f < 0:
                return 0.0
            if f > 1:
                return 1.0
            return f
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _parse_llm_json(raw: str) -> Optional[Dict[str, Any]]:
        """Robustly extract JSON from LLM text. Strips markdown fences."""
        if not raw:
            return None
        text = raw.strip()
        # Strip ```json or ``` fences
        if "```json" in text.lower():
            m = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
            if m:
                text = m.group(1).strip()
        elif text.startswith("```"):
            m = re.search(r"```\s*(.*?)\s*```", text, re.DOTALL)
            if m:
                text = m.group(1).strip()
        text = text.strip("`").strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Last resort: extract the first balanced {...}
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                pass
        return None

    @staticmethod
    def _format_history(history: List[Dict], max_messages: int = 6) -> str:
        if not history:
            return ""
        lines = []
        for m in history[-max_messages:]:
            role = m.get("role", "user").upper()
            content = (m.get("content") or "")[:200]
            lines.append(f"{role}: {content}")
        return "\n".join(lines)

    # ─── Domain inference helpers (used by fast paths that skip the LLM) ──

    @staticmethod
    def _infer_domain_from_query(query: str) -> str:
        """Cheap keyword inference for the fast paths. LLM is the source of truth otherwise."""
        q = query.lower()
        # Divorce overrides marriage when present
        if any(k in q for k in _DIVORCE_KEYWORDS):
            return "divorce"
        if any(k in q for k in ("marriage", "marr", "shaadi", "shadi", "vivah", "wedding", "spouse",
                                 "partner", "rishta", "love")):
            return "marriage"
        if any(k in q for k in ("career", "job", "naukri", "profession", "business", "kaam", "promotion")):
            return "career"
        if any(k in q for k in ("money", "finance", "wealth", "income", "paisa", "dhan", "arthik")):
            return "finance"
        if any(k in q for k in ("health", "illness", "disease", "swasthya", "bimari", "sehat")):
            return "health"
        if any(k in q for k in ("child", "children", "santaan", "bacche", "pregnancy", "baby")):
            return "children"
        if any(k in q for k in ("foreign", "abroad", "videsh", "overseas", "visa", "settlement")):
            return "foreign"
        if any(k in q for k in ("home", "house", "ghar", "property", "real estate")):
            return "home"
        if any(k in q for k in ("study", "studies", "education", "padhai", "exam", "college")):
            return "education"
        return "general"

    @staticmethod
    def _infer_question_mode_from_query(query: str) -> str:
        q = query.lower()
        if any(w in q for w in ("when", "kab", "timing", "which year", "kitne", "month", "kab hoga", "kab hogi")):
            return "timing"
        if any(w in q for w in ("kaisi", "kaisa", "what kind", "what type", "nature of", "kya rakhne")):
            return "qualities"
        if any(w in q for w in ("should i", "kya karoon", "what should", "kya karna")):
            return "advice"
        return "summary"

    # ─── Helpers shared across fast paths ─────────────────────────────────

    @staticmethod
    def _apply_divorce_override(frame: SemanticFrame, query: str) -> None:
        """If query literally mentions divorce/separation, force domain=divorce."""
        q = query.lower()
        if any(k in q for k in _DIVORCE_KEYWORDS):
            if frame.domain != "divorce":
                logger.info(
                    f"[FRAME] divorce override: {frame.domain} → divorce "
                    f"(matched literal divorce/separation phrasing)"
                )
                frame.domain = "divorce"
                # Treat as a fresh topic shift rather than continuation of generic marriage talk
                frame.intent_type = INTENT_NEW_TOPIC
                frame.referenced_topic = "divorce or separation"

    def _frame_from_route(
        self,
        route: str,
        source: str,
        fast_path_match: str,
        confidence: float,
        reasoning: str,
        domain: str,
        question_mode: str,
        history: List[Dict],
    ) -> SemanticFrame:
        """Build a frame for fast paths that resolved route deterministically."""
        return SemanticFrame(
            route=route, route_confidence=confidence,
            intent_type=INTENT_CONTINUATION if history else INTENT_NEW_TOPIC,
            domain=domain,
            question_mode=question_mode,
            polarity="mixed",
            confidence=confidence,
            reasoning=reasoning,
            source=source, fast_path_match=fast_path_match,
        )


# ──────────────────────────────────────────────────────────────────────────────
# Convenience builder (singleton) — let consumers import a ready-made instance
# without each module needing to wire dependencies.
# ──────────────────────────────────────────────────────────────────────────────

_default_builder: Optional[SemanticFrameBuilder] = None


def get_semantic_frame_builder(
    fast_llm=None,
    semantic_router=None,
) -> SemanticFrameBuilder:
    """Return the process-wide builder, creating it on first call.

    Subsequent calls update the LLM/router only if the existing builder has
    none set — this lets early init from chat_stateless win over later imports
    that pass None.
    """
    global _default_builder
    if _default_builder is None:
        _default_builder = SemanticFrameBuilder(fast_llm=fast_llm, semantic_router=semantic_router)
        return _default_builder
    if _default_builder.fast_llm is None and fast_llm is not None:
        _default_builder.set_llm(fast_llm)
    if _default_builder.semantic_router is None and semantic_router is not None:
        _default_builder.semantic_router = semantic_router
    return _default_builder

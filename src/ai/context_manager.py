# src/ai/context_manager.py
"""
AI Context Manager for NakshatraAI.

Handles intelligent conversation analysis, semantic query resolution,
summarization, and progressive disclosure conversation phase tracking.
"""

import json
import logging
from typing import Dict, List, Optional, Any
from src.llm.factory import LLMFactory

logger = logging.getLogger(__name__)


# ── Conversation Phase Constants ──────────────────────────────────────────────
# Phases control the progressive disclosure response pattern:
#   INITIAL           → First time asking a question on this topic
#   AWAITING_DETAIL   → Bot asked "want more details?" — waiting for yes/no
#   FOLLOWUP_LOOP     → Bot asked a follow-up question — loop continues
PHASE_INITIAL = "INITIAL"
PHASE_AWAITING_DETAIL = "AWAITING_DETAIL"
PHASE_FOLLOWUP_LOOP = "FOLLOWUP_LOOP"


# ── Affirmative / Negative Detection ─────────────────────────────────────────
_AFFIRMATIVE_SIGNALS = {
    # English
    'yes', 'yeah', 'yep', 'yup', 'sure', 'ok', 'okay', 'go ahead',
    'please', 'yes please', 'tell me', 'tell me more', 'more details',
    'explain more', 'elaborate', 'go on', 'continue', 'of course',
    'definitely', 'absolutely', 'why not', 'i want to know',
    'more information', 'yes, please', 'sure thing', 'alright',
    'sounds good', 'let me know', "i'd like that", 'that would be great',
    'hmm', 'uh huh', 'mm', 'interesting', 'okay go on',
    # Hindi / Hinglish
    'haan', 'ha', 'haji', 'bilkul', 'zaroor', 'aur batao', 'aur bataiye',
    'haan bataiye', 'haan ji', 'theek hai batao', 'batao', 'bataiye',
    'ji haan', 'detail mein batao', 'detail se batao', 'aur samjhao',
    'samjhao', 'samjhaiye', 'samjha do', 'bata do', 'bata na', 'batao na',
    'kar do', 'karo', 'theek hai karo', 'achha batao', 'achha samjhao',
    # Tamil
    'aamam', 'seri', 'sollunga',
    # Punjabi
    'haanji', 'hanji', 'ha ji', 'bilkul ji', 'dasso',
}

_NEGATIVE_SIGNALS = {
    # English
    'no', 'nah', 'nope', 'not now', 'no thanks', 'no thank you',
    'skip', 'not interested', 'maybe later', 'that\'s enough',
    'i\'m good', 'enough', 'pass', 'not really', 'no need',
    'that\'s fine', 'no its ok', 'no its okay', 'leave it',
    # Hindi / Hinglish
    'nahi', 'naa', 'rehne do', 'mat batao', 'bas', 'itna kaafi hai',
    'koi zaroorat nahi', 'chhodo', 'nahi chahiye',
    # Tamil
    'venda', 'illai', 'podhum',
    # Punjabi
    'nahi ji', 'nai', 'rehna do',
}


def detect_user_response_type(query: str) -> str:
    """Detect if user is giving an affirmative, negative, or other response.

    Returns: 'AFFIRMATIVE', 'NEGATIVE', or 'OTHER'
    """
    q = query.lower().strip().rstrip('!.,?')

    # Exact match
    if q in _AFFIRMATIVE_SIGNALS:
        return 'AFFIRMATIVE'
    if q in _NEGATIVE_SIGNALS:
        return 'NEGATIVE'

    # Prefix match for longer signals (len > 3 avoids noisy short prefixes)
    if any(q.startswith(s) for s in _AFFIRMATIVE_SIGNALS if len(s) > 3):
        return 'AFFIRMATIVE'
    if any(q.startswith(s) for s in _NEGATIVE_SIGNALS if len(s) > 3):
        return 'NEGATIVE'

    # Short-token prefix match — handles "ok karo", "ha bhai", "haan samjhao",
    # "no please", "nahi yaar" etc. where the affirmative/negative is the first word.
    _SHORT_AFF = ('ok ', 'ok,', 'ha ', 'ha,', 'haan ', 'hmm ', 'hmm,')
    _SHORT_NEG = ('no ', 'no,', 'nahi ', 'naa ', 'nai ')
    if any(q.startswith(p) for p in _SHORT_AFF):
        return 'AFFIRMATIVE'
    if any(q.startswith(p) for p in _SHORT_NEG):
        return 'NEGATIVE'

    return 'OTHER'


# ── Follow-up Question Domains ────────────────────────────────────────────────
# Each domain maps to follow-up questions the bot CAN reliably answer.
# These are used as LLM-prompt guidance — the LLM picks the most relevant one
# based on what was already discussed.
FOLLOWUP_QUESTION_BANK = {
    'marriage': [
        "Jupiter in your 3rd house is your 7th lord — that placement quietly shapes what your future partner will be like. What does it actually reveal about their personality?",
        "Venus is the primary karaka for love and marriage, and its exact placement in your chart tells a very specific story about your romantic life — what does yours say?",
        "The Navamsa (D9) chart is the real test of marriage strength in Vedic astrology — your birth chart sets the stage, but D9 reveals the depth. What does yours show?",
        "Your 2nd house (family) and 5th house (romance) together map the full journey from falling in love to building a home — what pattern do they form in your chart?",
        "There are specific Dasha periods in your chart that activate marriage far more powerfully than others — and some of them might surprise you. Which ones stand out?",
        "Interestingly, the same planetary period that opens your marriage window also influences your financial life — your chart connects these two in a specific way. Want to see how?",
    ],
    'career': [
        "Your 10th house lord's placement is the single biggest indicator of which career direction suits you best — it's quite specific in your chart. What does it point to?",
        "The 11th house in your chart reveals your true income ceiling and how you'll actually reach it — job, business, or something else entirely. What does yours show?",
        "Saturn's position shapes everything about long-term career — discipline, delays, and the eventual breakthrough. Its placement in your chart has a particular story to tell.",
        "There's a window in your Dasha timeline when career growth accelerates sharply — a promotion, a leap, or a complete shift. When does that open for you?",
        "Your lagnesh (ascendant lord) is the captain of your whole chart — where it sits tells you what drives your ambition. Its placement in your chart is quite revealing.",
        "Your 2nd and 11th houses together tell the real financial story behind your career — not just what you earn, but how and when. What do they indicate?",
    ],
    'finance': [
        "Your 2nd house (accumulated wealth) and 11th house (income gains) together reveal your real wealth-building pattern — and there's something specific worth knowing about yours.",
        "There's a planetary period in your timeline that's unusually powerful for financial gains — it's coming, and it's worth knowing exactly when.",
        "Your chart has clear indicators about whether you're built more for a job, business, or investments — which one does it favour?",
        "Jupiter and Venus are the two primary wealth karakas — their placements in your chart say a lot about your relationship with money. Where do they sit?",
        "Your career growth and financial growth windows are connected in your chart in an interesting way — the same period that advances one tends to move the other.",
    ],
    'health': [
        "Your 6th house is the primary health indicator in Vedic astrology — its lord's placement points to specific areas that need attention in your chart.",
        "Certain Dasha and Antardasha periods bring health pressure — not to alarm, but knowing which ones lets you be prepared. Which ones appear in your chart?",
        "Your lagna and its lord define your constitution and natural vitality — it's the foundation of everything else. What does your chart say about your physical makeup?",
        "Mars and Saturn together govern physical endurance and vulnerability — their placements in your chart tell a clear story about stamina and what to watch.",
    ],
    'children': [
        "Your 5th house is the primary house for children in Vedic astrology — its lord's placement gives specific clues about timing and the nature of your children.",
        "Jupiter is the karaka for children, and its placement in your chart says a lot — not just about children, but also about fortune and wisdom. Where does it sit?",
        "The 5th house also governs intelligence, creativity, and past-life merit — beyond children, there's a fascinating picture of your natural gifts hidden there.",
    ],
    'foreign': [
        "Rahu is the primary indicator for foreign connections and unconventional paths — its placement in your chart gives very specific clues about your ties to distant places.",
        "The 9th and 12th houses together map your foreign travel and settlement story — one shows the journey, the other shows where you might actually land. What do they say?",
        "Foreign opportunities in your chart tend to cluster around specific Dasha periods — some are for career, some for personal growth. Which ones are yours?",
    ],
    'general': [
        "Your Dasha timeline has some interesting peaks and valleys ahead — the next major phase shift is closer than you might think. What does it look like?",
        "Every chart has 2-3 standout planetary positions that give real natural advantages — yours has some specific ones worth knowing about.",
        "There's a significant transit in your chart right now that's quietly shaping your circumstances — what is it and how much longer does it last?",
        "Your lagna and its lord are the foundation of your entire chart — they reveal your core personality and life direction in a very specific way.",
        "Your Sade Sati status (Saturn transiting near your Moon sign) has a measurable effect on mood, effort, and outcomes — what does yours currently show?",
        "Every chart has one dominant planet that colours the whole life — a kind of personal signature. Which one is yours and what does it mean for your path?",
    ],
}

# Answerable topics per domain — used to constrain LLM-generated follow-up questions
# so the chatbot only asks about things it can actually answer from chart data.
ANSWERABLE_TOPICS_BY_DOMAIN: Dict[str, List[str]] = {
    'marriage': [
        'partner personality from 7th house lord sign and placement',
        'Venus placement and romantic life indicators',
        'D9 (Navamsa) chart marriage depth and partner nature',
        '7th house occupants and aspects on it',
        'marriage compatibility factors',
        'family dynamics from 2nd and 4th houses',
        'love-to-marriage journey via 5th house',
        'dasha periods that activate marriage strongly',
    ],
    'career': [
        '10th lord placement and best career directions',
        'income potential from 11th house',
        'Saturn influence on career discipline and timeline',
        'promotion or career leap window in Dasha',
        'lagnesh placement and professional drive',
        '6th house work environment indicators',
        'financial growth from 2nd and 11th houses',
    ],
    'finance': [
        'wealth potential from 2nd and 11th houses',
        'upcoming financial gain periods in Dasha',
        'job vs business vs investment aptitude',
        'Jupiter and Venus as wealth karakas',
        'career and financial growth alignment',
    ],
    'health': [
        '6th house health areas to watch',
        'dasha periods with health sensitivity',
        'constitution and vitality from lagna lord',
        'Mars and Saturn placements for physical endurance',
        '8th house and longevity indicators',
    ],
    'children': [
        '5th house timing and children nature',
        'Jupiter placement for children and fortune',
        '5th house intelligence and creativity indicators',
    ],
    'foreign': [
        'Rahu placement and foreign connections',
        'directions and regions of opportunity',
        '9th and 12th houses for travel and settlement',
        'career-linked foreign opportunity periods',
    ],
    'general': [
        'next major Dasha phase and its themes',
        'strongest planetary positions and natural advantages',
        'significant current transit and its duration',
        'lagna lord placement and life direction',
        'Sade Sati status and current impact',
        'dominant planet and its life influence',
    ],
}


def generate_followup_question(
    topic: str,
    last_answer: str,
    language: str,
    fast_llm,
    fallback: str = ""
) -> str:
    """Generate a contextually relevant follow-up question using the fast LLM.

    The question is constrained to chart-answerable topics so the chatbot can
    always answer what it asks.  Falls back to `fallback` on any error.
    """
    if not fast_llm:
        return fallback

    domain_topics = ANSWERABLE_TOPICS_BY_DOMAIN.get(topic.lower(), ANSWERABLE_TOPICS_BY_DOMAIN['general'])
    topics_list = '\n'.join(f'- {t}' for t in domain_topics)

    lang_hint = {
        'hi': 'Hindi (Roman/Devanagari, conversational Hinglish is fine)',
        'hi-lat': 'Hinglish (Roman-script Hindi)',
        'ta': 'Tamil',
        'pa': 'Punjabi',
        'en': 'English',
    }.get(language, 'match the language of the last answer')

    prompt = f"""An astrology chatbot just answered a question about "{topic}".

Last answer (excerpt): "{last_answer[:300]}"

Generate ONE short follow-up question for the user. Rules:
1. The question MUST be about one of these chart-answerable topics only:
{topics_list}
2. Do NOT repeat what was already covered in the last answer.
3. Phrase it as a direct observation + intriguing question, like a curious human astrologer would ask.
   WRONG style: "Would you like to know about your Venus?" / "Shall I explain X?"
   RIGHT style: "Venus in your chart carries a very specific message about your love life — what does it actually say?"
4. Language: {lang_hint}
5. Length: 15-25 words maximum.
6. Return ONLY the question itself — no preamble, no quotes, no explanation."""

    try:
        response = fast_llm.invoke(prompt)
        q = (response.content if hasattr(response, 'content') else str(response)).strip().strip('"').strip("'")
        if q and len(q) > 8:
            return q
    except Exception:
        pass

    return fallback


def detect_response_type_with_llm_fallback(
    query: str,
    last_bot_message: str,
    fast_llm,
    current_phase: str
) -> str:
    """Enhanced response type detection with LLM fallback.

    Chain:
      1. Pattern matching (fast_match via detect_user_response_type)
      2. LLM fallback — only in active phases when #1 returns OTHER

    Returns: 'AFFIRMATIVE', 'NEGATIVE', or 'OTHER'
    """
    # Step 1: Fast pattern match
    result = detect_user_response_type(query)
    if result != 'OTHER':
        return result

    # Step 2: LLM fallback — only when in active phase
    if current_phase not in (PHASE_AWAITING_DETAIL, PHASE_FOLLOWUP_LOOP):
        return 'OTHER'

    if not fast_llm:
        return 'OTHER'

    # Truncate for minimal token usage
    bot_msg = last_bot_message[-300:] if last_bot_message else ''
    prompt = f"""Chatbot just said: "{bot_msg}"
User replied: "{query}"

Is the user's reply:
A) AFFIRMATIVE — agreeing, curious, or asking to know more about the same topic
B) NEGATIVE — declining, dismissing, or clearly not interested
C) OTHER — asking a completely different/new question or changing topic

Reply with exactly one word: AFFIRMATIVE, NEGATIVE, or OTHER"""

    try:
        response = fast_llm.invoke(prompt)
        word = (response.content if hasattr(response, 'content') else str(response)).strip().upper()
        if word in ('AFFIRMATIVE', 'NEGATIVE', 'OTHER'):
            return word
        # Handle noisy responses ("AFFIRMATIVE." or "The answer is AFFIRMATIVE")
        for token in ('AFFIRMATIVE', 'NEGATIVE', 'OTHER'):
            if token in word:
                return token
    except Exception:
        pass

    return 'OTHER'


class ContextManager:
    """
    Professional-grade context manager using LLM for intelligent analysis.
    """

    def __init__(self):
        """Initialize fast LLM for context analysis."""
        self.fast_llm = LLMFactory.create(
            purpose="classification",
            temperature=0.1
        )
    
    def analyze_message_intent(
        self,
        current_query: str,
        conversation_history: List[Dict],
        conversation_summary: Optional[str] = None
    ) -> Dict[str, Any]:
        """Classify message as CONTINUATION, NEW_TOPIC, or CLARIFICATION."""
        conv_text = self._format_conversation(conversation_history)
        
        analysis_prompt = f"""You are a conversation analyzer for an astrology chatbot.

Analyze the user's current message and determine its intent.

CONVERSATION SUMMARY (if available):
{conversation_summary or "No summary yet - this is an early conversation"}

RECENT CONVERSATION:
{conv_text or "No previous messages"}

CURRENT USER MESSAGE:
"{current_query}"

Respond in JSON format:
{{
    "intent_type": "CONTINUATION" | "NEW_TOPIC" | "CLARIFICATION",
    "confidence": 0.0-1.0,
    "reasoning": "Brief explanation",
    "referenced_topic": "Specific topic (e.g., 'career' or 'Saturn transit')",
    "requires_context": true/false
}}
"""
        try:
            response = self.fast_llm.invoke(analysis_prompt)
            result = json.loads(response.content)
            return result
        except Exception as e:
            logger.error(f"[CONTEXT] Intent analysis error: {e}")
            return {
                "intent_type": "NEW_TOPIC",
                "confidence": 0.5,
                "reasoning": "Fallback due to error",
                "referenced_topic": None,
                "requires_context": False
            }

    def resolve_contextual_query(
        self,
        current_query: str,
        conversation_history: List[Dict],
        intent_analysis: Dict
    ) -> Dict[str, Any]:
        """Resolve ambiguity and inject context into follow-up queries."""
        if not intent_analysis.get('requires_context'):
            return {
                "action": "NONE",
                "processed_query": current_query,
                "ambiguity_score": 0.0,
                "clarification_needed": False,
                "explanation": "Clear query"
            }

        # Heuristic pre-check for common follow-up patterns
        FOLLOWUP_PHRASES = ['tell me more', 'what else', 'go on', 'expand', 'explain']
        query_lower = current_query.lower()
        referenced_topic = intent_analysis.get('referenced_topic', 'the previous topic')
        
        if any(phrase in query_lower for phrase in FOLLOWUP_PHRASES) and len(query_lower.split()) < 5:
            return {
                "action": "EXPAND",
                "processed_query": f"{current_query} about {referenced_topic}",
                "ambiguity_score": 0.9,
                "clarification_needed": False,
                "explanation": "Pattern-based expansion"
            }

        # LLM-based semantic interpretation
        conv_text = self._format_conversation(conversation_history[-3:])
        resolution_prompt = f"""You are a semantic analyzer for an astrology chatbot.

Analyze the user's query relative to the conversation context.

CONTEXT: {referenced_topic}
HISTORY: {conv_text}
QUERY: "{current_query}"

Respond in JSON:
{{
    "ambiguity_score": 0.0-1.0,
    "can_resolve_safely": true/false,
    "processed_query": "The resolved query (e.g., 'Tell me more about career' instead of 'Tell me more')",
    "reasoning": "Explanation"
}}
"""
        try:
            response = self.fast_llm.invoke(resolution_prompt)
            result = json.loads(response.content)
            
            score = result.get('ambiguity_score', 0.5)
            if score > 0.6 and result.get('can_resolve_safely'):
                return {
                    "action": "EXPAND",
                    "processed_query": result.get('processed_query', current_query),
                    "ambiguity_score": score,
                    "clarification_needed": False,
                    "explanation": result.get('reasoning')
                }
            elif score > 0.3:
                return {
                    "action": "HINT",
                    "processed_query": f"Regarding {referenced_topic}: {current_query}",
                    "ambiguity_score": score,
                    "clarification_needed": False,
                    "explanation": "Medium confidence hint"
                }
            else:
                return {
                    "action": "ASK_CLARIFICATION",
                    "processed_query": current_query,
                    "ambiguity_score": score,
                    "clarification_needed": True,
                    "clarification_question": f"Could you clarify what you mean regarding {referenced_topic}?",
                    "explanation": "Low confidence"
                }
        except Exception as e:
            logger.error(f"[CONTEXT] Resolution error: {e}")
            return {"action": "NONE", "processed_query": current_query, "ambiguity_score": 0.0, "clarification_needed": False, "explanation": "Fallback"}

    def generate_conversation_summary(
        self,
        conversation_history: List[Dict],
        current_summary: Optional[str] = None
    ) -> str:
        """Create or update a concise conversation summary."""
        recent_messages = conversation_history[-6:]
        conv_text = self._format_conversation(recent_messages)
        
        prompt = f"""Summarize this astrology conversation concisely (2-3 sentences).
{f'PREVIOUS SUMMARY: {current_summary}' if current_summary else ''}
NEW MESSAGES:
{conv_text}
ONLY respond with the summary text."""
        
        try:
            response = self.fast_llm.invoke(prompt)
            return response.content.strip()
        except Exception as e:
            logger.error(f"[CONTEXT] Summary error: {e}")
            return current_summary or "Astrological discussion."

    def _format_conversation(self, conversation: List[Dict]) -> str:
        return "\n".join([f"{m.get('role', 'user').upper()}: {m.get('content', '')}" for m in conversation])

# Global instance
_context_manager = None
def get_context_manager():
    global _context_manager
    if _context_manager is None:
        _context_manager = ContextManager()
    return _context_manager

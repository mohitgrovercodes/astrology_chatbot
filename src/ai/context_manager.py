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
#   INITIAL           -> First time asking a question on this topic
#   AWAITING_DETAIL   -> Bot asked "want more details?" -- waiting for yes/no
#   FOLLOWUP_LOOP     -> Bot asked a follow-up question -- loop continues
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
    'haan', 'haa', 'ha', 'haji', 'bilkul', 'zaroor', 'aur batao', 'aur bataiye',
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

    # Short-token prefix match -- handles "ok karo", "ha bhai", "haan samjhao",
    # "no please", "nahi yaar" etc. where the affirmative/negative is the first word.
    _SHORT_AFF = ('ok ', 'ok,', 'ha ', 'ha,', 'haa ', 'haa,', 'haan ', 'hmm ', 'hmm,')
    _SHORT_NEG = ('no ', 'no,', 'nahi ', 'naa ', 'nai ')
    if any(q.startswith(p) for p in _SHORT_AFF):
        return 'AFFIRMATIVE'
    if any(q.startswith(p) for p in _SHORT_NEG):
        return 'NEGATIVE'

    return 'OTHER'


# ── Follow-up Question Domains ────────────────────────────────────────────────
# Each domain maps to follow-up questions the bot CAN reliably answer.
# These are used as LLM-prompt guidance -- the LLM picks the most relevant one
# based on what was already discussed.
# NOTE: These questions PIVOT to a different life area — they must never ask for more detail
# on the same topic just covered. The LLM uses these as the suggested pivot topic.
FOLLOWUP_QUESTION_BANK = {
    'marriage': [
        "Now that we've covered marriage timing, your career chart for this same period shows something interesting — shall I explore that?",
        "Finances often shift around the same time as major life events like marriage — would you like to see what your chart says about that period financially?",
        "Children timing is closely linked to this marriage window in your chart — shall I look at what the 5th house shows?",
        "Your health indicators for this period also deserve a look — shall I explain what to be mindful of physically during this phase?",
        "Foreign travel or relocation sometimes connects to marriage windows — your 12th house has something specific here — want me to explore?",
    ],
    'career': [
        "Your financial picture for this career period is closely connected — shall I look at what the 2nd and 11th houses show?",
        "Health and stamina directly affect professional performance — your chart has a specific indicator there — want me to cover that?",
        "Marriage or relationship timing sometimes aligns with career peaks — shall I check what your 7th house shows for this period?",
        "Foreign opportunities or relocation for career — your 12th house has something relevant here — shall I explore?",
        "Children timing, if relevant, often surfaces around career growth periods — want me to check what the 5th house says?",
    ],
    'finance': [
        "Career direction is the engine behind this financial picture — shall I explore what your 10th house shows for the same period?",
        "Your health indicators for this financial phase are worth a look — certain periods bring both financial and physical changes — shall I explain?",
        "Marriage timing and financial shifts often coincide — want me to check whether your relationship window overlaps with this period?",
        "Property or asset acquisition potential is a separate angle from income — shall I look at your 4th house for this?",
        "Foreign income or overseas financial opportunities — your 12th house has something specific — want me to explore?",
    ],
    'health': [
        "Career performance is directly tied to energy levels — your chart shows something specific for this period professionally — shall I explain?",
        "Financial pressure sometimes creates health stress — want me to check whether your financial picture eases during this phase?",
        "Marriage or relationship quality has a real impact on wellbeing — shall I look at your 7th house for this period?",
        "Children timing, if on your mind, is worth checking alongside health indicators — shall I explore the 5th house?",
        "Spiritual practices and daily routine are ruled by the 12th house — your chart shows a specific window for recovery and restoration — want me to explain?",
    ],
    'children': [
        "Career growth and children timing often coincide in charts — shall I look at what the 10th house shows for this same period?",
        "Financial readiness for this phase is worth checking — want me to see what the 2nd and 11th houses say?",
        "Your health indicators are particularly important around this period — shall I explain what to pay attention to?",
        "Marriage dynamics and children timing are deeply connected — want me to look at your 7th house for the same window?",
        "Education and learning for yourself or your child — your 5th house has more than just children timing — shall I explore?",
    ],
    'foreign': [
        "Career opportunities in that foreign destination — your 10th house has a specific connection here — shall I explore?",
        "Financial implications of foreign relocation or travel show up clearly in your chart — want me to check that?",
        "Health during foreign stays or long travel is worth knowing — shall I look at what your chart shows?",
        "Relationship or marriage timing sometimes aligns with foreign phases — want me to check the 7th house for this window?",
        "Spiritual growth and foreign connection are often linked in Vedic charts — shall I explore the deeper meaning of this placement?",
    ],
    'general': [
        "Career direction for the coming period shows something specific in your chart — shall I explore that?",
        "Financial picture for the next 1-2 years has a clear indicator in your chart — want me to walk you through it?",
        "Health and vitality trends for this phase are worth knowing — shall I explain what your chart shows?",
        "Relationship or marriage timing — if that's on your mind — is clearly indicated in your chart — want me to look at it?",
        "Children or family expansion timing, if relevant, shows up in the 5th house — shall I check?",
    ],
}

# Answerable topics per domain -- used to constrain LLM-generated follow-up questions
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
    fallback: str = "",
    timeout: float = 4.0,
    chart_context: Optional[str] = None
) -> str:
    """Generate a personalized, chart-specific follow-up question using the fast LLM.

    Uses actual planetary placements from the user's chart so questions are specific
    ("Jupiter in your 3rd house shapes your partner's nature -- what does it reveal?")
    rather than generic ("agar koi planet hai toh...").

    Falls back to `fallback` on any error or timeout -- never blocks the pipeline.
    """
    import concurrent.futures

    if not fast_llm:
        return fallback

    domain_topics = ANSWERABLE_TOPICS_BY_DOMAIN.get(topic.lower(), ANSWERABLE_TOPICS_BY_DOMAIN['general'])
    topics_list = '\n'.join(f'- {t}' for t in domain_topics)

    lang_hint = {
        'en':     'English',
        'hi':     'Hindi in Devanagari script (native script only, NOT Roman)',
        'hi-lat': 'Hinglish -- Roman-script Hindi (e.g. "Meri shadi kab hogi")',
        'ta':     'Tamil in Tamil script (native script only, NOT Roman)',
        'ta-lat': 'Tanglish -- Roman-script Tamil (e.g. "En thirumanam eppodhu")',
        'pa':     'Punjabi in Gurmukhi script (native script only, NOT Roman)',
        'pa-lat': 'Punjabi in Roman script (e.g. "Mera vivaah kaddon hoga")',
        'mr':     'Marathi in Devanagari script (native script only, NOT Roman)',
        'mr-lat': 'Marathi in Roman script',
        'te':     'Telugu in Telugu script (native script only, NOT Roman)',
        'te-lat': 'Telugu in Roman script',
        'ml':     'Malayalam in Malayalam script (native script only, NOT Roman)',
        'ml-lat': 'Malayalam in Roman script',
    }.get(language, 'match the exact language and script of the last answer')

    chart_block = f"USER'S ACTUAL CHART PLACEMENTS:\n{chart_context}" if chart_context else "No chart data available."

    prompt = f"""You are a perceptive Vedic astrologer delivering a personalised reading.

{chart_block}

Topic just discussed: {topic}
Last answer (do NOT repeat anything from here): "{last_answer[:200]}"

TASK: Write ONE follow-up line that PIVOTS to a DIFFERENT life area than '{topic}' and invites the user to explore it.

CRITICAL RULE — DO NOT OFFER MORE DETAIL ON '{topic}'. The detailed answer on that topic is now complete.
Instead, find a natural bridge to a DIFFERENT area: career, finances, health, children, marriage, foreign travel, or similar.

HOW TO BUILD IT:
  1. Choose a life area that is DIFFERENT from '{topic}' and naturally connected to the user's current life stage.
  2. Identify ONE specific planet or house placement in the chart above that is relevant to that different area.
  3. Tease what is interesting or revealing about it — without giving the answer. Close with a formal invitation.

RULES:
  - NEVER ask for more detail, a deeper breakdown, or further explanation of '{topic}'.
  - Ground the question in the actual chart data above so it feels personal, not generic.
  - YOU are offering to reveal something new. Never ask the user to explain astrology.
  - Use only real placements listed above. NEVER write "agar koi planet ho" or "if a planet is present".
  - Close with a formal, respectful invitation: "— kya aap jaanna chahenge?", "— shall I explore that?", "— want me to look at that?".
  - Language: {lang_hint}. Maximum 30 words. Return ONLY the single follow-up line.

STYLE REFERENCE (illustrate tone — use DIFFERENT topic from '{topic}', use actual chart planets/houses):
  "Aapke career mein bhi is samay ek interesting shift aa rahi hai — 10th lord ki placement mein kuch specific hai — kya aap jaanna chahenge?"
  "Financial picture for this period also shows something notable in the 2nd house — shall I explore that?"
  "Health indicators for this phase are worth knowing — Mars and Saturn have a specific angle here — want me to explain?"
  "Children timing, if that's on your mind, connects naturally to this period in your chart — shall I look at the 5th house?"
"""

    def _call() -> str:
        response = fast_llm.invoke(prompt)
        return (response.content if hasattr(response, 'content') else str(response)).strip().strip('"').strip("'")

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_call)
            q = future.result(timeout=timeout)
            if q and len(q) > 8:
                return q
    except concurrent.futures.TimeoutError:
        logger.warning("[FOLLOWUP_GEN] Timed out after %.1fs -- using static fallback", timeout)
    except Exception as e:
        logger.debug("[FOLLOWUP_GEN] Failed (%s) -- using static fallback", e)

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
      2. LLM fallback - only in active phases when #1 returns OTHER

    Returns: 'AFFIRMATIVE', 'NEGATIVE', or 'OTHER'
    """
    # Step 1: Fast pattern match
    result = detect_user_response_type(query)
    if result != 'OTHER':
        return result

    # Step 2: LLM fallback -- only when in active phase
    if current_phase not in (PHASE_AWAITING_DETAIL, PHASE_FOLLOWUP_LOOP):
        return 'OTHER'

    if not fast_llm:
        return 'OTHER'

    # Truncate for minimal token usage
    bot_msg = last_bot_message[-300:] if last_bot_message else ''
    prompt = (
        f'Chatbot just said: "{bot_msg}"\n'
        f'User replied: "{query}"\n\n'
        'Is the user reply:\n'
        'A) AFFIRMATIVE - agreeing, curious, or asking to know more about the same topic\n'
        'B) NEGATIVE - declining, dismissing, or clearly not interested\n'
        'C) OTHER - asking a completely different/new question or changing topic\n\n'
        'Reply with exactly one word: AFFIRMATIVE, NEGATIVE, or OTHER'
    )

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
        """
        Classify message as CONTINUATION, NEW_TOPIC, or CLARIFICATION and
        derive a semantic domain + question mode for downstream logic.
        """
        conv_text = self._format_conversation(conversation_history)
        
        analysis_prompt = f"""You are a conversation analyzer for an astrology chatbot.

Your job is to understand what the user is REALLY asking, not just match keywords.

CONVERSATION SUMMARY (if available):
{conversation_summary or "No summary yet - this is an early conversation"}

RECENT CONVERSATION:
{conv_text or "No previous messages"}

CURRENT USER MESSAGE:
"{current_query}"

CRITICAL DOMAIN GUIDANCE (read carefully before answering):
- The "domain" field must capture the TRUE life-area of the question, even if the user uses indirect or emotional language.
- Examples that MUST be tagged as "divorce" (NOT generic "marriage"):
  - "Meri shaadi kab tootegi?" / "Meri shaadi kab toot jayegi?"
  - "Mera rishta kab khatam hoga?" / "Relationship kab khatam hoga?"
  - "Ham alag kab honge?" / "kab separation hoga?"
  - Any phrasing where the user is clearly asking when a marriage/relationship will BREAK / END / TOOT / KHATAM.
- Examples that SHOULD stay "marriage":
  - "Meri shaadi kab hogi?" (asking about getting married)
  - "Meri shaadi kaisi rahegi?" (quality of marriage)
  - "Mere partner ke baare mein batao" (partner description without breakup focus)

- Use the broader conversation for nuance: if earlier messages were about marriage and now the user asks about it "tootna", treat this turn's domain as "divorce".

Respond in STRICT JSON format, no extra text:
{{
  "intent_type": "CONTINUATION" | "NEW_TOPIC" | "CLARIFICATION",
  "domain": "marriage" | "divorce" | "career" | "children" | "health" | "finance" | "home" | "foreign" | "general",
  "question_mode": "timing" | "qualities" | "advice" | "summary",
  "polarity": "positive" | "negative" | "mixed",
  "confidence": 0.0-1.0,
  "reasoning": "Brief explanation of how you inferred this",
  "referenced_topic": "Specific topic (e.g., 'career change', 'divorce', 'foreign travel')",
  "requires_context": true/false
}}
"""
        try:
            response = self.fast_llm.invoke(analysis_prompt)
            result = json.loads(response.content)
            # Basic robustness: fill missing keys with safe defaults
            result.setdefault("intent_type", "NEW_TOPIC")
            result.setdefault("domain", "general")
            result.setdefault("question_mode", "summary")
            result.setdefault("polarity", "mixed")
            result.setdefault("confidence", 0.5)
            result.setdefault("reasoning", "")
            result.setdefault("referenced_topic", None)
            result.setdefault("requires_context", False)

            # HARD OVERRIDE FOR DIVORCE / SEPARATION QUERIES
            # If the literal question talks about divorce/separation, always treat the
            # semantic domain as 'divorce' and handle it as a fresh topic. This avoids
            # misclassifying it as a generic 'marriage' continuation.
            _q_lower = (current_query or "").lower()
            _divorce_keywords = [
                "divorce",
                "separation",
                "separate",
                "alag hona",
                "talaq",
                "breakup",
                "break-up",
                "judicial separation",
                "relationship end",
                "marriage end",
                # Common Hindi/Hinglish breakup phrasings
                "shaadi tootegi",
                "shaadi toot jayegi",
                "shaadi tootega",
                "shaadi toot jayega",
                "shaadi khatam",
                "rishta tootega",
                "rishta toot jayega",
                "rishta khatam",
                "relationship khatam",
            ]
            if any(k in _q_lower for k in _divorce_keywords):
                result["domain"] = "divorce"
                # Treat as a new semantic topic even if it follows a marriage answer
                result["intent_type"] = "NEW_TOPIC"
                result["referenced_topic"] = "divorce or separation"

            return result
        except Exception as e:
            logger.error(f"[CONTEXT] Intent analysis error: {e}")
            return {
                "intent_type": "NEW_TOPIC",
                "domain": "general",
                "question_mode": "summary",
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

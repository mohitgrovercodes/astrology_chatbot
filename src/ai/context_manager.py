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

    # Short-token prefix match -- handles "ok karo", "ha bhai", "haan samjhao",
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
# These are used as LLM-prompt guidance -- the LLM picks the most relevant one
# based on what was already discussed.
FOLLOWUP_QUESTION_BANK = {
    'marriage': [
        "7th lord ki placement mein ek twist hai jo future partner ki personality ke baare mein kuch unexpected reveal karta hai -- woh angle abhi cover nahi hua.",
        "Venus aapke chart mein jahan hai, woh prem aur attraction ke baare mein kuch specific kehta hai jo bahut log notice hi nahi karte.",
        "Navamsa (D9) chart ko shadi ka asli aaina kaha jaata hai -- aur aapke D9 mein kuch aisa hai jo birth chart se bilkul alag picture banata hai.",
        "Aapke Dasha timeline mein ek period hai jo shadi ke liye unusually powerful hai -- aur woh woh nahi hai jo obvious lagta hai.",
        "Jo planetary period aapki shadi ka darwaza khol raha hai, wahi period ek doosri zindagi-badalne wali cheez bhi leke aa raha hai.",
    ],
    'career': [
        "10th lord ki placement ek specific career direction clearly point karti hai -- aur woh field usually woh nahi hoti jo log pehle sochte hain.",
        "11th house mein ek indicator hai jo bata sakta hai ki aap job se zyada earn karenge ya business se -- aur answer genuinely surprising ho sakta hai.",
        "Saturn aapke chart mein career ke baare mein ek unusual message de raha hai -- delay ki nahi, ek specific breakthrough window ki baat hai.",
        "Aapke Dasha mein ek window hai jab career ek sharp leap leta hai -- woh period khulne wala hai, aur yeh jaanna preparation ke liye zaroori hai.",
        "Lagnesh ki placement professional drive ke baare mein ek hidden indicator hai -- jo aapko actually aage push karta hai woh chart mein clearly visible hai.",
    ],
    'finance': [
        "2nd aur 11th houses ka jo combination aapke chart mein hai, woh income ke baare mein ek specific aur somewhat surprising picture banata hai.",
        "Ek planetary period aapke aage aa raha hai jo financial gains ke liye unusually powerful hai -- aur woh woh nahi jo surface pe obvious dikhta hai.",
        "Aapke chart mein ek clear indicator hai ki aap job, business, ya investments -- kin mein se kisme naturally zyada success milegi.",
        "Jupiter aur Venus dono wealth ke karak hain -- aur aapke chart mein inki placement mein ek interesting tension hai jo money ke saath relationship ko shape karta hai.",
    ],
    'health': [
        "6th house lord ki placement ek specific area point karti hai jahan dhyan rakhna genuinely helpful hoga -- aur woh woh area nahi hoga jo aap expect karein.",
        "Ek Dasha period hai jab health extra attention maangta hai -- yeh jaanna advance mein genuinely practical hai.",
        "Lagna lord ki placement constitution aur natural vitality ke baare mein ek interesting picture banata hai -- strength aur weakness dono clearly visible hain wahan.",
        "Mars aur Saturn ka jo angle aapke chart mein hai, woh physical stamina ke baare mein ek specific aur somewhat unexpected story batata hai.",
    ],
    'children': [
        "5th house lord ki placement children ki timing ke baare mein ek clear signal deta hai -- aur kuch aur bhi hai wahan jo intelligence aur creativity ke baare mein interesting hai.",
        "Jupiter aapke chart mein jahan hai, woh children ke baare mein ek picture banata hai jo birth chart se zyada D5 mein clearly dikhta hai.",
        "5th house sirf bachcho ka ghar nahi -- past-life merit aur natural gifts ka bhi hai, aur aapke chart mein ek specific strength wahan chhupi hui hai.",
    ],
    'foreign': [
        "Rahu ki placement foreign connection ke baare mein ek clear hint deta hai -- aur jo indicate karta hai woh career se personal life tak ek specific angle hai.",
        "9th aur 12th houses ka combination bata sakta hai ki foreign travel ya settlement ka waqt aur direction kya hoga -- aapke chart mein kuch specific hai.",
        "Foreign opportunities aapke Dasha timeline mein ek particular period ke around cluster karti hain -- kaunsa period hai aur kya type ki opportunity?",
    ],
    'general': [
        "Aapke Dasha mein agla major phase shift ek interesting mix leke aata hai -- kuch challenges, kuch unexpected openings. Kya dikhta hai aage?",
        "Aapke chart mein 2-3 planetary positions hain jo real natural advantages dete hain -- woh strengths hain jo shayad aap abhi fully use nahi kar rahe.",
        "Ek significant transit abhi chal raha hai jo silently current circumstances shape kar raha hai -- aur exactly kab tak chalega yeh jaanna helpful hai.",
        "Lagna lord ki exact placement personality aur life direction ke baare mein jo picture banata hai, woh usually jo log expect karte hain usse alag hota hai.",
        "Sade Sati ka aapke chart par ek measurable asar hai -- exactly kab peak hai aur kab lift hota hai, yeh practically jaanna zaroori hai.",
        "Har chart mein ek dominant planet hota hai jo puri zindagi ko color karta hai -- aapka woh signature planet kaunsa hai?",
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

    prompt = f"""You are a sharp, insightful Vedic astrologer who notices things others miss.

{chart_block}

Topic just discussed: {topic}
Last answer (do NOT repeat anything from here): "{last_answer[:200]}"

TASK: Write ONE follow-up question this specific user will want to answer immediately.

HOW TO BUILD IT (think in steps):
  1. Pick the single most interesting chart placement above that relates to {topic} and was NOT covered in the last answer.
  2. Identify what is surprising, ironic, or revealing about it -- something the user does not know yet.
  3. Name the actual planet and house. Tease the insight. End with a hook.

NON-NEGOTIABLE RULES:
  - Use a real placement from the chart above. NEVER say "agar koi planet ho" or "if a planet is present".
  - Do NOT ask permission: no "kya aap jaanna chahenge", no "would you like to know".
  - Tease, do not tell. The question should make the user feel: "I did not know that -- tell me."
  - Language: {lang_hint}. Max 20 words. Return ONLY the question.

EXAMPLES of the exact quality and style to match (adapt planet/house to the actual chart):
  "Venus 1st house mein debilitate hone ke bawajood ek hidden strength carry karti hai -- zyada tar log yeh miss karte hain."
  "Jupiter 3rd house mein aapka 7th lord hai -- yeh ek unusual spot hai jo future partner ki personality ke baare mein kuch specific aur unexpected batata hai."
  "Aapka 10th lord Mercury exalted aur 1st house mein -- yeh rare placement success ke tarike ke baare mein ek surprising picture banata hai."
  "Moon aur Saturn jo combination aapke chart mein bana rahe hain, woh career timing ke baare mein ek window dikhaata hai jo bahut kam log jaante hain."
  "Rahu ki placement aapki financial growth se ek aisa angle se connected hai jo surface pe nahi dikhta."
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

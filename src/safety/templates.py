# src/safety/templates.py
# src\safety\templates.py
"""
Response Templates for Safety Handling

Pre-defined response templates for blocked queries, disclaimers, and reframed responses.
"""

from typing import Dict


# ============================================================================
# HARD BLOCK TEMPLATES (Never Answer)
# ============================================================================

HARD_BLOCK_DEATH = """I understand you're seeking clarity about life events, but I cannot provide predictions about specific timing of death or mortality. Such predictions can cause significant psychological distress and are ethically inappropriate.

Astrology can offer insights into life phases, health tendencies, and personal growth—but not fixed outcomes about death.

If you're experiencing anxiety about mortality or loss, I encourage you to speak with a counselor or trusted person. I'm here to help with other astrological questions about life patterns, growth periods, or understanding your chart."""

HARD_BLOCK_MEDICAL = """I cannot provide medical diagnoses or treatment advice based on astrological charts. While astrology may indicate health *tendencies* (like a predisposition to certain imbalances), it is not a substitute for medical evaluation.

**Please consult a qualified healthcare provider for any health concerns.**

I can discuss general health-related astrological factors (like 6th house placements or Saturn's influence) in educational terms, but not as medical guidance."""

HARD_BLOCK_GAMBLING = """I don't provide specific gambling or lottery predictions. Astrology is not meant for fortune-telling in this way, and such advice could contribute to harmful gambling behavior.

Astrology works better for understanding life patterns, personal growth, and decision-making frameworks—not for predicting random outcomes like lottery numbers or betting results.

I'm happy to help with other astrological questions about timing, life phases, or chart interpretation."""

HARD_BLOCK_LEGAL = """I cannot provide predictions about legal case outcomes or legal advice. Such matters require professional legal counsel, not astrological interpretation.

While astrology can discuss general themes around justice, contracts, and negotiations (like 7th house matters or Mercury periods), it should never be used as a basis for legal decisions.

**Please consult a qualified attorney for legal matters.**

I'm here to help with other astrological questions about your chart or life patterns."""

HARD_BLOCK_HARM = """I cannot and will not provide guidance that could lead to harm.

If you're experiencing thoughts of self-harm or harming others, please reach out immediately to:
- **National Suicide Prevention Lifeline**: 988 (US)
- **Crisis Text Line**: Text HOME to 741741
- **International Association for Suicide Prevention**: https://www.iasp.info/resources/Crisis_Centres/

Astrology is a tool for self-understanding and growth, not for harmful actions. I'm here to help with constructive astrological questions when you're ready."""

HARD_BLOCK_UNDERAGE = """I cannot provide astrological guidance for making decisions about minors without appropriate parental consent and context.

Questions involving children's futures, marriages, or major life decisions require careful consideration by parents, guardians, and appropriate professionals—not astrological predictions.

If you're a parent seeking general guidance about supporting your child's development, I can discuss that in educational terms. Otherwise, I'm here to help with questions about your own chart."""

HARD_BLOCK_VULGAR = """I'm here to provide professional Vedic astrology guidance and I'm not able to respond to messages that contain vulgar, explicit, or sexually inappropriate content.

Please keep our conversation respectful so I can continue helping you with meaningful astrological insights about your chart, life patterns, and timing."""


# ============================================================================
# SOFT BLOCK TEMPLATES (Decline Politely)
# ============================================================================

SOFT_BLOCK_FORTUNE = """I understand you're looking for clarity about the future. However, astrology doesn't work as fixed fortune-telling—it shows *tendencies*, *potentials*, and *timing of opportunities*, but not predetermined outcomes.

Your chart reveals periods when certain energies are stronger, but your choices, circumstances, and free will play crucial roles in how things unfold.

Instead of "What will happen?", we can explore:
- "What energies are active in my chart now?"
- "What are favorable periods for [specific goal]?"
- "What patterns should I be aware of?"

Would you like to reframe your question in one of these ways?"""

SOFT_BLOCK_PRIVACY = """I can only provide astrological insights about your own chart or about others if:
1. You have their explicit consent, AND
2. You have their accurate birth details

Analyzing someone else's chart without consent raises privacy and ethical concerns.

If you're interested in relationship compatibility or understanding dynamics with others, I can:
- Discuss general astrological principles of compatibility
- Analyze these dynamics from *your* chart perspective (e.g., your 7th house)
- Explain what to look for in synastry (if you later get consent)

Would any of these approaches be helpful?"""

SOFT_BLOCK_OUT_OF_SCOPE = """This question goes beyond the scope of astrological practice. Astrology focuses on:
- Planetary influences and timing
- Birth chart interpretation
- Personal growth patterns
- Relationship dynamics
- Career and life purpose insights

For questions about topics other than the above, you would need to consult specialists in that field.

I'm here to help with astrological questions about your chart, planetary periods, or how to understand astrological concepts. What would you like to explore?"""

SOFT_BLOCK_CONSPIRACY = """I focus on traditional astrological principles based on planetary movements, houses, and signs. The topic you're asking about falls outside the scope of mainstream astrological practice.

I'm happy to discuss:
- Planetary transits and their influences
- Birth chart interpretation
- Dashas and timing techniques
- Astrological symbolism and mythology

Is there a specific astrological concept you'd like to explore instead?"""

SOFT_BLOCK_THIRD_PARTY_HARM = """I cannot provide astrological analysis that might be used to judge, manipulate, or make decisions about others without their knowledge and consent.

Astrology is best used for:
- Self-understanding and growth
- Making informed decisions about your own life
- Understanding relationship dynamics from your perspective

If you're experiencing difficulties in a relationship, I can help you understand your own chart's patterns and what you might work on personally. Would that be helpful?"""

SOFT_BLOCK_THIRD_PARTY_PREDICTION = """I appreciate your concern, but I can only provide astrological readings that stay centered on you and your own chart.

**Why I cannot give direct predictions for others:**
- Meaningful astrological analysis needs accurate birth details (date, time, place)
- Making specific predictions about someone else without their consent raises ethical concerns
- Astrology is healthiest when it is used for self-understanding, personal growth, and better choices in your own life

**What I can help you with instead:**
- Look at YOUR chart to understand how you tend to handle crisis, risk, or stressful phases (including accidents / health / travel sensitivity)
- Highlight periods in YOUR life where it may be wise to be extra mindful and careful
- Explain general astrological principles related to your question (for example, how Mars, Saturn, the 8th house and certain dashas can symbolically relate to accidents or sudden events)

If you’d like, we can explore your own chart to see how you can navigate such situations with more awareness and safety in your life.

Is there something about YOUR chart I can help you with instead?"""

SOFT_BLOCK_SABOTAGE_CRITICISM = """I understand that astrology might not always resonate, or sometimes a prediction may feel misaligned with your current experience. Astrology provides a map of probabilities and energies, but life is complex, and your free will is the ultimate deciding factor.

If you feel I've made an error in interpreting your chart, I appreciate your feedback! My goal is to help you explore your chart constructively. 

We can always look at a different aspect of your chart, or if you prefer to end the session here, that is completely fine as well. How would you like to proceed?"""


# ============================================================================
# CONDITIONAL DISCLAIMERS (Answer with Warning)
# ============================================================================

DISCLAIMER_HEALTH = """

[HEALTH] **Important Disclaimer**: The astrological insights I provide are for educational and self-reflection purposes only. Astrology indicates *tendencies* and *areas of focus*, not medical diagnoses. Always consult qualified healthcare providers for health concerns, diagnoses, or treatment decisions."""

DISCLAIMER_FINANCIAL = """

[FINANCIAL] **Important Disclaimer**: Astrological insights about finances and career are for guidance and timing awareness only. They should not be your sole basis for major financial decisions. Always consult financial advisors and make practical assessments before significant investments or career changes."""

DISCLAIMER_RELATIONSHIP = """

[RELATIONSHIP] **Important Reminder**: Astrological compatibility is one factor among many in relationships. Real-world communication, shared values, mutual respect, and effort are far more important than chart compatibility. Use these insights as a tool for understanding, not as a relationship verdict."""

DISCLAIMER_CHILDREN = """

[CHILDREN] **Important Note**: Questions about children and fertility are deeply personal. While astrology can indicate favorable periods, it cannot predict specific outcomes. Medical consultation is essential for fertility and family planning decisions. These astrological insights are for timing awareness only."""

DISCLAIMER_CAREER = """

[CAREER] **Important Reminder**: Career decisions should be based on practical factors—skills, market conditions, financial stability, and personal circumstances. Astrological timing is one input among many. Use this guidance to inform your decision-making, not replace it."""

DISCLAIMER_GENERAL = """

[ASTROLOGY] **Important Reminder**: Astrological insights are for self-reflection and timing awareness. They show tendencies and potentials, not fixed destinies. Your free will, choices, and circumstances all play crucial roles in shaping outcomes."""


# ============================================================================
# REFRAME TEMPLATES
# ============================================================================

REFRAME_INTRO = """"""

REFRAME_SUGGESTIONS = {
    "wealth": {
        "original_pattern": r"will I (get|become) (rich|wealthy)",
        "reframed": "What periods in my chart support wealth accumulation and financial growth?"
    },
    "marriage": {
        "original_pattern": r"will I (get married|find love)",
        "reframed": "What does my 7th house reveal about relationship timing and partnership potential?"
    },
    "success": {
        "original_pattern": r"will I be successful",
        "reframed": "What are my chart's indicators for career achievement and when are favorable periods?"
    },
    "fame": {
        "original_pattern": r"will I be famous",
        "reframed": "What does my chart say about public recognition and visibility potential?"
    },
    "punishment": {
        "original_pattern": r"why is (god|universe) punishing me",
        "reframed": "What challenging planetary periods am I experiencing, and what growth opportunities do they offer?"
    },
    "job": {
        "original_pattern": r"will I get (the|a|this) job",
        "reframed": "What does my current planetary period indicate about career opportunities?"
    }
}

# ============================================================================
# REFRAME — Semantic LLM-based reframing (replaces hardcoded regex patterns)
# ============================================================================

# Legacy patterns kept ONLY as final fallback examples for the LLM prompt;
# actual reframing is now done by the LLM (see get_semantic_reframe below).
_REFRAME_EXAMPLES = [
    ("Will I get rich?",
     "What periods in my chart support wealth accumulation and financial growth?"),
    ("Will I get married?",
     "What does my 7th house reveal about relationship timing and partnership potential?"),
    ("Will I be successful?",
     "What are my chart's indicators for career achievement and when are the favorable periods?"),
    ("Why is God punishing me?",
     "What challenging planetary periods am I in, and how can I grow through them?"),
    ("Will I get the job?",
     "What does my current planetary period indicate about career opportunities?"),
]


def get_semantic_reframe(query: str, llm=None, language: str = "en") -> str:
    """
    Reframe a fatalistic or fortune-telling query into an empowering,
    guidance-oriented question using the LLM.

    Works in any language — if the user asked in Hindi, the LLM reframes in Hindi.
    Falls back to a graceful generic reframe when no LLM is available.

    Args:
        query:    The original user query (any language)
        llm:      A LangChain-compatible LLM instance, or None
        language: ISO language code (e.g. 'en', 'hi', 'hi-lat', 'ta')

    Returns:
        A reframed question string that redirects the user constructively
    """
    if llm is None:
        # LLM unavailable — return a sensible generic
        return (
            "What astrological patterns and planetary periods are active in my chart "
            "that are relevant to this area of my life, and how can I navigate them wisely?"
        )

    examples_block = "\n".join(
        f'  Original: "{orig}"\n  Reframed: "{ref}"'
        for orig, ref in _REFRAME_EXAMPLES
    )

    prompt = (
        f"You are a professional Vedic astrologer who reframes fortune-telling questions "
        f"into empowering, guidance-oriented questions.\n\n"
        f"EXAMPLES:\n{examples_block}\n\n"
        f"TASK: Reframe the following query into an empowering question that:\n"
        f"1. Focuses on understanding patterns and opportunities (not fixed outcomes)\n"
        f"2. Is answerable with astrological analysis\n"
        f"3. Uses the SAME LANGUAGE as the original query\n"
        f"4. Preserves the user's core interest\n\n"
        f'Original query: "{query}"\n\n'
        f"Reframed question (ONLY output the reframed question, nothing else):"
    )
    try:
        response = llm.invoke(prompt)
        reframed = (response.content if hasattr(response, 'content') else str(response)).strip()
        # Sanity check — must be shorter than a paragraph
        if reframed and len(reframed) < 300:
            return reframed
    except Exception:
        pass

    # Fallback
    return (
        "What astrological patterns and planetary periods are active in my chart "
        "that are relevant to this area of my life, and how can I navigate them wisely?"
    )


# ============================================================================
# EMPATHY TEMPLATES (For Difficult Topics)
# ============================================================================
EMPATHY_LOSS = """I can sense you're going through a difficult time with loss or grief. While I cannot predict specific timing or outcomes around such sensitive matters, I can offer some astrological perspective on navigating challenging periods.

If you're open to it, we could explore:
- Current planetary transits and how they might relate to emotional processing
- Supportive periods for healing and reflection
- Your chart's indicators for emotional resilience

Would any of these be helpful? And please remember, speaking with a counselor or trusted friend is invaluable during times of grief."""

EMPATHY_HEALTH_ANXIETY = """I understand health concerns can be very stressful. While I can discuss astrological indicators related to vitality and wellness, I want to emphasize that astrology is not a diagnostic tool.

If you're experiencing health anxiety or specific symptoms, please consult healthcare professionals.

If you'd like, I can share general astrological insights about:
- Vitality indicators in your chart
- Periods that favor self-care and wellness
- Mind-body balance from an astrological perspective

Would that be helpful?"""

EMPATHY_RELATIONSHIP_DISTRESS = """It sounds like you're going through a challenging time in your relationship. Relationship difficulties are complex and involve many factors beyond astrology.

While I can offer astrological perspective on compatibility and timing, real-world factors—communication, mutual respect, shared values, and effort—are far more important.

I can help with:
- Understanding relationship patterns in your chart
- Current transits affecting partnerships
- Timing for important conversations or decisions

Would you like to explore any of these? And consider reaching out to a relationship counselor if you're struggling—they can offer direct, personalized support."""


# ============================================================================
# GREETING TEMPLATES
# Note: First-time greeting is handled by the mobile application.
# These pools are used for all in-session greetings.
# ============================================================================

# English — varied, warm, short
GREETING_RETURNING = [
    "Hey {user_name}! What's on your mind?",
    "Namaste, {user_name} — I'm here. What would you like to explore?",
    "Good to hear from you, {user_name}. What's your question?",
    "Yes, {user_name}! What can I look into for you?",
    "I'm listening — what would you like to know?",
    "Always here, {user_name}. Ask away!",
    "The stars are aligned — what's your question, {user_name}?",
    "Hi again! What would you like to explore today?",
]

# Hindi (Native Script) - natural, conversational
GREETING_HINDI_RETURNING = [
    "Namaste, {user_name}! Bataiye, kya jaanna chahenge?",
    "Han {user_name}, main yahan hoon. Kya poochhna hai?",
    "Ji {user_name}, boliye!",
    "Kya jaanna chahte hain aap?",
    "Bataiye - main sun raha hoon.",
    "Aapke liye kya dekh sakta hoon?",
]

# Hinglish (Romanized Hindi) — for hi-lat language code
GREETING_HINGLISH_RETURNING = [
    "Namaste {user_name}! Kya jaanna chahte hain?",
    "Haan {user_name}, batao — kya sawaal hai?",
    "Main yahan hoon. Kya poochhna hai?",
    "Bolo {user_name}, kya dekhein aapke liye?",
    "Suno raha hoon — kya jaanna hai?",
]

# Tamil (Romanized) — for ta-lat language code
GREETING_TAMIL_RETURNING = [
    "Vanakkam {user_name}! Enna theriyanum?",
    "Sollunga {user_name} — enna kekka virumbareengal?",
    "Inge irukken — enna kekka poreenga?",
    "Jolly ah kettunga {user_name}!",
]

# Punjabi (Gurmukhi) - for pa
GREETING_PUNJABI_RETURNING = [
    "ਸਤਿ ਸ੍ਰੀ ਅਕਾਲ {user_name}! ਮੈਂ ਤੁਹਾਡੀ ਕੀ ਮਦਦ ਕਰ ਸਕਦਾ ਹਾਂ?",
    "ਹਾਂਜੀ {user_name}, ਦੱਸੋ ਕੀ ਪੁੱਛਣਾ ਚਾਹੁੰਦੇ ਹੋ?",
    "ਜੀ {user_name}, ਦੱਸੋ!",
    "ਤੁਹਾਡਾ ਕੀ ਸਵਾਲ ਹੈ?",
]

# Punjabi (Romanized) - for pa-lat
GREETING_PUNJABI_LAT_RETURNING = [
    "Sat Sri Akal {user_name}! Main tuhadi ki madad kar sakda haan?",
    "Haanji {user_name}, dasso ki puchhanna chaunde ho?",
    "Ji {user_name}, dasso!",
    "Tuhada ki sawal hai?",
]


# ============================================================================
# CONVERSATIONAL TONE GUIDELINES (For System Prompts)
# ============================================================================

CONVERSATIONAL_TONE_SYSTEM_PROMPT = """
TONE & LANGUAGE GUIDELINES:

1. **Use Natural Language:**
   - Write like you're having a friendly conversation
   - Use "you", "your", active voice
   - Avoid overly formal or academic language

2. **Balance Sanskrit Terms:**
   - Use English names FIRST: "Mars (Mangal)" not "Mangal (Mars)"
   - Only use Sanskrit when it adds clarity or tradition
   - Maximum 2-3 Sanskrit terms per paragraph

3. **Simplify Technical Concepts:**
   [FAIL] "The 10th Bhava lord positioned in the 4th Bhava"
   [OK] "Your career planet is in your home sector"
   
   [FAIL] "Shani in Kumbha in the 6th Bhava"
   [OK] "Saturn in Aquarius in your 6th house (daily work)"
   
   [FAIL] "Chandra in Mithuna indicates"
   [OK] "Your Moon in Gemini shows"

4. **Explain, Don't Just State:**
   [FAIL] "Jupiter aspects your 7th house"
   [OK] "Jupiter sends its beneficial energy to your relationship sector, supporting harmonious partnerships"

5. **Use Parentheticals for Sanskrit:**
   [OK] "Your Moon (Chandra) in Gemini..."
   [OK] "The 7th house (marriage sector)..."
   [OK] "During Saturn's period (Shani dasha)..."

6. **Conversational Connectors:**
   Use: "This means...", "In other words...", "Think of it like...", "Here's what this means for you..."
   Avoid: "Thus", "Therefore", "Hence", "Thereby"

7. **For Timing Questions:**
   ALWAYS provide specific months/timeframes:
   [OK] "March-April 2026 when Jupiter transits..."
   [FAIL] "During your Saturn Mahadasha" (too vague)

EXAMPLE TRANSFORMATION:

[FAIL] BAD: "Your Chandra positioned in Mithuna Rashi in the 10th Bhava indicates communicative faculties in professional endeavors."

[OK] GOOD: "Your Moon in Gemini (your career house) shows you're naturally great at communication and adapting to change at work. This placement often means you thrive in dynamic environments where you can use your quick thinking."
"""


# ============================================================================
# ALTERNATIVE SUGGESTIONS (When Declining)
# ============================================================================

ALTERNATIVE_SUGGESTIONS = """

**What I can help you with instead:**
- Birth chart interpretation and planetary placements
- Current dashas and transit influences
- Timing for specific activities (travel, business start, etc.)
- Understanding astrological concepts and principles
- Compatibility analysis (with consent and birth details)
- Career and life purpose indicators in your chart

What aspect of astrology interests you most?"""


# ============================================================================
# Template Dictionary (for easy lookup)
# ============================================================================

RESPONSE_TEMPLATES: Dict[str, str] = {
    # Hard Blocks
    "HARD_BLOCK_DEATH": HARD_BLOCK_DEATH,
    "HARD_BLOCK_DEATH_PREDICTION": HARD_BLOCK_DEATH,
    "HARD_BLOCK_MEDICAL": HARD_BLOCK_MEDICAL,
    "HARD_BLOCK_MEDICAL_DIAGNOSIS": HARD_BLOCK_MEDICAL,
    "HARD_BLOCK_GAMBLING": HARD_BLOCK_GAMBLING,
    "HARD_BLOCK_GAMBLING_SPECIFIC": HARD_BLOCK_GAMBLING,
    "HARD_BLOCK_LEGAL": HARD_BLOCK_LEGAL,
    "HARD_BLOCK_LEGAL_ADVICE": HARD_BLOCK_LEGAL,
    "HARD_BLOCK_HARM": HARD_BLOCK_HARM,
    "HARD_BLOCK_HARMFUL_INTENT": HARD_BLOCK_HARM,
    "HARD_BLOCK_UNDERAGE": HARD_BLOCK_UNDERAGE,
    "HARD_BLOCK_VULGAR_CONTENT": HARD_BLOCK_VULGAR,
    "HARD_BLOCK_VULGAR": HARD_BLOCK_VULGAR,
    
    # Soft Blocks
    "SOFT_BLOCK_FORTUNE": SOFT_BLOCK_FORTUNE,
    "SOFT_BLOCK_FORTUNE_TELLING": SOFT_BLOCK_FORTUNE,
    "SOFT_BLOCK_PRIVACY": SOFT_BLOCK_PRIVACY,
    "SOFT_BLOCK_PRIVACY_VIOLATION": SOFT_BLOCK_PRIVACY,
    "SOFT_BLOCK_OUT_OF_SCOPE": SOFT_BLOCK_OUT_OF_SCOPE,
    "SOFT_BLOCK_CONSPIRACY": SOFT_BLOCK_CONSPIRACY,
    "SOFT_BLOCK_CONSPIRACY_THEORY": SOFT_BLOCK_CONSPIRACY,
    "SOFT_BLOCK_THIRD_PARTY_HARM": SOFT_BLOCK_THIRD_PARTY_HARM,
    "SOFT_BLOCK_THIRD_PARTY_PREDICTION": SOFT_BLOCK_THIRD_PARTY_PREDICTION,
    "SOFT_BLOCK_THIRD_PARTY": SOFT_BLOCK_THIRD_PARTY_PREDICTION,
    
    # Greetings (first-time greeting is owned by mobile app)
    
    # System Prompts
    "CONVERSATIONAL_TONE_SYSTEM_PROMPT": CONVERSATIONAL_TONE_SYSTEM_PROMPT,
    
    # Disclaimers
    "DISCLAIMER_HEALTH": DISCLAIMER_HEALTH,
    "DISCLAIMER_FINANCIAL": DISCLAIMER_FINANCIAL,
    "DISCLAIMER_RELATIONSHIP": DISCLAIMER_RELATIONSHIP,
    "DISCLAIMER_CHILDREN": DISCLAIMER_CHILDREN,
    "DISCLAIMER_CAREER": DISCLAIMER_CAREER,
    "DISCLAIMER_GENERAL": DISCLAIMER_GENERAL,
    
    # Reframe
    "REFRAME_INTRO": REFRAME_INTRO,
    
    # Empathy
    "EMPATHY_LOSS": EMPATHY_LOSS,
    "EMPATHY_HEALTH_ANXIETY": EMPATHY_HEALTH_ANXIETY,
    "EMPATHY_RELATIONSHIP_DISTRESS": EMPATHY_RELATIONSHIP_DISTRESS,
    
    # Alternatives
    "ALTERNATIVE_SUGGESTIONS": ALTERNATIVE_SUGGESTIONS,
}


def get_template(template_key: str, **kwargs) -> str:
    """
    Get response template by key and format with provided arguments.
    
    Args:
        template_key: Key for the template (e.g., 'HARD_BLOCK_DEATH')
        **kwargs: Formatting arguments (e.g., topic="conspiracy theories")
    
    Returns:
        Formatted template string
    
    Example:
        >>> get_template("HARD_BLOCK_DEATH")
        "I understand you're seeking clarity..."
        
        >>> get_template("REFRAME_INTRO", 
        ...              original="Will I get rich?",
        ...              reframed="What periods support wealth?")
        "Let me reframe that question..."
    """
    template = RESPONSE_TEMPLATES.get(template_key)
    
    if template is None:
        # Fallback generic message
        return (
            "I cannot provide guidance on this specific query due to safety, "
            "ethical, or scope limitations. I'm here to help with astrological "
            "questions about your birth chart, planetary periods, and life patterns. "
            "What else would you like to explore?"
        )
    
    try:
        return template.format(**kwargs)
    except KeyError:
        # If formatting fails, return unformatted template
        return template


def get_disclaimer(disclaimer_type: str, language: str = 'en', llm=None) -> str:
    """
    Get disclaimer text by type and optionally translate it.
    
    Args:
        disclaimer_type: Type of disclaimer ('HEALTH', 'FINANCIAL', etc.)
        language: ISO language code to translate into
        llm: Optional Langchain LLM object for translation
    
    Returns:
        Disclaimer text string
    """
    key = f"DISCLAIMER_{disclaimer_type.upper()}"
    text = get_template(key)

    if language != 'en' and llm is not None:
        try:
            from src.utils.localization import get_localization_manager
            lang_name = get_localization_manager().get_language_name(language)
            
            script_instruction = ""
            if '-lat' in language:
                script_instruction = f" Respond in {lang_name} using ROMAN ALPHABET only (no native script)."
            else:
                script_instruction = f" Respond entirely in {lang_name} (native script)."
                
            prompt = (
                f"You are a professional Vedic astrologer translating a disclaimer. "
                f"Translate the following disclaimer accurately.{script_instruction}\n\n"
                f"Disclaimer:\n{text}\n\n"
                f"Translation (ONLY output the exact translated message without quotes):"
            )
            resp = llm.invoke(prompt)
            translated = (resp.content if hasattr(resp, 'content') else str(resp)).strip()
            if translated and len(translated) > 10:
                return translated
        except Exception as e:
            print(f"[DISCLAIMER_TRANSLATION_ERROR] {e}")
            pass

    return text


def format_reframe_response(original_query: str, reframed_query: str) -> str:
    """
    Format a reframe introduction message.
    
    Args:
        original_query: Original user query
        reframed_query: Reframed version of the query
    
    Returns:
        Formatted reframe intro text
    """
    return get_template(
        "REFRAME_INTRO",
        original=original_query,
        reframed=reframed_query
    )


# ============================================================================
# Default Fallback Messages
# ============================================================================

DEFAULT_BLOCK_MESSAGE = """I cannot provide guidance on this query due to safety or ethical concerns.

I'm here to help with astrological questions about:
- Birth chart interpretation
- Planetary periods and transits
- Compatibility and relationships (with consent)
- Career and life purpose indicators
- Understanding astrological concepts

What would you like to explore?"""

DEFAULT_ERROR_MESSAGE = """I encountered an issue processing your request. This might be due to safety checks or technical limitations.

Please try:
- Rephrasing your question
- Asking about specific astrological concepts
- Focusing on your own chart rather than predicting specific outcomes

I'm here to help with astrological guidance and chart interpretation. What would you like to know?"""


# ============================================================================
# Helper Functions for Context-Aware Responses
# ============================================================================

# ============================================================================
# CHITCHAT RESPONSE POOLS
# Varied replies for common social signals so the bot never sounds scripted.
# ============================================================================

CHITCHAT_RESPONSES = {
    # User says thanks / expresses gratitude
    "thanks": [
        "You're very welcome, {user_name}!",
        "Glad I could help! Anything else on your mind?",
        "Happy to assist — the stars are always talking.",
        "Anytime, {user_name}! Just ask.",
        "Of course! Let me know if you'd like to explore anything else.",
    ],
    "thanks_hi": [
        "Koi baat nahi, {user_name}!",
        "Khushi hui! Aur kuch jaanna hai?",
        "Bilkul! Koi aur sawaal ho toh poochhein.",
        "Shukriya {user_name} — aur kuch hoga toh zaroor bataein.",
    ],

    # User says goodbye
    "bye": [
        "Take care, {user_name}! The planets will guide you.",
        "Goodbye! Come back whenever the stars call.",
        "See you soon, {user_name}! Wishing you clear skies.",
        "Until next time, {user_name}. Namaste!",
        "Farewell — may Jupiter bless your path!",
    ],
    "bye_hi": [
        "Alvida, {user_name}! Shubhkaamnaen.",
        "Namaste {user_name} — phir milenge!",
        "Take care! Grahon ki kripa bani rahe.",
        "Dhanyawad! Jab bhi zaroorat ho, yahan hoon.",
    ],

    # User asks how the bot is doing
    "how_are_you": [
        "I'm doing well, tuned in to the cosmic frequencies! How can I help?",
        "Energized and ready — the planets are active today! What's on your mind?",
        "All good on this end! What would you like to explore?",
        "Ready and listening, {user_name}. How can I assist?",
    ],
    "how_are_you_hi": [
        "Main theek hoon, shukriya! Aap ke liye kya kar sakta hoon?",
        "Graho ke saath bahut accha chal raha hai! Batao kya jaanna hai.",
        "Main yahan hoon aur tayyar hoon — kya poochhna hai?",
    ],

    # User asks who/what the bot is
    "who_are_you": [
        "I'm NakshatraAI — your personal Vedic astrology guide. Ask me anything about your chart!",
        "Think of me as your digital jyotishi, {user_name}. Vedic and Western astrology, all in one place.",
        "I'm NakshatraAI, trained in Vedic and Western astrology. What would you like to know?",
        "Your friendly astrology consultant! Planets, dashas, transits — I've got you covered.",
    ],
    "who_are_you_hi": [
        "Main NakshatraAI hoon — aapka Vedic jyotish sahayak! Kya jaanna hai?",
        "Sochiye mujhe apna digital jyotishi! Kundali, dasha, transit — sab kuch yahan hai.",
        "Main aapka astrology guide hoon, {user_name}. Kuch poochhein!",
    ],
}


def get_contextual_greeting(user_name: str, conversation_length: int, language: str = 'en') -> str:
    """
    Get a short, varied greeting from the appropriate language pool.
    First-time greeting is handled by the mobile app; this always returns
    a brief, conversational returning-user response.

    Args:
        user_name: User's name
        conversation_length: Not used for selection (kept for API compatibility)
        language: ISO language code ('en', 'hi', 'hi-lat', 'ta', 'ta-lat')

    Returns:
        Randomly selected greeting string, formatted with user_name
    """
    import random

    if language == 'hi':
        pool = GREETING_HINDI_RETURNING
    elif language in ('hi-lat', 'hi_lat'):
        pool = GREETING_HINGLISH_RETURNING
    elif language.startswith('ta'):
        pool = GREETING_TAMIL_RETURNING
    elif language == 'pa':
        pool = GREETING_PUNJABI_RETURNING
    elif language in ('pa-lat', 'pa_lat'):
        pool = GREETING_PUNJABI_LAT_RETURNING
    else:
        pool = GREETING_RETURNING

    return random.choice(pool).format(user_name=user_name)


def get_chitchat_response(
    trigger: str,
    user_name: str = "friend",
    language: str = "en",
    llm=None,
    query: str = "",
) -> str:
    """
    Return a varied, humanised response for common chitchat signals.

    Falls back to an LLM-generated response when the trigger doesn't match
    any pool, maintaining personality even for novel social inputs.

    Args:
        trigger:   One of 'thanks', 'bye', 'how_are_you', 'who_are_you', or 'unknown'
        user_name: User's display name
        language:  ISO language code
        llm:       Optional LangChain LLM instance for novel triggers
        query:     Original user query (used when falling back to LLM)

    Returns:
        A varied, natural-sounding response string
    """
    import random

    # Pick language-appropriate pool suffix
    lang_suffix = "_hi" if language in ('hi', 'hi-lat', 'hi_lat') else ""
    pool_key = f"{trigger}{lang_suffix}"

    pool = CHITCHAT_RESPONSES.get(pool_key) or CHITCHAT_RESPONSES.get(trigger)
    if pool:
        return random.choice(pool).format(user_name=user_name)

    # Unknown chitchat trigger — use LLM for a characterful response
    if llm and query:
        try:
            prompt = (
                f"You are NakshatraAI, a warm, professional Vedic astrology assistant.\n"
                f"Keep the response SHORT (1-2 sentences), friendly and in character.\n"
                f"Do NOT give astrological analysis. This is casual conversation.\n"
                f"User: {query}\n"
                f"NakshatraAI:"
            )
            resp = llm.invoke(prompt)
            text = (resp.content if hasattr(resp, 'content') else str(resp)).strip()
            if text:
                return text
        except Exception:
            pass

    # Final generic fallback
    generic = [
        f"I'm here whenever you're ready, {user_name}!",
        "Feel free to ask anything astrology-related!",
        "The stars are always ready — so am I.",
    ]
    return random.choice(generic)


def detect_third_party_query(query: str) -> tuple[bool, str]:
    """
    Detect if user is asking about someone else's chart/prediction.

    Covers English AND Hindi/Hinglish relationship terms so privacy
    protections are applied for multilingual users.

    Returns:
        (is_third_party, person_mentioned)
    """
    q = query.lower()

    # Third-party indicators — English
    en_patterns = [
        'my friend', 'my sister', 'my brother', 'my mother', 'my father',
        'my husband', 'my wife', 'my boyfriend', 'my girlfriend',
        'my son', 'my daughter', 'my child', 'my children',
        'my boss', 'my colleague', 'my partner', 'my aunt', 'my uncle',
        # Possessive third-person
        'her chart', 'his chart', 'their chart',
        'her horoscope', 'his horoscope',
        'her birth', 'his birth',
        # Predictive third-person
        'when will he', 'when will she', 'when will they',
        'will he', 'will she', 'will they',
        'does he', 'does she', 'do they',
    ]

    # Third-party indicators — Hindi / Hinglish
    hi_patterns = [
        'mera dost', 'meri saheli', 'mera bhai', 'meri behen',
        'meri maa', 'mere papa', 'mera pati', 'meri patni',
        'mera beta', 'meri beti', 'mere bacche',
        'mera boss', 'mere saathi', 'mera partner',
        # Possessive third-person (Hinglish)
        'uski kundali', 'unki kundali', 'uska chart',
        'uska janm', 'unka janm',
        # Predictive third-person
        'woh kab', 'unka kab', 'kya woh', 'kya unka',
    ]

    all_patterns = en_patterns + hi_patterns

    person_mentioned = "someone else"
    for pattern in all_patterns:
        if pattern in q:
            # Try to extract name if present
            import re
            words_after = query[query.lower().find(pattern) + len(pattern):]
            names = re.findall(r'\b[A-Z][a-z]+\b', words_after[:50])
            if names:
                person_mentioned = names[0]

            if 'name is' in q or 'named' in q:
                name_match = re.search(r'name is ([A-Z][a-z]+)', query, re.IGNORECASE)
                if name_match:
                    person_mentioned = name_match.group(1)

            return True, person_mentioned

    return False, None


def build_third_party_refusal(person: str, user_name: str) -> str:
    """
    Build polite refusal for third-party predictions.
    
    Args:
        person: Name/description of the third party
        user_name: Authenticated user's name
    
    Returns:
        Formatted refusal message
    """
    return SOFT_BLOCK_THIRD_PARTY_PREDICTION.replace(
        "for others:", 
        f"for {person}:"
    ).replace(
        "Is there something about YOUR chart",
        f"Is there something about YOUR chart, {user_name},"
    )
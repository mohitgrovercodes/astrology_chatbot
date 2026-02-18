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

For questions about {topic}, you would need to consult specialists in that field.

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


# ============================================================================
# CONDITIONAL DISCLAIMERS (Answer with Warning)
# ============================================================================

DISCLAIMER_HEALTH = """

⚕️ **Important Disclaimer**: The astrological insights I provide are for educational and self-reflection purposes only. Astrology indicates *tendencies* and *areas of focus*, not medical diagnoses. Always consult qualified healthcare providers for health concerns, diagnoses, or treatment decisions."""

DISCLAIMER_FINANCIAL = """

💼 **Important Disclaimer**: Astrological insights about finances and career are for guidance and timing awareness only. They should not be your sole basis for major financial decisions. Always consult financial advisors and make practical assessments before significant investments or career changes."""

DISCLAIMER_RELATIONSHIP = """

💕 **Important Reminder**: Astrological compatibility is one factor among many in relationships. Real-world communication, shared values, mutual respect, and effort are far more important than chart compatibility. Use these insights as a tool for understanding, not as a relationship verdict."""

DISCLAIMER_CHILDREN = """

👶 **Important Note**: Questions about children and fertility are deeply personal. While astrology can indicate favorable periods, it cannot predict specific outcomes. Medical consultation is essential for fertility and family planning decisions. These astrological insights are for timing awareness only."""

DISCLAIMER_CAREER = """

💼 **Important Reminder**: Career decisions should be based on practical factors—skills, market conditions, financial stability, and personal circumstances. Astrological timing is one input among many. Use this guidance to inform your decision-making, not replace it."""

DISCLAIMER_GENERAL = """

🔮 **Important Reminder**: Astrological insights are for self-reflection and timing awareness. They show tendencies and potentials, not fixed destinies. Your free will, choices, and circumstances all play crucial roles in shaping outcomes."""


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
    
    # Soft Blocks
    "SOFT_BLOCK_FORTUNE": SOFT_BLOCK_FORTUNE,
    "SOFT_BLOCK_FORTUNE_TELLING": SOFT_BLOCK_FORTUNE,
    "SOFT_BLOCK_PRIVACY": SOFT_BLOCK_PRIVACY,
    "SOFT_BLOCK_PRIVACY_VIOLATION": SOFT_BLOCK_PRIVACY,
    "SOFT_BLOCK_OUT_OF_SCOPE": SOFT_BLOCK_OUT_OF_SCOPE,
    "SOFT_BLOCK_CONSPIRACY": SOFT_BLOCK_CONSPIRACY,
    "SOFT_BLOCK_CONSPIRACY_THEORY": SOFT_BLOCK_CONSPIRACY,
    "SOFT_BLOCK_THIRD_PARTY_HARM": SOFT_BLOCK_THIRD_PARTY_HARM,
    
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


def get_disclaimer(disclaimer_type: str) -> str:
    """
    Get disclaimer text by type.
    
    Args:
        disclaimer_type: Type of disclaimer ('HEALTH', 'FINANCIAL', etc.)
    
    Returns:
        Disclaimer text string
    """
    key = f"DISCLAIMER_{disclaimer_type.upper()}"
    return get_template(key)


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

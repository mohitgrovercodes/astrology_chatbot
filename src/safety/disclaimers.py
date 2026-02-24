# src/safety/disclaimers.py
# src\safety\disclaimers.py
"""
Disclaimers - Natural Astrologer-Style Disclaimers
===================================================

Provides contextual disclaimers that sound like a professional astrologer,
not legal boilerplate. These are designed to be embedded naturally in responses.
"""

from typing import Dict, Optional
from enum import Enum


class DisclaimerType(Enum):
    """Types of disclaimers available."""
    HEALTH = "health"
    DEATH_MORTALITY = "death_mortality"
    MENTAL_HEALTH = "mental_health"
    LEGAL = "legal"
    FINANCIAL = "financial"
    RELATIONSHIP = "relationship"
    GENERAL_PREDICTION = "general_prediction"
    TIMING = "timing"


# Full disclaimer templates by type
DISCLAIMERS: Dict[str, str] = {
    "health": (
        "As an astrologer, I can share what the planetary influences suggest about "
        "your vitality and constitution. The chart reveals periods of strength and "
        "vulnerability, though of course this complements rather than replaces "
        "proper medical guidance. What the stars show are tendencies and timing."
    ),
    
    "death_mortality": (
        "The ancient Vedic texts approach longevity with great wisdom - they teach us "
        "that astrology reveals the quality and rhythm of life, not its absolute duration. "
        "Charts show periods that call for extra care and periods of robust vitality. "
        "Many great astrologers emphasize that awareness itself is the best protection."
    ),
    
    "mental_health": (
        "Astrological cycles can illuminate periods of emotional intensity or calm, "
        "but I want you to know that if you're experiencing difficulty, professional "
        "support is always valuable. The planets show the terrain, but you never have "
        "to walk difficult paths alone."
    ),
    
    "legal": (
        "From an astrological perspective, I can examine the planetary positions "
        "affecting timing and energy around legal matters. The 6th house of disputes "
        "and the 7th of contracts tell a story, though specific legal advice should "
        "always come from a qualified attorney who knows your case."
    ),
    
    "financial": (
        "The stars indicate general periods of financial opportunity or caution - "
        "the 2nd house of wealth, the 11th of gains, Jupiter's blessings. These are "
        "trends and tendencies. Specific investment decisions benefit from professional "
        "financial advice tailored to your complete picture."
    ),
    
    "relationship": (
        "Astrology offers beautiful insights into relationship dynamics - compatibility, "
        "timing, the dance of Venus and Mars. At the same time, every relationship "
        "involves two souls making choices. The stars incline, as the ancients said, "
        "they do not compel."
    ),
    
    "general_prediction": (
        "Based on your chart and the current planetary transits, I see tendencies and "
        "possibilities rather than fixed outcomes. Astrology is a language of probability "
        "and potential - it shows the currents, while you remain the captain of your ship."
    ),
    
    "timing": (
        "Astrological timing works in general windows and tendencies. Specific dates "
        "depend on many factors including your engagement with opportunities and "
        "the choices you make. Think of these as favorable winds rather than precise schedules."
    )
}


# Clarifying questions for sensitive topics
CLARIFYING_QUESTIONS: Dict[str, str] = {
    "death_mortality": (
        "I sense this is an important question for you. To provide the most helpful "
        "guidance, could you share what's prompting this inquiry? Are you looking to "
        "understand longevity factors in your chart, or is there a specific concern "
        "I can address with more care?"
    ),
    
    "mental_health": (
        "I want to make sure I understand your question correctly and can offer the "
        "most supportive guidance. Are you asking about general periods of emotional "
        "challenge in your chart, or is there something more immediate on your mind? "
        "I'm here to help in whatever way I can."
    ),
    
    "health": (
        "To give you the most relevant astrological perspective, could you tell me "
        "a bit more about what you're hoping to understand? Are you looking at general "
        "health periods, or is there a specific concern you'd like me to address?"
    ),
    
    "relationship": (
        "Relationship questions often have many layers. To give you the most helpful "
        "guidance, could you share what aspect you're most curious about - compatibility, "
        "timing, or understanding current dynamics?"
    ),
    
    "legal": (
        "Legal matters can involve many astrological factors. To focus my analysis, "
        "could you tell me more about whether you're asking about timing, likelihood "
        "of favorable outcomes, or general planetary influences?"
    ),
    
    "financial": (
        "Financial questions in astrology can cover many areas. Are you curious about "
        "general periods of opportunity, career growth, or something more specific "
        "like timing for a major decision?"
    )
}


# Positive redirects to reframe queries constructively
POSITIVE_REDIRECTS: Dict[str, str] = {
    "death_mortality": (
        "Let me focus on the vitality and longevity factors in your chart - the "
        "strength of your Lagna, the condition of your 8th house lord, and the "
        "protective influences present. Understanding these helps you know when "
        "to take extra care of yourself."
    ),
    
    "health": (
        "I'll share what your chart reveals about your constitutional strengths "
        "and the planetary periods most favorable for health and healing. Your "
        "chart has specific indicators of vitality that are helpful to understand."
    ),
    
    "mental_health": (
        "Let me look at the periods of emotional strength in your chart and the "
        "planetary support available to you. The Moon's condition and Jupiter's "
        "blessings often show where peace and resilience can be found."
    ),
    
    "legal": (
        "I'll examine the planetary influences affecting legal matters and the "
        "periods most favorable for resolution. The 6th house of disputes and "
        "Jupiter's position often indicate paths toward positive outcomes."
    ),
    
    "financial": (
        "Let me share the periods of financial opportunity indicated in your chart. "
        "The 2nd house of wealth, the 11th house of gains, and Jupiter's transits "
        "often indicate when fortune smiles."
    ),
    
    "relationship": (
        "I'll look at the relationship dynamics and periods of harmony indicated "
        "in your chart. Venus's position and the 7th house often reveal the deeper "
        "patterns at play and the potential for connection."
    )
}


# Empathetic openings for sensitive topics
EMPATHETIC_OPENINGS: Dict[str, str] = {
    "death_mortality": (
        "I understand this is a profound question that touches on some of our "
        "deepest concerns. Let me approach this with the care it deserves."
    ),
    
    "health": (
        "Health concerns naturally bring a desire for clarity and hope. "
        "Let me share what the stars reveal with care."
    ),
    
    "mental_health": (
        "I hear the weight in your question, and I want to offer what guidance "
        "I can while honoring the depth of what you're experiencing."
    ),
    
    "relationship": (
        "Matters of the heart are never simple, and your seeking clarity is "
        "understandable. Let me look at what the planets reveal."
    ),
    
    "legal": (
        "Legal matters can carry significant stress. Astrology can offer "
        "perspective on timing and energy that may be helpful."
    ),
    
    "financial": (
        "Financial questions often reflect deeper concerns about security "
        "and wellbeing. Let me share what your chart reveals."
    )
}


def get_disclaimer(disclaimer_type: str) -> str:
    """
    Get a disclaimer by type.
    
    Args:
        disclaimer_type: Type of disclaimer (health, legal, etc.)
        
    Returns:
        The disclaimer text, or empty string if not found
    """
    return DISCLAIMERS.get(disclaimer_type, DISCLAIMERS.get("general_prediction", ""))


def get_clarifying_question(topic: str) -> str:
    """
    Get a clarifying question for a sensitive topic.
    
    Args:
        topic: The sensitive topic category
        
    Returns:
        A naturally-worded clarifying question
    """
    return CLARIFYING_QUESTIONS.get(
        topic,
        "Could you tell me more about what you're hoping to understand? "
        "This helps me give you the most relevant guidance."
    )


def get_positive_redirect(topic: str) -> str:
    """
    Get a positive-framing redirect for a topic.
    
    Args:
        topic: The topic category
        
    Returns:
        A positive framing statement
    """
    return POSITIVE_REDIRECTS.get(topic, "")


def get_empathetic_opening(topic: str) -> str:
    """
    Get an empathetic opening for a sensitive topic.
    
    Args:
        topic: The topic category
        
    Returns:
        An empathetic opening statement
    """
    return EMPATHETIC_OPENINGS.get(topic, "")


def build_enhanced_response(
    main_response: str,
    topic: str,
    include_opening: bool = True,
    include_redirect: bool = True,
    include_disclaimer: bool = True
) -> str:
    """
    Build an enhanced response with all appropriate framing.
    
    Args:
        main_response: The main astrological response
        topic: The sensitive topic category
        include_opening: Whether to add empathetic opening
        include_redirect: Whether to add positive redirect
        include_disclaimer: Whether to add disclaimer
        
    Returns:
        Fully enhanced response
    """
    parts = []
    
    if include_opening:
        opening = get_empathetic_opening(topic)
        if opening:
            parts.append(opening)
    
    if include_redirect:
        redirect = get_positive_redirect(topic)
        if redirect:
            parts.append(redirect)
    
    parts.append(main_response)
    
    if include_disclaimer:
        disclaimer = get_disclaimer(topic)
        if disclaimer:
            parts.append(disclaimer)
    
    return "\n\n".join(parts)

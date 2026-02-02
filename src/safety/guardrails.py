"""
Guardrails - Core Safety Logic
==============================

Analyzes queries for sensitive topics and enhances responses with appropriate
context, disclaimers, and empathetic framing.

Philosophy: C -> B -> A
- C: Clarify first (ask clarifying questions for ambiguous sensitive queries)
- B: Redirect to positive (frame around constructive aspects)
- A: Provide with empathy (give astrological insight with care)
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import re


class SensitivityCategory(Enum):
    """Categories of sensitive topics requiring special handling."""
    GENERAL = "general"
    HEALTH = "health"
    DEATH_MORTALITY = "death_mortality"
    LEGAL = "legal"
    FINANCIAL = "financial"
    RELATIONSHIP = "relationship"
    MENTAL_HEALTH = "mental_health"


class HandlingStrategy(Enum):
    """How to handle the query based on analysis."""
    PROCEED_NORMAL = "proceed_normal"           # No special handling needed
    CLARIFY_FIRST = "clarify_first"             # Ask clarifying question (C)
    REDIRECT_POSITIVE = "redirect_positive"     # Frame positively (B)
    EMPATHETIC_RESPONSE = "empathetic_response" # Provide with empathy + disclaimer (A)


@dataclass
class QueryAnalysis:
    """Result of analyzing a query for sensitive content."""
    category: SensitivityCategory
    sensitivity_level: float  # 0.0 (none) to 1.0 (very sensitive)
    handling_strategy: HandlingStrategy
    requires_disclaimer: bool
    disclaimer_type: str
    clarifying_question: Optional[str] = None
    positive_redirect: Optional[str] = None
    detected_keywords: List[str] = field(default_factory=list)
    reasoning: str = ""


class QueryAnalyzer:
    """
    Analyzes user queries to detect sensitive topics and determine
    appropriate handling strategy.
    
    This does NOT block queries - it provides guidance for response generation.
    """
    
    # Keyword patterns for each category
    PATTERNS = {
        SensitivityCategory.DEATH_MORTALITY: {
            "keywords": [
                r"\bdie\b", r"\bdeath\b", r"\bdying\b", r"\bkill\b",
                r"\bmortality\b", r"\blifespan\b", r"\bfatal\b",
                r"\bend of life\b", r"\blast days\b", r"\bmaraka\b",
                r"\bayushya\b", r"\blongevity\b", r"\bsuicide\b"
            ],
            "questions": [
                r"when will .* die",
                r"how long .* live",
                r"what age .* die",
                r"is .* going to die",
                r"will .* survive"
            ],
            "sensitivity": 0.9,
            "clarify": True  # Always clarify first for death-related
        },
        SensitivityCategory.HEALTH: {
            "keywords": [
                r"\billness\b", r"\bdisease\b", r"\bsick\b", r"\bmedical\b",
                r"\bhospital\b", r"\bsurgery\b", r"\bcancer\b", r"\btreatment\b",
                r"\brecovery\b", r"\bhealth\b", r"\bcure\b", r"\bdiagnos",
                r"\bpregnancy\b", r"\bconceive\b", r"\bfertility\b", r"\bchild.*birth\b"
            ],
            "questions": [
                r"will .* recover",
                r"will .* get better",
                r"is .* serious",
                r"when .* heal",
                r"will .* have .* baby"
            ],
            "sensitivity": 0.7,
            "clarify": False  # Can proceed with empathy
        },
        SensitivityCategory.MENTAL_HEALTH: {
            "keywords": [
                r"\bdepressed\b", r"\bdepression\b", r"\banxiety\b", r"\banxious\b",
                r"\bmental\b", r"\bstress\b", r"\bsuicid", r"\bharm.*self\b",
                r"\bhopeless\b", r"\bworthless\b", r"\bending it\b"
            ],
            "questions": [
                r"will .* feel better",
                r"when .* depression",
                r"is .* worth"
            ],
            "sensitivity": 0.95,
            "clarify": True
        },
        SensitivityCategory.LEGAL: {
            "keywords": [
                r"\bcourt\b", r"\blawsuit\b", r"\blegal\b", r"\bjudge\b",
                r"\bprison\b", r"\bjail\b", r"\barrest\b", r"\bpolice\b",
                r"\blawyer\b", r"\btrial\b", r"\bcase\b.*win\b", r"\bverdict\b",
                r"\bdivorce.*court\b", r"\bcustody\b"
            ],
            "questions": [
                r"will .* win .* case",
                r"will .* go to jail",
                r"will .* get arrested",
                r"what .* verdict"
            ],
            "sensitivity": 0.6,
            "clarify": False
        },
        SensitivityCategory.FINANCIAL: {
            "keywords": [
                r"\blottery\b", r"\bgambl", r"\bbet\b", r"\bcasino\b",
                r"\bstock\b", r"\binvest\b", r"\bcrypto\b", r"\bbitcoin\b",
                r"\bbankrupt\b", r"\bdebt\b", r"\bloan\b", r"\brich\b"
            ],
            "questions": [
                r"should .* invest",
                r"will .* win .* lottery",
                r"will .* become rich",
                r"which stock",
                r"when .* money"
            ],
            "sensitivity": 0.5,
            "clarify": False
        },
        SensitivityCategory.RELATIONSHIP: {
            "keywords": [
                r"\bcheat", r"\baffair\b", r"\binfidelity\b", r"\bbetra",
                r"\bdivorce\b", r"\bseparate\b", r"\bbreak.*up\b",
                r"\babuse\b", r"\bviolence\b", r"\bhurt\b.*partner\b",
                r"\bleaving me\b", r"\bleft me\b"
            ],
            "questions": [
                r"is .* cheating",
                r"should .* divorce",
                r"will .* leave me",
                r"is .* having .* affair",
                r"will .* come back"
            ],
            "sensitivity": 0.6,
            "clarify": False
        }
    }
    
    def __init__(self):
        """Initialize the query analyzer."""
        # Compile regex patterns for efficiency
        self._compiled_patterns = {}
        for category, config in self.PATTERNS.items():
            self._compiled_patterns[category] = {
                "keywords": [re.compile(p, re.IGNORECASE) for p in config["keywords"]],
                "questions": [re.compile(p, re.IGNORECASE) for p in config["questions"]],
                "sensitivity": config["sensitivity"],
                "clarify": config["clarify"]
            }
    
    def analyze(self, query: str) -> QueryAnalysis:
        """
        Analyze a query for sensitive content.
        
        Args:
            query: The user's query text
            
        Returns:
            QueryAnalysis with category, sensitivity, and handling guidance
        """
        query_lower = query.lower()
        
        # Check each category
        matches: List[Tuple[SensitivityCategory, float, List[str]]] = []
        
        for category, compiled in self._compiled_patterns.items():
            detected_keywords = []
            
            # Check keywords
            for pattern in compiled["keywords"]:
                match = pattern.search(query_lower)
                if match:
                    detected_keywords.append(match.group())
            
            # Check question patterns (higher weight)
            for pattern in compiled["questions"]:
                match = pattern.search(query_lower)
                if match:
                    detected_keywords.append(f"[Q] {match.group()}")
            
            if detected_keywords:
                # Calculate sensitivity based on matches
                base_sensitivity = compiled["sensitivity"]
                # More matches = higher sensitivity
                match_boost = min(len(detected_keywords) * 0.05, 0.1)
                final_sensitivity = min(base_sensitivity + match_boost, 1.0)
                
                matches.append((category, final_sensitivity, detected_keywords))
        
        # If no sensitive content detected
        if not matches:
            return QueryAnalysis(
                category=SensitivityCategory.GENERAL,
                sensitivity_level=0.0,
                handling_strategy=HandlingStrategy.PROCEED_NORMAL,
                requires_disclaimer=False,
                disclaimer_type="none",
                reasoning="No sensitive content detected"
            )
        
        # Get the most sensitive match
        matches.sort(key=lambda x: x[1], reverse=True)
        top_category, top_sensitivity, top_keywords = matches[0]
        
        # Determine handling strategy based on C -> B -> A philosophy
        config = self._compiled_patterns[top_category]
        
        if config["clarify"] and top_sensitivity >= 0.8:
            # C: Clarify first for highly sensitive queries
            strategy = HandlingStrategy.CLARIFY_FIRST
            clarify_q = self._get_clarifying_question(top_category, query)
            positive_redirect = None
        elif top_sensitivity >= 0.5:
            # B -> A: Redirect positive, then empathetic
            strategy = HandlingStrategy.EMPATHETIC_RESPONSE
            clarify_q = None
            positive_redirect = self._get_positive_redirect(top_category)
        else:
            # Low sensitivity, proceed normally with disclaimer
            strategy = HandlingStrategy.PROCEED_NORMAL
            clarify_q = None
            positive_redirect = None
        
        return QueryAnalysis(
            category=top_category,
            sensitivity_level=top_sensitivity,
            handling_strategy=strategy,
            requires_disclaimer=top_sensitivity >= 0.3,
            disclaimer_type=top_category.value,
            clarifying_question=clarify_q,
            positive_redirect=positive_redirect,
            detected_keywords=top_keywords,
            reasoning=f"Detected {len(top_keywords)} indicators for {top_category.value}"
        )
    
    def _get_clarifying_question(self, category: SensitivityCategory, query: str) -> str:
        """Get an appropriate clarifying question for the category."""
        questions = {
            SensitivityCategory.DEATH_MORTALITY: (
                "I sense this is an important question for you. To provide the most helpful "
                "guidance, could you share what's prompting this inquiry? Are you looking to "
                "understand longevity factors in your chart, or is there a specific concern "
                "I can address with more care?"
            ),
            SensitivityCategory.MENTAL_HEALTH: (
                "I want to make sure I understand your question correctly and can offer the "
                "most supportive guidance. Are you asking about general periods of emotional "
                "challenge in your chart, or is there something more immediate on your mind? "
                "I'm here to help in whatever way I can."
            ),
            SensitivityCategory.HEALTH: (
                "To give you the most relevant astrological perspective, could you tell me "
                "a bit more about what you're hoping to understand? Are you looking at general "
                "health periods, or is there a specific concern you'd like me to address?"
            ),
            SensitivityCategory.RELATIONSHIP: (
                "Relationship questions often have many layers. To give you the most helpful "
                "guidance, could you share what aspect you're most curious about - compatibility, "
                "timing, or understanding current dynamics?"
            )
        }
        return questions.get(category, "Could you tell me more about what you're hoping to understand?")
    
    def _get_positive_redirect(self, category: SensitivityCategory) -> str:
        """Get a positive framing redirect for the category."""
        redirects = {
            SensitivityCategory.DEATH_MORTALITY: (
                "Let me focus on the vitality and longevity factors in your chart, "
                "and the periods that call for extra attention to wellbeing."
            ),
            SensitivityCategory.HEALTH: (
                "I'll share what your chart reveals about your constitutional strengths "
                "and the planetary periods most favorable for health and recovery."
            ),
            SensitivityCategory.MENTAL_HEALTH: (
                "Let me look at the periods of emotional strength in your chart "
                "and the planetary support available to you."
            ),
            SensitivityCategory.LEGAL: (
                "I'll examine the planetary influences affecting legal matters "
                "and the periods most favorable for resolution."
            ),
            SensitivityCategory.FINANCIAL: (
                "Let me share the periods of financial opportunity indicated in your chart "
                "and the favorable times for growth."
            ),
            SensitivityCategory.RELATIONSHIP: (
                "I'll look at the relationship dynamics and periods of harmony "
                "indicated in your chart."
            )
        }
        return redirects.get(category, "")


class ResponseEnhancer:
    """
    Enhances LLM responses with appropriate disclaimers,
    empathetic framing, and professional astrologer tone.
    """
    
    def __init__(self):
        """Initialize the response enhancer."""
        pass
    
    def enhance(
        self,
        response: str,
        analysis: QueryAnalysis,
        include_disclaimer: bool = True
    ) -> str:
        """
        Enhance a response based on the query analysis.
        
        Args:
            response: The raw LLM response
            analysis: The QueryAnalysis from QueryAnalyzer
            include_disclaimer: Whether to add disclaimers
            
        Returns:
            Enhanced response with appropriate framing
        """
        if analysis.category == SensitivityCategory.GENERAL:
            # No enhancement needed for general queries
            return response
        
        enhanced_parts = []
        
        # 1. Add empathetic opening if needed
        if analysis.sensitivity_level >= 0.7:
            opening = self._get_empathetic_opening(analysis.category)
            if opening and not response.lower().startswith(opening.lower()[:20]):
                enhanced_parts.append(opening)
        
        # 2. Add positive redirect if available
        if analysis.positive_redirect:
            enhanced_parts.append(analysis.positive_redirect)
        
        # 3. Add the main response
        enhanced_parts.append(response)
        
        # 4. Add natural disclaimer if needed
        if include_disclaimer and analysis.requires_disclaimer:
            disclaimer = self._get_natural_disclaimer(analysis.category)
            # Only add if not already present in response
            if disclaimer and disclaimer.lower() not in response.lower():
                enhanced_parts.append(disclaimer)
        
        # Join with appropriate spacing
        return "\n\n".join(part for part in enhanced_parts if part)
    
    def _get_empathetic_opening(self, category: SensitivityCategory) -> str:
        """Get an empathetic opening for sensitive categories."""
        openings = {
            SensitivityCategory.DEATH_MORTALITY: (
                "I understand this is a profound question that touches on our deepest concerns."
            ),
            SensitivityCategory.HEALTH: (
                "Health concerns naturally bring a desire for clarity and hope."
            ),
            SensitivityCategory.MENTAL_HEALTH: (
                "I hear the weight in your question, and I want to offer what guidance I can."
            ),
            SensitivityCategory.RELATIONSHIP: (
                "Matters of the heart are never simple, and your seeking clarity is understandable."
            ),
            SensitivityCategory.LEGAL: (
                "Legal matters can be stressful, and astrology can offer perspective on timing and energy."
            ),
            SensitivityCategory.FINANCIAL: (
                "Financial questions often reflect deeper concerns about security and wellbeing."
            )
        }
        return openings.get(category, "")
    
    def _get_natural_disclaimer(self, category: SensitivityCategory) -> str:
        """Get a natural-sounding disclaimer that fits the astrologer persona."""
        disclaimers = {
            SensitivityCategory.DEATH_MORTALITY: (
                "The ancient texts remind us that astrology reveals tendencies and periods of "
                "vulnerability or strength, not fixed fates. Awareness itself is protective, "
                "and the planets show us possibilities, not certainties."
            ),
            SensitivityCategory.HEALTH: (
                "Of course, astrological insights complement but never replace proper medical "
                "guidance. The planets can indicate periods of vitality or vulnerability, "
                "helping you know when to take extra care."
            ),
            SensitivityCategory.MENTAL_HEALTH: (
                "While astrology offers perspective on emotional cycles and challenging periods, "
                "please know that professional support is always available if you need it. "
                "You don't have to navigate difficult times alone."
            ),
            SensitivityCategory.LEGAL: (
                "Astrological timing can offer perspective on favorable periods, though "
                "specific legal matters should always be discussed with a qualified attorney "
                "who knows your situation fully."
            ),
            SensitivityCategory.FINANCIAL: (
                "The planets indicate general periods of opportunity or caution, but specific "
                "investment decisions benefit from professional financial guidance tailored "
                "to your unique situation."
            ),
            SensitivityCategory.RELATIONSHIP: (
                "Astrology illuminates patterns and possibilities in relationships, while "
                "remembering that every connection involves two people making choices. "
                "The stars incline, they do not compel."
            )
        }
        return disclaimers.get(category, "")
    
    def should_ask_clarification(self, analysis: QueryAnalysis) -> Tuple[bool, Optional[str]]:
        """
        Determine if we should ask a clarifying question first.
        
        Returns:
            Tuple of (should_clarify, clarifying_question)
        """
        if analysis.handling_strategy == HandlingStrategy.CLARIFY_FIRST:
            return True, analysis.clarifying_question
        return False, None


# Convenience function for quick analysis
def analyze_query(query: str) -> QueryAnalysis:
    """Quick analysis of a query."""
    analyzer = QueryAnalyzer()
    return analyzer.analyze(query)


# Convenience function for quick enhancement
def enhance_response(response: str, query: str) -> str:
    """Quick enhancement of a response based on query."""
    analyzer = QueryAnalyzer()
    enhancer = ResponseEnhancer()
    analysis = analyzer.analyze(query)
    return enhancer.enhance(response, analysis)

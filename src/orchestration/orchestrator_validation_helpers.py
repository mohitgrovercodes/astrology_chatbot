# src/orchestration/orchestrator_validation_helpers.py
"""
Validation Engine Integration Helpers for NakshatraAI Orchestrator
Complete implementation with LLM-based query type confirmation and soft halt handling.

FIXED VERSION - All dasha_data and transit_data null access issues resolved
"""

from typing import Dict, Optional, List, Any
from config.logger import get_logger

logger = get_logger("validation_helpers")


# ============================================================================
# QUERY TYPE DETECTION WITH LLM CONFIRMATION
# ============================================================================

def detect_query_type_patterns(query: str) -> tuple[str, float]:
    """
    Pattern-based query type detection with confidence score.
    
    Returns:
        (query_type, confidence) where confidence is 0.0-1.0
    """
    query_lower = query.lower()
    
    # Define keyword patterns with weights
    categories = {
        'marriage': {
            'strong': ['marry', 'marriage', 'spouse', 'wedding', 'shaadi', 'shadi', 'vivah', 'byah', 'biyah', 'nikah', 'mangni', 'sagai'],
            'medium': ['partner', 'relationship', 'love life', 'wife', 'husband', 'life partner', 'dulha', 'dulhan', 'patni', 'pati'],
            'weak': ['matrimony', 'married life', 'rishta', 'rishtey']
        },
        'career': {
            'strong': ['job', 'career', 'profession', 'business', 'naukri', 'rozgaar', 'rozgar', 'kaam', 'vyavsay'],
            'medium': ['work', 'employment', 'service', 'occupation', 'office', 'company'],
            'weak': ['promotion', 'vyapar', 'dhandha', 'tarakki']
        },
        'finance': {
            'strong': ['money', 'wealth', 'income', 'dhan', 'paisa', 'paise', 'dhana', 'arthik'],
            'medium': ['prosperity', 'financial', 'rich', 'fortune', 'ameer', 'samridhi'],
            'weak': ['property', 'assets', 'savings', 'investment', 'sampatti']
        },
        'health': {
            'strong': ['health', 'disease', 'illness', 'swasthya', 'bimari', 'sehat', 'rog'],
            'medium': ['medical', 'sickness', 'cure', 'dawai', 'ilaaj'],
            'weak': ['treatment', 'ailment', 'takleef']
        },
        'children': {
            'strong': ['child', 'children', 'son', 'daughter', 'santan', 'baccha', 'bachche', 'beta', 'beti', 'ladka', 'ladki'],
            'medium': ['pregnancy', 'putra', 'offspring', 'garbh', 'prasav'],
            'weak': ['progeny', 'kids', 'aulad']
        },
        'foreign': {
            'strong': ['foreign', 'abroad', 'videsh', 'overseas', 'immigration', 'visa', 'settlement abroad',
                       'foreign trip', 'foreign travel', 'foreign yatra', 'videsh yatra', 'bahar jaana',
                       'foreign land', 'settle abroad', 'job abroad'],
            'medium': ['travel', 'yatra', 'trip', 'bahar', 'safar', 'journey', 'relocation', 'migrate'],
            'weak': ['tour', 'visit abroad', 'go abroad', 'foreign country']
        }
    }
    
    # Score each category
    scores = {}
    for category, keyword_sets in categories.items():
        score = 0.0
        matches = 0
        
        for kw in keyword_sets['strong']:
            if kw in query_lower:
                score += 3.0
                matches += 1
        
        for kw in keyword_sets['medium']:
            if kw in query_lower:
                score += 2.0
                matches += 1
        
        for kw in keyword_sets['weak']:
            if kw in query_lower:
                score += 1.0
                matches += 1
        
        scores[category] = (score, matches)
    
    # Find best match
    best_category = max(scores, key=lambda k: scores[k][0])
    best_score, best_matches = scores[best_category]
    
    if best_score == 0:
        return 'general', 1.0  # No matches = general question (high confidence)
    
    # Calculate confidence based on score and exclusivity
    total_score = sum(s[0] for s in scores.values())
    confidence = best_score / total_score if total_score > 0 else 0.0
    
    # Boost confidence if multiple strong keywords matched
    if best_matches >= 2:
        confidence = min(1.0, confidence + 0.2)
    
    return best_category, confidence


def confirm_query_type_with_llm(query: str, pattern_type: str, llm) -> str:
    """
    Use LLM to confirm or correct the pattern-based query type detection.
    
    Args:
        query: User's query
        pattern_type: Type detected by pattern matching
        llm: Fast LLM instance
        
    Returns:
        Confirmed query type
    """
    prompt = f"""Identify the PRIMARY topic of this astrology query. Choose ONE category:

CATEGORIES:
- marriage: Questions about marriage timing, spouse, relationship, love life
- career: Questions about job, profession, business, work
- finance: Questions about money, wealth, income, prosperity
- health: Questions about health, disease, medical issues
- children: Questions about children, pregnancy, offspring
- foreign: Questions about foreign travel, abroad, videsh, overseas, visa, immigration, settlement
- general: Theoretical questions, concepts, or unclear intent

QUERY: "{query}"

PATTERN DETECTED: {pattern_type}

Respond with ONLY the category name (one word). If the pattern detection looks wrong, correct it.

ANSWER:"""

    try:
        response = llm.invoke(prompt)
        content = response.content if hasattr(response, 'content') else str(response)
        confirmed_type = content.strip().lower()

        # Validate response
        valid_types = {'marriage', 'career', 'finance', 'health', 'children', 'foreign', 'general'}
        if confirmed_type in valid_types:
            return confirmed_type
        else:
            # LLM gave invalid response, stick with pattern detection
            return pattern_type
            
    except Exception as e:
        logger.error(f"[QUERY_TYPE] LLM confirmation failed: {e}")
        return pattern_type  # Fallback to pattern detection


def detect_query_type(
    query: str,
    llm=None,
    use_llm_confirmation: bool = True,
    intent_domain_hint: Optional[str] = None,
) -> str:
    """
    Hybrid query type detection: patterns + optional LLM confirmation.
    
    Args:
        query: User's question
        llm: Optional fast LLM for confirmation
        use_llm_confirmation: Whether to use LLM when confidence is low
        
    Returns:
        Query type: 'marriage' | 'career' | 'finance' | 'health' | 'children' | 'foreign' | 'general'
    """
    # Step 0: If we already have a trusted semantic domain from the intent
    # analyzer, use it directly when it maps cleanly to our query_type set.
    if intent_domain_hint:
        _hint = intent_domain_hint.strip().lower()
        # Normalise 'foreign_travel' -> 'foreign'
        if _hint == 'foreign_travel':
            _hint = 'foreign'
        _allowed = {'marriage', 'career', 'finance', 'health', 'children', 'foreign', 'general'}
        if _hint in _allowed:
            logger.info(f"[QUERY_TYPE] Using intent_domain_hint='{_hint}' as query_type")
            return _hint

    # Step 1: Pattern-based detection
    pattern_type, confidence = detect_query_type_patterns(query)
    
    logger.info(f"[QUERY_TYPE] Pattern detection: {pattern_type} (confidence: {confidence:.2f})")
    
    # Step 2: LLM confirmation if confidence is low, or if pattern returned 'general'
    # (LLM can catch domain-specific queries that pattern missed, e.g. "foreign trip")
    if use_llm_confirmation and llm and (confidence < 0.7 or pattern_type == 'general'):
        logger.info(f"[QUERY_TYPE] Low confidence, confirming with LLM...")
        confirmed_type = confirm_query_type_with_llm(query, pattern_type, llm)
        
        if confirmed_type != pattern_type:
            logger.info(f"[QUERY_TYPE] LLM correction: {pattern_type} -> {confirmed_type}")
            return confirmed_type
        else:
            logger.info(f"[QUERY_TYPE] LLM confirmed: {confirmed_type}")
            return confirmed_type
    
    return pattern_type


# ============================================================================
# VALIDATION TIER SELECTION (OPTIMIZED FOR LIVE CHAT)
# ============================================================================

def determine_validation_tier(query: str, user_preferences: Optional[Dict] = None) -> int:
    """
    Determine validation tier - OPTIMIZED FOR LIVE CHAT (defaults to Tier 1).
    
    Tier 1 (Fast, ~750 rules, <5s): DEFAULT for live chat
    Tier 2 (Standard, ~2500 rules, <15s): Explicit request or complex query
    Tier 3 (Detailed, ~5000+ rules, <45s): Explicit "detailed/comprehensive" request
    """
    query_lower = query.lower()
    
    # Explicit tier 3 request (must be very clear)
    detailed_keywords = ['detailed', 'comprehensive', 'thorough', 'complete analysis', 'in-depth', 'everything']
    if any(keyword in query_lower for keyword in detailed_keywords):
        return 3
    
    # Explicit tier 2 request or moderate complexity
    moderate_keywords = ['explain', 'analyze', 'what does', 'how does']
    question_count = query_lower.count('?')
    and_count = query_lower.count(' and ')
    
    if any(keyword in query_lower for keyword in moderate_keywords) or (question_count >= 2 and and_count >= 1):
        return 2
    
    # DEFAULT: Tier 1 for live chat speed
    return 1


def determine_live_chat_rule_cap(tier: int, query: str = "") -> int:
    """
    Adaptive live-chat validation cap by tier.

    Tier 1 stays fast (80 rules). Tier 2/3 allow deeper checks for
    explicit detailed-analysis requests while keeping latency bounded.
    """
    # Baseline by tier
    if tier >= 3:
        cap = 150
    elif tier == 2:
        cap = 120
    else:
        cap = 80

    # Small bump for explicit "full/detailed analysis" wording
    q = (query or "").lower()
    if any(k in q for k in ("detailed", "comprehensive", "full analysis", "in-depth")):
        cap = max(cap, 150 if tier >= 2 else 100)

    return cap


def is_analysis_only_request(query: str, question_mode: Optional[str] = None) -> bool:
    """
    Detect analysis-focused requests that are not asking for timing.

    Used to keep responses analytical (strengths/challenges/yogas/houses)
    and avoid over-emphasizing windows/dates.
    """
    q = (query or "").lower()
    if (question_mode or "").lower() == "timing":
        return False

    timing_markers = (
        "when", "kab", "timing", "date", "month", "year", "window",
        "period", "dasha", "antardasha", "pratyantar", "by when",
    )
    if any(m in q for m in timing_markers):
        return False

    analysis_markers = (
        "analyze", "analyse", "analysis", "explain", "breakdown",
        "strength", "weakness", "challenge", "overview", "assessment",
        "detailed reading", "complete reading",
    )
    return any(m in q for m in analysis_markers)


# ============================================================================
# CHART DATA PREPARATION FOR VALIDATION
# ============================================================================

def prepare_chart_for_validation(
    chart_data: Dict,
    dasha_data: Dict,
    transit_data: Dict
) -> Dict:
    """
    Convert orchestrator chart format to validation engine format.
    
    COMPREHENSIVE VERSION - Includes ALL available calculations:
    - D1 (Rasi) chart
    - ALL divisional charts (D2-D60) if available
    - Yogas (Raja Yoga, Dhana Yoga, etc.)
    - Planetary strengths (Shadbala)
    - Dasha periods with dates
    - Current transits
    - Aspects
    - House lordships
    
    FIXED: All null pointer issues for dasha_data and transit_data
    """
    
    # =========================================================================
    # 1. D1 CHART (Main Birth Chart)
    # =========================================================================
    planets_d1 = {}
    for planet_name, planet_info in chart_data.get('planets', {}).items():
        if isinstance(planet_info, dict):
            planets_d1[planet_name] = planet_info.get('rashi', 'Unknown')
        else:
            planets_d1[planet_name] = str(planet_info)
    
    validation_chart = {
        "D1": {
            "lagna": chart_data.get('lagna', chart_data.get('ascendant', {}).get('rashi', 'Unknown')),
            "planets": planets_d1
        }
    }
    
    # =========================================================================
    # 2. DIVISIONAL CHARTS (D2-D60)
    # =========================================================================
    # Check multiple possible locations for divisional charts
    divisional_charts = (
        chart_data.get('divisional_charts') or 
        chart_data.get('vargas') or 
        chart_data.get('varga_charts') or
        {}
    )
    
    # If divisional charts are in AllVargaPositions format (from VedicEngine)
    if divisional_charts and hasattr(list(divisional_charts.values())[0], 'get_position'):
        # Convert from AllVargaPositions to simple dict
        converted_charts = {}
        
        for chart_type in ['D2', 'D3', 'D4', 'D7', 'D9', 'D10', 'D12', 'D16', 'D20', 'D24', 'D27', 'D30', 'D40', 'D45', 'D60']:
            chart_planets = {}
            
            for planet_name, varga_positions in divisional_charts.items():
                try:
                    from src.engines.vedic.vedic_constants import VargaChart
                    varga_enum = getattr(VargaChart, chart_type, None)
                    
                    if varga_enum:
                        position = varga_positions.get_position(varga_enum)
                        if position:
                            chart_planets[planet_name] = position.rashi.name
                except:
                    pass
            
            if chart_planets:
                converted_charts[chart_type] = {
                    "lagna": "Unknown",  # TODO: Calculate divisional lagna
                    "planets": chart_planets
                }
        
        # Add all converted charts
        validation_chart.update(converted_charts)
    
    # If divisional charts are already in simple dict format
    elif divisional_charts and isinstance(divisional_charts, dict):
        for chart_name, chart_content in divisional_charts.items():
            if isinstance(chart_content, dict) and 'planets' in chart_content:
                validation_chart[chart_name] = chart_content
            elif isinstance(chart_content, dict):
                # Try to extract planets
                validation_chart[chart_name] = {
                    "lagna": chart_content.get('lagna', 'Unknown'),
                    "planets": chart_content.get('planets', chart_content)
                }
    
    # CRITICAL: Ensure D9 is present (most important for marriage)
    if 'D9' not in validation_chart or not validation_chart['D9'].get('planets'):
        # Try alternate locations on the original chart payload
        d9_data = (
            chart_data.get('D9') or
            chart_data.get('navamsa') or
            chart_data.get('Navamsa')
        )
        
        if d9_data:
            validation_chart['D9'] = {
                "lagna": d9_data.get('lagna', 'Unknown'),
                "planets": d9_data.get('planets', {})
            }
        else:
            # Still not found - mark as unavailable
            validation_chart['D9'] = {
                "lagna": "Unknown",
                "planets": {}
            }

    # Many validation rules also look for an explicit "navamsa" key, not just "D9".
    # Mirror the D9 chart into a simple "navamsa" structure so both styles are satisfied.
    if 'D9' in validation_chart and validation_chart['D9'].get('planets'):
        validation_chart['navamsa'] = {
            "lagna": validation_chart['D9'].get('lagna', 'Unknown'),
            "planets": validation_chart['D9'].get('planets', {}),
        }
    
    # =========================================================================
    # 3. YOGAS (Auspicious/Inauspicious Combinations)
    # =========================================================================
    yogas = chart_data.get('yogas', chart_data.get('yoga_analysis', {}))
    
    if yogas:
        validation_chart['yogas'] = yogas
    else:
        validation_chart['yogas'] = {
            'raja_yogas': [],
            'dhana_yogas': [],
            'mahapurusha_yogas': [],
            'other_yogas': []
        }
    
    # =========================================================================
    # 4. PLANETARY STRENGTHS (Shadbala, Ashtakavarga, etc.)
    # =========================================================================
    strengths = (
        chart_data.get('planetary_strengths') or
        chart_data.get('shadbala') or
        chart_data.get('strengths') or
        {}
    )
    
    if strengths:
        validation_chart['planetary_strengths'] = strengths
    
    # =========================================================================
    # 5. DASHA PERIODS (WITH DATES) - FIXED FOR NULL SAFETY
    # =========================================================================
    # CRITICAL FIX: Safe null handling - dasha_data can be None if calculation fails
    safe_dasha = dasha_data or {}
    
    validation_chart['dasha'] = {
        "mahadasha": {
            "planet": safe_dasha.get('mahadasha', {}).get('planet', 'Unknown'),
            "start_date": safe_dasha.get('mahadasha', {}).get('start_date', 'Unknown'),
            "end_date": safe_dasha.get('mahadasha', {}).get('end_date', 'Unknown'),
            "balance_years": safe_dasha.get('mahadasha', {}).get('balance_years', 'Unknown')
        },
        "antardasha": {
            "planet": safe_dasha.get('antardasha', {}).get('planet', 'Unknown'),
            "start_date": safe_dasha.get('antardasha', {}).get('start_date', 'Unknown'),
            "end_date": safe_dasha.get('antardasha', {}).get('end_date', 'Unknown')
        },
        "pratyantardasha": {
            "planet": safe_dasha.get('pratyantardasha', {}).get('planet', 'Unknown'),
            "start_date": safe_dasha.get('pratyantardasha', {}).get('start_date', 'Unknown'),
            "end_date": safe_dasha.get('pratyantardasha', {}).get('end_date', 'Unknown')
        },
        "dasha_sequence": safe_dasha.get('dasha_sequence', 'Unknown'),
        "calculation_details": safe_dasha.get('calculation_details', {})
    }
    
    # =========================================================================
    # 6. CURRENT TRANSITS - FIXED FOR NULL SAFETY
    # =========================================================================
    # CRITICAL FIX: Safe null handling - transit_data can be None
    safe_transit = transit_data or {}
    validation_chart['transits'] = {}
    
    for planet_name, transit_info in safe_transit.get('transits', {}).items():
        if isinstance(transit_info, str):
            # Simple rashi name
            validation_chart['transits'][planet_name] = {
                "rashi": transit_info,
                "house": None,
                "nakshatra": None
            }
        elif isinstance(transit_info, dict):
            # Detailed transit info
            validation_chart['transits'][planet_name] = {
                "rashi": transit_info.get('rashi', 'Unknown'),
                "house": transit_info.get('house'),
                "nakshatra": transit_info.get('nakshatra'),
                "degree": transit_info.get('degree')
            }
    
    # Add transit date
    validation_chart['transit_date'] = safe_transit.get('date', safe_transit.get('calculation_date'))
    
    # =========================================================================
    # 7. ASPECTS (Vedic & Western)
    # =========================================================================
    aspects = chart_data.get('aspects', chart_data.get('planetary_aspects', {}))
    if aspects:
        validation_chart['aspects'] = aspects
    
    # =========================================================================
    # 8. HOUSE LORDSHIPS
    # =========================================================================
    house_lords = chart_data.get('house_lords', chart_data.get('bhava_lords', {}))
    if house_lords:
        validation_chart['house_lords'] = house_lords
    
    # =========================================================================
    # 9. ADDITIONAL METADATA
    # =========================================================================
    validation_chart['metadata'] = {
        'ayanamsa': chart_data.get('ayanamsa', 'Lahiri'),
        'calculation_date': chart_data.get('calculation_date'),
        'timezone': chart_data.get('timezone'),
        'latitude': chart_data.get('latitude'),
        'longitude': chart_data.get('longitude')
    }
    
    return validation_chart


# ============================================================================
# SOFT HALT HANDLING (4-TIER SYSTEM)
# ============================================================================

def should_hard_halt(validation_strength: float, critical_failures: List) -> bool:
    """
    Determine if prediction should be completely refused (hard halt).
    
    Hard halt only for EXTREME cases:
    - Strength < 2.0 AND multiple critical failures
    """
    if validation_strength < 2.0 and len(critical_failures) >= 3:
        return True
    return False


def get_response_framing(validation_strength: float) -> Dict[str, str]:
    """
    Get response framing instructions based on validation strength.
    
    Returns dict with: tone, phrases, disclaimer_level
    """
    if validation_strength >= 8.0:
        return {
            'tone': 'confident and optimistic',
            'phrases': 'The chart clearly indicates..., Strong potential for..., Favorable alignment suggests...',
            'disclaimer_level': 'none',
            'proceed': True
        }
    
    elif validation_strength >= 6.0:
        return {
            'tone': 'balanced and realistic',
            'phrases': 'The chart suggests..., There are indications of..., With effort, you may...',
            'disclaimer_level': 'light',
            'proceed': True
        }
    
    elif validation_strength >= 4.0:
        return {
            'tone': 'cautious with emphasis on free will',
            'phrases': 'The chart shows mixed signals..., This area may require extra effort..., Consider this as one possibility...',
            'disclaimer_level': 'moderate',
            'proceed': True
        }
    
    elif validation_strength >= 2.0:
        return {
            'tone': 'focus on growth opportunities',
            'phrases': 'The chart presents challenges in this area..., This may not be the primary focus..., Alternative paths might be...',
            'disclaimer_level': 'strong',
            'proceed': True  # Soft warning, don't halt
        }
    
    else:  # < 2.0
        return {
            'tone': 'compassionate refusal',
            'phrases': '',
            'disclaimer_level': 'halt',
            'proceed': False  # Hard halt
        }


def build_halt_response(validation_result: Dict, user_profile: Dict, language: str = "en") -> str:
    """Build compassionate refusal for hard halt cases."""
    
    user_name = user_profile.get('name', 'Friend')
    query_type = validation_result.get('query_type', 'this area')
    critical_failures = validation_result.get('critical_failures', [])
    
    explanation_parts = []
    for failure in critical_failures[:2]:
        # Handle both dict and RuleResult object
        if isinstance(failure, dict):
            classical_ref = failure.get('classical_ref', '')
            reason = failure.get('reason', '')
        else:
            # RuleResult dataclass - use attributes
            classical_ref = getattr(failure, 'classical_ref', '')
            reason = getattr(failure, 'reason', '')
        
        if classical_ref:
            explanation_parts.append(f"According to {classical_ref}, {reason.lower()}")
        else:
            explanation_parts.append(reason)
    
    explanation_text = ". ".join(explanation_parts) if explanation_parts else \
        "the planetary configurations do not strongly support this prediction"
    
    reframe_suggestions = {
        'marriage': "I'd be happy to discuss relationship growth, self-development, or understanding your partnership needs.",
        'career': "Let's explore skill development, alternative career paths, or opportunities that align with your strengths.",
        'finance': "We can focus on financial stability, smart money habits, or gradual wealth building.",
        'health': "I can offer insights on wellness maintenance, preventive care timing, or lifestyle adjustments.",
        'children': "We might explore nurturing energy, family planning timing, or understanding your parental potential."
    }
    
    reframe_text = reframe_suggestions.get(query_type, 
        "I'd be happy to explore alternative questions that align better with your chart's strengths.")
    
    return f"""Namaste, {user_name}.

After careful validation of your birth chart, I find that {explanation_text}.

**Why I cannot make this prediction:**
The validation process identified significant gaps in the essential planetary configurations needed for {query_type} predictions according to classical texts.

**This is not about your worth:**
Every chart has unique strengths. The absence of certain yogas in one area often means special gifts in another.

**What we can explore instead:**
{reframe_text}

Would you like to explore any of these alternative perspectives?"""


def build_validation_disclaimer(validation_strength: float, query_type: str, critical_failures: List) -> str:
    """Build disclaimer text for weak charts (soft warnings)."""
    
    if validation_strength >= 6.0:
        return ""  # No disclaimer needed
    
    if validation_strength >= 4.0:
        # Moderate disclaimer
        disclaimer = f"\n\n**Astrological Note:** Your chart shows moderate indicators for {query_type} "
        disclaimer += f"(validation strength: {validation_strength:.1f}/10). "
        disclaimer += "This prediction should be interpreted as tendencies rather than certainties. "
        disclaimer += "Outcomes depend heavily on free will and personal effort."
        return disclaimer
    
    # Strong disclaimer for 2.0-3.9
    disclaimer = f"\n\n**Important Caveat:** Your chart shows relatively weak support for {query_type} "
    disclaimer += f"(validation strength: {validation_strength:.1f}/10). "
    
    if critical_failures:
        disclaimer += "Classical rules indicate:\n"
        for f in critical_failures[:2]:
            # Handle both dict and RuleResult object
            if isinstance(f, dict):
                rule_name = f.get('rule_name', 'Unknown rule')
                reason = f.get('reason', '')
            else:
                # RuleResult dataclass - use attributes
                rule_name = getattr(f, 'rule_name', 'Unknown rule')
                reason = getattr(f, 'reason', '')
            disclaimer += f"- {rule_name}: {reason}\n"
    
    disclaimer += "\nThis prediction is exploratory. Consider focusing on areas where your chart shows stronger potential."
    return disclaimer


# ============================================================================
# VALIDATION RESULT FORMATTING FOR PROMPT INJECTION
# ============================================================================

def format_validation_for_prompt(validation_result: Dict) -> str:
    """Format validation results for LLM prompt injection."""
    
    if not validation_result:
        return ""
    
    query_type = validation_result.get('query_type', 'unknown')
    strength = validation_result.get('overall_strength', 5.0)
    critical_failures = validation_result.get('critical_failures', [])
    
    # Get framing instructions
    framing = get_response_framing(strength)
    
    # Build critical failures list
    failures_text = "None - all critical rules passed"
    if critical_failures:
        failures_lines = []
        for f in critical_failures[:3]:
            # Handle both dict and RuleResult object
            if isinstance(f, dict):
                rule_id = f.get('rule_id', 'Unknown')
                rule_name = f.get('rule_name', 'Unknown')
                reason = f.get('reason', '')
                classical_ref = f.get('classical_ref', '')
            else:
                # RuleResult dataclass - use attributes
                rule_id = getattr(f, 'rule_id', 'Unknown')
                rule_name = getattr(f, 'rule_name', 'Unknown')
                reason = getattr(f, 'reason', '')
                classical_ref = getattr(f, 'classical_ref', '')
            
            ref_text = f" ({classical_ref})" if classical_ref else ""
            failures_lines.append(f"[{rule_id}] {rule_name}{ref_text}\n       -> {reason}")
        
        failures_text = "\n   ".join(failures_lines)
    
    validation_context = f"""
### VALIDATION ANALYSIS

**Query Type:** {query_type.title()}
**Chart Strength:** {strength:.1f}/10
**Validation Verdict:** {"[OK] SUPPORTED" if strength >= 6.0 else "[WARN] WEAK SUPPORT" if strength >= 4.0 else "[FAIL] VERY WEAK"}

**Critical Rule Violations:**
   {failures_text}

**RESPONSE FRAMING INSTRUCTION:**
Tone: {framing['tone']}
Use phrases like: {framing['phrases']}
Disclaimer level: {framing['disclaimer_level']}

**GROUNDING REQUIREMENT:**
Your response MUST align with the {strength:.1f}/10 strength score. 
{"Be confident and optimistic." if strength >= 8.0 else ""}
{"Be balanced - acknowledge both potential and challenges." if 6.0 <= strength < 8.0 else ""}
{"Be cautious - emphasize free will and effort required." if 4.0 <= strength < 6.0 else ""}
{"Focus on growth opportunities, not prediction of success." if strength < 4.0 else ""}
"""
    
    return validation_context


# ============================================================================
# TESTING
# ============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("VALIDATION HELPERS TEST")
    print("=" * 70)
    
    # Test query type detection
    test_queries = [
        "When will I get married?",
        "What about my career growth?",
        "Will I have children soon?",
        "Tell me about Jupiter in 7th house",  # General
        "My job and marriage both seem stuck"  # Ambiguous - needs LLM
    ]
    
    for q in test_queries:
        qtype, conf = detect_query_type_patterns(q)
        print(f"\n'{q}'")
        print(f"  Type: {qtype}, Confidence: {conf:.2f}")
        print(f"  Would use LLM: {conf < 0.7 and qtype != 'general'}")
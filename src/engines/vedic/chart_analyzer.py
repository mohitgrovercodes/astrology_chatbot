# src/engines/vedic/chart_analyzer.py
"""
Enhanced Chart Analyzer - Extracts classical factors from VedicChart

Provides:
- Planetary dignities (exalted/debilitated/own/friend/enemy/neutral)
- House lordships (which planet rules which house)
- Planetary aspects (Vedic drishti)
- Combustion check
- Retrograde status
- Simplified strength scoring

This bridges VedicEngine calculations with LLM-readable structured data.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass


@dataclass
class PlanetaryDignity:
    """Dignity status of a planet in a sign."""
    planet: str
    sign: str
    dignity: str  # exalted | debilitated | own | friend | neutral | enemy
    degrees: float
    is_deep: bool  # Deep exaltation/debilitation (within 5° of exact point)


@dataclass
class HouseLordship:
    """House ownership information."""
    house_number: int
    sign: str
    lord: str
    lord_placement_house: int
    lord_placement_sign: str
    lord_dignity: str


@dataclass
class PlanetaryAspect:
    """Aspect from one planet to houses/planets."""
    aspecting_planet: str
    aspecting_from_house: int
    aspected_houses: List[int]
    aspect_type: str  # full | special_5th | special_7th | special_9th | special_3rd | special_10th


# Classical dignity tables
EXALTATION_SIGNS = {
    'SUN': 'Aries', 'MOON': 'Taurus', 'MARS': 'Capricorn', 
    'MERCURY': 'Virgo', 'JUPITER': 'Cancer', 'VENUS': 'Pisces', 
    'SATURN': 'Libra', 'RAHU': 'Taurus', 'KETU': 'Scorpio'
}

DEBILITATION_SIGNS = {
    'SUN': 'Libra', 'MOON': 'Scorpio', 'MARS': 'Cancer',
    'MERCURY': 'Pisces', 'JUPITER': 'Capricorn', 'VENUS': 'Virgo',
    'SATURN': 'Aries', 'RAHU': 'Scorpio', 'KETU': 'Taurus'
}

# Deep exaltation/debilitation degrees
DEEP_EXALTATION_DEGREES = {
    'SUN': 10, 'MOON': 3, 'MARS': 28, 'MERCURY': 15,
    'JUPITER': 5, 'VENUS': 27, 'SATURN': 20
}

OWN_SIGNS = {
    'SUN': ['Leo'],
    'MOON': ['Cancer'],
    'MARS': ['Aries', 'Scorpio'],
    'MERCURY': ['Gemini', 'Virgo'],
    'JUPITER': ['Sagittarius', 'Pisces'],
    'VENUS': ['Taurus', 'Libra'],
    'SATURN': ['Capricorn', 'Aquarius'],
    'RAHU': [],  # No ownership
    'KETU': []   # No ownership
}

# Natural friendships (simplified — full table is complex)
NATURAL_FRIENDS = {
    'SUN': ['MOON', 'MARS', 'JUPITER'],
    'MOON': ['SUN', 'MERCURY'],
    'MARS': ['SUN', 'MOON', 'JUPITER'],
    'MERCURY': ['SUN', 'VENUS'],
    'JUPITER': ['SUN', 'MOON', 'MARS'],
    'VENUS': ['MERCURY', 'SATURN'],
    'SATURN': ['MERCURY', 'VENUS'],
}

NATURAL_ENEMIES = {
    'SUN': ['VENUS', 'SATURN'],
    'MOON': ['NONE'],
    'MARS': ['MERCURY'],
    'MERCURY': ['MOON'],
    'JUPITER': ['MERCURY', 'VENUS'],
    'VENUS': ['SUN', 'MOON'],
    'SATURN': ['SUN', 'MOON', 'MARS'],
}

# Sign lordships (which planet rules which sign)
SIGN_LORDS = {
    'Aries': 'MARS', 'Taurus': 'VENUS', 'Gemini': 'MERCURY',
    'Cancer': 'MOON', 'Leo': 'SUN', 'Virgo': 'MERCURY',
    'Libra': 'VENUS', 'Scorpio': 'MARS', 'Sagittarius': 'JUPITER',
    'Capricorn': 'SATURN', 'Aquarius': 'SATURN', 'Pisces': 'JUPITER'
}

# Sanskrit to English sign name mapping
SANSKRIT_TO_ENGLISH = {
    'Mesha': 'Aries', 'Vrishabha': 'Taurus', 'Mithuna': 'Gemini',
    'Karka': 'Cancer', 'Simha': 'Leo', 'Kanya': 'Virgo',
    'Tula': 'Libra', 'Vrischika': 'Scorpio', 'Dhanu': 'Sagittarius',
    'Makara': 'Capricorn', 'Kumbha': 'Aquarius', 'Meena': 'Pisces'
}

def normalize_sign_name(sign: str) -> str:
    """Convert Sanskrit sign names to English if needed."""
    if not sign:
        return sign
    # Already English
    if sign in ['Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo',
                'Libra', 'Scorpio', 'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces']:
        return sign
    # Convert from Sanskrit
    return SANSKRIT_TO_ENGLISH.get(sign, sign)


class ChartAnalyzer:
    """
    Analyzes a Vedic chart to extract classical factors.
    
    Works with both VedicChart objects and serialized chart dicts.
    """
    
    def __init__(self):
        pass
    
    # ──────────────────────────────────────────────────────────────────────
    # DIGNITY ANALYSIS
    # ──────────────────────────────────────────────────────────────────────
    
    def get_planetary_dignities(self, chart_data: Dict) -> List[PlanetaryDignity]:
        """
        Calculate dignity status for all planets.
        
        Returns list of PlanetaryDignity objects with:
        - exalted / debilitated / own / friend / neutral / enemy
        - is_deep flag for deep exaltation/debilitation
        """
        dignities = []
        planets = chart_data.get('planets', {})
        
        for planet_name, planet_data in planets.items():
            if planet_name in ['RAHU', 'KETU']:
                continue  # Skip nodes for dignity (different rules)
            
            sign = planet_data.get('sign') or planet_data.get('rashi')
            degrees = planet_data.get('degree') or planet_data.get('degrees', 0.0)
            
            # Normalize sign name
            sign = normalize_sign_name(sign)
            
            dignity_status = self._calculate_dignity(planet_name, sign, degrees)
            is_deep = self._is_deep_dignity(planet_name, sign, degrees)
            
            dignities.append(PlanetaryDignity(
                planet=planet_name,
                sign=sign,
                dignity=dignity_status,
                degrees=degrees,
                is_deep=is_deep
            ))
        
        return dignities
    
    def _calculate_dignity(self, planet: str, sign: str, degrees: float) -> str:
        """Determine dignity status of a planet in a sign."""
        # Exaltation
        if EXALTATION_SIGNS.get(planet) == sign:
            return "exalted"
        
        # Debilitation
        if DEBILITATION_SIGNS.get(planet) == sign:
            return "debilitated"
        
        # Own sign
        if sign in OWN_SIGNS.get(planet, []):
            return "own"
        
        # Friend/enemy/neutral (simplified — check sign lord)
        sign_lord = SIGN_LORDS.get(sign)
        if not sign_lord:
            return "neutral"
        
        if sign_lord in NATURAL_FRIENDS.get(planet, []):
            return "friend"
        elif sign_lord in NATURAL_ENEMIES.get(planet, []):
            return "enemy"
        else:
            return "neutral"
    
    def _is_deep_dignity(self, planet: str, sign: str, degrees: float) -> bool:
        """Check if planet is within 5° of deep exaltation/debilitation point."""
        if planet in DEEP_EXALTATION_DEGREES:
            deep_degree = DEEP_EXALTATION_DEGREES[planet]
            
            # Check if in exaltation/debilitation sign
            if EXALTATION_SIGNS.get(planet) == sign or DEBILITATION_SIGNS.get(planet) == sign:
                # Within 5° of exact point
                if abs(degrees - deep_degree) <= 5.0:
                    return True
        
        return False
    
    # ──────────────────────────────────────────────────────────────────────
    # HOUSE LORDSHIP ANALYSIS
    # ──────────────────────────────────────────────────────────────────────
    
    def get_house_lordships(self, chart_data: Dict) -> List[HouseLordship]:
        """
        Calculate which planet rules each house and where that lord is placed.
        
        Critical for analysis: "7th lord in 10th house" type factors.
        """
        lordships = []
        
        # Get ascendant sign to determine house signs
        lagna_data = chart_data.get('lagna') or chart_data.get('ascendant', {})
        lagna_sign = lagna_data.get('sign') or lagna_data.get('rashi')
        
        if not lagna_sign:
            return []
        
        # Normalize sign name (Sanskrit → English)
        lagna_sign = normalize_sign_name(lagna_sign)
        
        # Calculate sign for each house (sequential from ascendant)
        signs_cycle = [
            'Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo',
            'Libra', 'Scorpio', 'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces'
        ]
        lagna_index = signs_cycle.index(lagna_sign)
        
        planets = chart_data.get('planets', {})
        
        for house_num in range(1, 13):
            house_sign = signs_cycle[(lagna_index + house_num - 1) % 12]
            lord_planet = SIGN_LORDS.get(house_sign)
            
            # Find where this lord is placed
            lord_placement_house = None
            lord_placement_sign = None
            lord_dignity = "unknown"
            
            if lord_planet and lord_planet in planets:
                lord_data = planets[lord_planet]
                lord_placement_house = lord_data.get('house')
                lord_placement_sign = lord_data.get('sign') or lord_data.get('rashi')
                
                # Normalize sign name
                lord_placement_sign = normalize_sign_name(lord_placement_sign)
                
                # Get dignity of the lord
                lord_degrees = lord_data.get('degree') or lord_data.get('degrees', 0.0)
                lord_dignity = self._calculate_dignity(lord_planet, lord_placement_sign, lord_degrees)
            
            lordships.append(HouseLordship(
                house_number=house_num,
                sign=house_sign,
                lord=lord_planet or "Unknown",
                lord_placement_house=lord_placement_house or 0,
                lord_placement_sign=lord_placement_sign or "Unknown",
                lord_dignity=lord_dignity
            ))
        
        return lordships
    
    # ──────────────────────────────────────────────────────────────────────
    # ASPECT ANALYSIS (VEDIC DRISHTI)
    # ──────────────────────────────────────────────────────────────────────
    
    def get_planetary_aspects(self, chart_data: Dict) -> List[PlanetaryAspect]:
        """
        Calculate Vedic aspects (drishti).
        
        Rules:
        - All planets aspect 7th house from their position (opposition)
        - Mars aspects 4th, 7th, 8th houses
        - Jupiter aspects 5th, 7th, 9th houses
        - Saturn aspects 3rd, 7th, 10th houses
        """
        aspects = []
        planets = chart_data.get('planets', {})
        
        for planet_name, planet_data in planets.items():
            if planet_name in ['RAHU', 'KETU']:
                continue  # Nodes have different aspect rules
            
            from_house = planet_data.get('house')
            if not from_house:
                continue
            
            aspected = []
            aspect_type = "full"
            
            # All planets aspect 7th house from their position
            seventh_house = ((from_house + 6) % 12) or 12
            aspected.append(seventh_house)
            
            # Special aspects
            if planet_name == 'MARS':
                fourth_house = ((from_house + 3) % 12) or 12
                eighth_house = ((from_house + 7) % 12) or 12
                aspected.extend([fourth_house, eighth_house])
                aspect_type = "special_mars"
            
            elif planet_name == 'JUPITER':
                fifth_house = ((from_house + 4) % 12) or 12
                ninth_house = ((from_house + 8) % 12) or 12
                aspected.extend([fifth_house, ninth_house])
                aspect_type = "special_jupiter"
            
            elif planet_name == 'SATURN':
                third_house = ((from_house + 2) % 12) or 12
                tenth_house = ((from_house + 9) % 12) or 12
                aspected.extend([third_house, tenth_house])
                aspect_type = "special_saturn"
            
            aspects.append(PlanetaryAspect(
                aspecting_planet=planet_name,
                aspecting_from_house=from_house,
                aspected_houses=sorted(set(aspected)),
                aspect_type=aspect_type
            ))
        
        return aspects
    
    # ──────────────────────────────────────────────────────────────────────
    # COMBUSTION & RETROGRADE
    # ──────────────────────────────────────────────────────────────────────
    
    def check_combustion(self, chart_data: Dict) -> Dict[str, bool]:
        """
        Check which planets are combust (too close to Sun).
        
        Combustion ranges (degrees from Sun):
        - Moon: 12°, Mars: 17°, Mercury: 14° (12° if retrograde)
        - Jupiter: 11°, Venus: 10° (8° if retrograde), Saturn: 15°
        """
        combustion_limits = {
            'MOON': 12, 'MARS': 17, 'MERCURY': 14,
            'JUPITER': 11, 'VENUS': 10, 'SATURN': 15
        }
        
        planets = chart_data.get('planets', {})
        sun_data = planets.get('SUN', {})
        sun_long = sun_data.get('longitude') or self._sign_degree_to_longitude(
            sun_data.get('sign') or sun_data.get('rashi'),
            sun_data.get('degree') or sun_data.get('degrees', 0)
        )
        
        combustion_status = {}
        
        for planet_name, limit in combustion_limits.items():
            if planet_name not in planets:
                continue
            
            planet_data = planets[planet_name]
            planet_long = planet_data.get('longitude') or self._sign_degree_to_longitude(
                planet_data.get('sign') or planet_data.get('rashi'),
                planet_data.get('degree') or planet_data.get('degrees', 0)
            )
            
            # Calculate angular distance
            diff = abs(planet_long - sun_long)
            if diff > 180:
                diff = 360 - diff
            
            # Adjust for retrograde
            is_retro = planet_data.get('is_retrograde', False)
            if planet_name == 'MERCURY' and is_retro:
                limit = 12
            elif planet_name == 'VENUS' and is_retro:
                limit = 8
            
            combustion_status[planet_name] = (diff <= limit)
        
        return combustion_status
    
    def get_retrograde_planets(self, chart_data: Dict) -> List[str]:
        """Return list of retrograde planets."""
        retrograde = []
        planets = chart_data.get('planets', {})
        
        for planet_name, planet_data in planets.items():
            if planet_name in ['SUN', 'MOON', 'RAHU', 'KETU']:
                continue  # These never go retrograde
            
            if planet_data.get('is_retrograde', False):
                retrograde.append(planet_name)
        
        return retrograde
    
    # ──────────────────────────────────────────────────────────────────────
    # STRENGTH SCORING (SIMPLIFIED)
    # ──────────────────────────────────────────────────────────────────────
    
    def calculate_simplified_strengths(self, chart_data: Dict) -> Dict[str, float]:
        """
        Simplified strength scoring (0-10 scale).
        
        Based on:
        - Dignity (exalted=10, own=8, friend=6, neutral=5, enemy=3, debilitated=2)
        - Combustion (-3 if combust)
        - Retrograde (+1 for benefics, -1 for malefics)
        """
        strengths = {}
        
        dignities = self.get_planetary_dignities(chart_data)
        combustion = self.check_combustion(chart_data)
        retrograde = self.get_retrograde_planets(chart_data)
        
        benefics = ['JUPITER', 'VENUS', 'MERCURY', 'MOON']
        
        for dignity in dignities:
            # Base strength from dignity
            base = {
                'exalted': 10, 'own': 8, 'friend': 6,
                'neutral': 5, 'enemy': 3, 'debilitated': 2
            }.get(dignity.dignity, 5)
            
            # Deep exaltation/debilitation bonus/penalty
            if dignity.is_deep:
                if dignity.dignity == 'exalted':
                    base += 2  # Max 12 for deep exaltation
                elif dignity.dignity == 'debilitated':
                    base -= 2  # Min 0 for deep debilitation
            
            # Combustion penalty
            if combustion.get(dignity.planet, False):
                base -= 3
            
            # Retrograde effect
            if dignity.planet in retrograde:
                if dignity.planet in benefics:
                    base += 1  # Retrograde benefics gain strength
                else:
                    base -= 1  # Retrograde malefics lose strength
            
            # Clamp to 0-10 range
            strengths[dignity.planet] = max(0, min(10, base))
        
        return strengths
    
    # ──────────────────────────────────────────────────────────────────────
    # HELPERS
    # ──────────────────────────────────────────────────────────────────────
    
    def _sign_degree_to_longitude(self, sign: str, degree: float) -> float:
        """Convert sign + degree to absolute longitude (0-360)."""
        signs = [
            'Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo',
            'Libra', 'Scorpio', 'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces'
        ]
        if sign not in signs:
            return 0.0
        
        sign_index = signs.index(sign)
        return (sign_index * 30) + degree
    
    # ──────────────────────────────────────────────────────────────────────
    # UNIFIED ANALYSIS
    # ──────────────────────────────────────────────────────────────────────
    
    def analyze_chart(self, chart_data: Dict) -> Dict[str, Any]:
        """
        Complete chart analysis — returns all factors in one structured dict.
        
        This is what gets passed to the LLM or synthesis engine.
        """
        return {
            "dignities": [
                {
                    "planet": d.planet,
                    "sign": d.sign,
                    "dignity": d.dignity,
                    "is_deep": d.is_deep,
                    "degrees": d.degrees
                }
                for d in self.get_planetary_dignities(chart_data)
            ],
            "house_lords": [
                {
                    "house": hl.house_number,
                    "sign": hl.sign,
                    "lord": hl.lord,
                    "lord_in_house": hl.lord_placement_house,
                    "lord_in_sign": hl.lord_placement_sign,
                    "lord_dignity": hl.lord_dignity
                }
                for hl in self.get_house_lordships(chart_data)
            ],
            "aspects": [
                {
                    "planet": asp.aspecting_planet,
                    "from_house": asp.aspecting_from_house,
                    "aspects_houses": asp.aspected_houses,
                    "type": asp.aspect_type
                }
                for asp in self.get_planetary_aspects(chart_data)
            ],
            "combustion": self.check_combustion(chart_data),
            "retrograde": self.get_retrograde_planets(chart_data),
            "strengths": self.calculate_simplified_strengths(chart_data)
        }


# ──────────────────────────────────────────────────────────────────────────
# CONVENIENCE FUNCTIONS
# ──────────────────────────────────────────────────────────────────────────

def analyze_chart(chart_data: Dict) -> Dict[str, Any]:
    """Convenience function — analyzes chart and returns structured data."""
    analyzer = ChartAnalyzer()
    return analyzer.analyze_chart(chart_data)


def get_house_lord_summary(chart_data: Dict, house_num: int) -> str:
    """Get human-readable summary of a house lord's status."""
    analyzer = ChartAnalyzer()
    lordships = analyzer.get_house_lordships(chart_data)
    
    for hl in lordships:
        if hl.house_number == house_num:
            return (
                f"{hl.sign} ruled by {hl.lord}, "
                f"placed in {hl.lord_placement_sign} in house {hl.lord_placement_house} "
                f"({hl.lord_dignity})"
            )
    
    return f"House {house_num} analysis unavailable"


if __name__ == "__main__":
    # Test with sample chart
    sample = {
        "lagna": {"sign": "Aries", "degree": 15.23},
        "planets": {
            "SUN": {"sign": "Taurus", "house": 2, "degree": 12.45, "is_retrograde": False},
            "MOON": {"sign": "Cancer", "house": 4, "degree": 8.23, "is_retrograde": False},
            "MARS": {"sign": "Scorpio", "house": 8, "degree": 22.10, "is_retrograde": False},
            "MERCURY": {"sign": "Taurus", "house": 2, "degree": 20.10, "is_retrograde": False},
            "JUPITER": {"sign": "Cancer", "house": 4, "degree": 5.30, "is_retrograde": False},
            "VENUS": {"sign": "Aries", "house": 1, "degree": 28.50, "is_retrograde": False},
            "SATURN": {"sign": "Pisces", "house": 12, "degree": 9.78, "is_retrograde": False},
        }
    }
    
    analysis = analyze_chart(sample)
    
    print("=== CHART ANALYSIS ===\n")
    print("Dignities:")
    for d in analysis['dignities']:
        deep = " (DEEP)" if d['is_deep'] else ""
        print(f"  {d['planet']}: {d['dignity']}{deep} in {d['sign']}")
    
    print("\nHouse Lords:")
    for hl in analysis['house_lords'][:7]:  # First 7 houses
        print(f"  H{hl['house']}: {hl['sign']} ruled by {hl['lord']} "
              f"(placed in H{hl['lord_in_house']}, {hl['lord_dignity']})")
    
    print("\nStrengths:")
    for planet, strength in analysis['strengths'].items():
        print(f"  {planet}: {strength:.1f}/10")
    
    print("\nCombustion:")
    for planet, is_combust in analysis['combustion'].items():
        if is_combust:
            print(f"  {planet}: COMBUST")
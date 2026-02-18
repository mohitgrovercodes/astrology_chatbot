# src/engines/vedic/vedic_constants.py
# src\engines\vedic\vedic_constants.py
"""
Vedic Astrology Constants
=========================

This module contains all the constant data used in Vedic astrological calculations.
These are the fundamental reference tables that don't change - they're the "lookup
tables" of Jyotish.

Why Separate Constants?
-----------------------
1. Single source of truth - all calculations reference the same data
2. Easy to verify against classical texts (BPHS, Phaladeepika, etc.)
3. No risk of typos in multiple places
4. Clear separation of DATA from LOGIC

These constants are derived from classical texts, primarily:
- Brihat Parashara Hora Shastra (BPHS)
- Phaladeepika
- Saravali
- Jataka Parijata
"""

from enum import IntEnum, Enum
from typing import NamedTuple
from src.engines.core.celestial_bodies import CelestialBody
import swisseph as swe


class Ayanamsa(IntEnum):
    """
    Ayanamsa (precession correction) systems for sidereal calculations.
    
    The ayanamsa is the angular difference between the tropical and sidereal
    zodiacs. Different traditions use different ayanamsas, which is why
    Vedic astrologers may give slightly different positions.
    
    Common values (as of 2024):
    - LAHIRI: ~24.17Â° (most popular in India, used by Indian government)
    - RAMAN: ~22.47Â° (created by B.V. Raman)
    - KRISHNAMURTI: ~23.76Â° (KP system)
    - FAGAN_BRADLEY: ~24.85Â° (Western sidereal)
    """
    LAHIRI = swe.SIDM_LAHIRI                    # Official Indian standard
    RAMAN = swe.SIDM_RAMAN                      # B.V. Raman's ayanamsa
    KRISHNAMURTI = swe.SIDM_KRISHNAMURTI        # KP Astrology
    FAGAN_BRADLEY = swe.SIDM_FAGAN_BRADLEY      # Western sidereal
    TRUE_CITRA = swe.SIDM_TRUE_CITRA            # Citra at 0Â° Libra
    TRUE_REVATI = swe.SIDM_TRUE_REVATI          # Revati at 29Â°50' Pisces
    TRUE_PUSHYA = swe.SIDM_TRUE_PUSHYA          # Pushya at 16Â° Cancer
    YUKTESHWAR = swe.SIDM_YUKTESHWAR            # Sri Yukteshwar
    JN_BHASIN = swe.SIDM_JN_BHASIN              # J.N. Bhasin




# =============================================================================
# RASHI (ZODIAC SIGNS) CONSTANTS
# =============================================================================

class Rashi(IntEnum):
    """
    The 12 Rashis (zodiac signs) in Vedic astrology.
    
    Index starts at 0 for programmatic convenience, but traditional
    numbering starts at 1 (Mesha = 1). Use the .number property
    for traditional numbering.
    """
    MESHA = 0       # Aries
    VRISHABHA = 1   # Taurus
    MITHUNA = 2     # Gemini
    KARKA = 3       # Cancer
    SIMHA = 4       # Leo
    KANYA = 5       # Virgo
    TULA = 6        # Libra
    VRISCHIKA = 7   # Scorpio
    DHANU = 8       # Sagittarius
    MAKARA = 9      # Capricorn
    KUMBHA = 10     # Aquarius
    MEENA = 11      # Pisces
    
    @property
    def number(self) -> int:
        """Traditional 1-based numbering."""
        return self.value + 1
    
    @property
    def english_name(self) -> str:
        """English name of the sign."""
        return RASHI_ENGLISH_NAMES[self.value]
    
    @property 
    def lord(self) -> CelestialBody:
        """The planetary ruler of this sign."""
        return RASHI_LORDS[self.value]


RASHI_ENGLISH_NAMES: tuple[str, ...] = (
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"
)

RASHI_SANSKRIT_NAMES: tuple[str, ...] = (
    "Mesha", "Vrishabha", "Mithuna", "Karka", "Simha", "Kanya",
    "Tula", "Vrischika", "Dhanu", "Makara", "Kumbha", "Meena"
)

# Planetary lordship of signs (0-indexed by sign)
RASHI_LORDS: tuple[CelestialBody, ...] = (
    CelestialBody.MARS,      # Mesha (Aries)
    CelestialBody.VENUS,     # Vrishabha (Taurus)
    CelestialBody.MERCURY,   # Mithuna (Gemini)
    CelestialBody.MOON,      # Karka (Cancer)
    CelestialBody.SUN,       # Simha (Leo)
    CelestialBody.MERCURY,   # Kanya (Virgo)
    CelestialBody.VENUS,     # Tula (Libra)
    CelestialBody.MARS,      # Vrischika (Scorpio)
    CelestialBody.JUPITER,   # Dhanu (Sagittarius)
    CelestialBody.SATURN,    # Makara (Capricorn)
    CelestialBody.SATURN,    # Kumbha (Aquarius)
    CelestialBody.JUPITER,   # Meena (Pisces)
)

# Sign elements (Tattva)
class Tattva(Enum):
    FIRE = "fire"      # Agni
    EARTH = "earth"    # Prithvi
    AIR = "air"        # Vayu
    WATER = "water"    # Jala

RASHI_TATTVA: tuple[Tattva, ...] = (
    Tattva.FIRE,    # Mesha
    Tattva.EARTH,   # Vrishabha
    Tattva.AIR,     # Mithuna
    Tattva.WATER,   # Karka
    Tattva.FIRE,    # Simha
    Tattva.EARTH,   # Kanya
    Tattva.AIR,     # Tula
    Tattva.WATER,   # Vrischika
    Tattva.FIRE,    # Dhanu
    Tattva.EARTH,   # Makara
    Tattva.AIR,     # Kumbha
    Tattva.WATER,   # Meena
)

# Sign modalities (Chara, Sthira, Dvisvabhava)
class Modality(Enum):
    MOVABLE = "chara"        # Cardinal
    FIXED = "sthira"         # Fixed
    DUAL = "dvisvabhava"     # Mutable

RASHI_MODALITY: tuple[Modality, ...] = (
    Modality.MOVABLE,  # Mesha
    Modality.FIXED,    # Vrishabha
    Modality.DUAL,     # Mithuna
    Modality.MOVABLE,  # Karka
    Modality.FIXED,    # Simha
    Modality.DUAL,     # Kanya
    Modality.MOVABLE,  # Tula
    Modality.FIXED,    # Vrischika
    Modality.DUAL,     # Dhanu
    Modality.MOVABLE,  # Makara
    Modality.FIXED,    # Kumbha
    Modality.DUAL,     # Meena
)

# Odd/Even signs (important for various calculations)
RASHI_IS_ODD: tuple[bool, ...] = (
    True, False, True, False, True, False,
    True, False, True, False, True, False
)


# =============================================================================
# NAKSHATRA CONSTANTS
# =============================================================================

class Nakshatra(IntEnum):
    """
    The 27 Nakshatras (lunar mansions).
    
    Each Nakshatra spans 13Â°20' (13.333... degrees) of the zodiac.
    """
    ASHWINI = 0
    BHARANI = 1
    KRITTIKA = 2
    ROHINI = 3
    MRIGASHIRA = 4
    ARDRA = 5
    PUNARVASU = 6
    PUSHYA = 7
    ASHLESHA = 8
    MAGHA = 9
    PURVA_PHALGUNI = 10
    UTTARA_PHALGUNI = 11
    HASTA = 12
    CHITRA = 13
    SWATI = 14
    VISHAKHA = 15
    ANURADHA = 16
    JYESHTHA = 17
    MULA = 18
    PURVA_ASHADHA = 19
    UTTARA_ASHADHA = 20
    SHRAVANA = 21
    DHANISHTA = 22
    SHATABHISHA = 23
    PURVA_BHADRAPADA = 24
    UTTARA_BHADRAPADA = 25
    REVATI = 26
    
    @property
    def lord(self) -> CelestialBody:
        """Planetary ruler for Vimshottari Dasha."""
        return NAKSHATRA_LORDS[self.value]
    
    @property
    def start_degree(self) -> float:
        """Starting degree of this Nakshatra in the zodiac."""
        return self.value * NAKSHATRA_SPAN
    
    @property
    def end_degree(self) -> float:
        """Ending degree of this Nakshatra."""
        return (self.value + 1) * NAKSHATRA_SPAN


# Each Nakshatra spans exactly 13Â°20' = 13.333... degrees
NAKSHATRA_SPAN: float = 360.0 / 27.0  # 13.333...

# Each Pada (quarter) spans 3Â°20' = 3.333... degrees
PADA_SPAN: float = NAKSHATRA_SPAN / 4.0  # 3.333...

NAKSHATRA_NAMES: tuple[str, ...] = (
    "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra",
    "Punarvasu", "Pushya", "Ashlesha", "Magha", "Purva Phalguni", "Uttara Phalguni",
    "Hasta", "Chitra", "Swati", "Vishakha", "Anuradha", "Jyeshtha",
    "Mula", "Purva Ashadha", "Uttara Ashadha", "Shravana", "Dhanishta", "Shatabhisha",
    "Purva Bhadrapada", "Uttara Bhadrapada", "Revati"
)

# Nakshatra lords for Vimshottari Dasha (the cycle repeats 3 times across 27 nakshatras)
# Order: Ketu, Venus, Sun, Moon, Mars, Rahu, Jupiter, Saturn, Mercury (then repeats)
NAKSHATRA_LORDS: tuple[CelestialBody, ...] = (
    CelestialBody.KETU,      # Ashwini
    CelestialBody.VENUS,     # Bharani
    CelestialBody.SUN,       # Krittika
    CelestialBody.MOON,      # Rohini
    CelestialBody.MARS,      # Mrigashira
    CelestialBody.RAHU,      # Ardra
    CelestialBody.JUPITER,   # Punarvasu
    CelestialBody.SATURN,    # Pushya
    CelestialBody.MERCURY,   # Ashlesha
    CelestialBody.KETU,      # Magha
    CelestialBody.VENUS,     # Purva Phalguni
    CelestialBody.SUN,       # Uttara Phalguni
    CelestialBody.MOON,      # Hasta
    CelestialBody.MARS,      # Chitra
    CelestialBody.RAHU,      # Swati
    CelestialBody.JUPITER,   # Vishakha
    CelestialBody.SATURN,    # Anuradha
    CelestialBody.MERCURY,   # Jyeshtha
    CelestialBody.KETU,      # Mula
    CelestialBody.VENUS,     # Purva Ashadha
    CelestialBody.SUN,       # Uttara Ashadha
    CelestialBody.MOON,      # Shravana
    CelestialBody.MARS,      # Dhanishta
    CelestialBody.RAHU,      # Shatabhisha
    CelestialBody.JUPITER,   # Purva Bhadrapada
    CelestialBody.SATURN,    # Uttara Bhadrapada
    CelestialBody.MERCURY,   # Revati
)


# =============================================================================
# PLANETARY DIGNITY CONSTANTS
# =============================================================================

# Exaltation degrees (Uccha) - the exact degree where each planet is strongest
# Format: {planet: (sign_index, exact_degree_in_sign)}
EXALTATION_DEGREES: dict[CelestialBody, tuple[int, float]] = {
    CelestialBody.SUN: (Rashi.MESHA, 10.0),           # Sun exalted at 10Â° Aries
    CelestialBody.MOON: (Rashi.VRISHABHA, 3.0),       # Moon exalted at 3Â° Taurus
    CelestialBody.MARS: (Rashi.MAKARA, 28.0),         # Mars exalted at 28Â° Capricorn
    CelestialBody.MERCURY: (Rashi.KANYA, 15.0),       # Mercury exalted at 15Â° Virgo
    CelestialBody.JUPITER: (Rashi.KARKA, 5.0),        # Jupiter exalted at 5Â° Cancer
    CelestialBody.VENUS: (Rashi.MEENA, 27.0),         # Venus exalted at 27Â° Pisces
    CelestialBody.SATURN: (Rashi.TULA, 20.0),         # Saturn exalted at 20Â° Libra
    # Rahu and Ketu have disputed exaltation - using common interpretation
    CelestialBody.RAHU: (Rashi.VRISHABHA, 20.0),      # Rahu exalted in Taurus
    CelestialBody.KETU: (Rashi.VRISCHIKA, 20.0),      # Ketu exalted in Scorpio
}

# Debilitation is exactly 180Â° from exaltation
# (calculated programmatically, but we define it for clarity)
DEBILITATION_SIGNS: dict[CelestialBody, int] = {
    CelestialBody.SUN: Rashi.TULA,          # Sun debilitated in Libra
    CelestialBody.MOON: Rashi.VRISCHIKA,    # Moon debilitated in Scorpio
    CelestialBody.MARS: Rashi.KARKA,        # Mars debilitated in Cancer
    CelestialBody.MERCURY: Rashi.MEENA,     # Mercury debilitated in Pisces
    CelestialBody.JUPITER: Rashi.MAKARA,    # Jupiter debilitated in Capricorn
    CelestialBody.VENUS: Rashi.KANYA,       # Venus debilitated in Virgo
    CelestialBody.SATURN: Rashi.MESHA,      # Saturn debilitated in Aries
    CelestialBody.RAHU: Rashi.VRISCHIKA,    # Rahu debilitated in Scorpio
    CelestialBody.KETU: Rashi.VRISHABHA,    # Ketu debilitated in Taurus
}

# Mooltrikona signs and degree ranges
# Format: {planet: (sign_index, start_degree, end_degree)}
MOOLTRIKONA: dict[CelestialBody, tuple[int, float, float]] = {
    CelestialBody.SUN: (Rashi.SIMHA, 0.0, 20.0),           # Sun: Leo 0-20Â°
    CelestialBody.MOON: (Rashi.VRISHABHA, 3.0, 30.0),      # Moon: Taurus 3-30Â°
    CelestialBody.MARS: (Rashi.MESHA, 0.0, 12.0),          # Mars: Aries 0-12Â°
    CelestialBody.MERCURY: (Rashi.KANYA, 15.0, 20.0),      # Mercury: Virgo 15-20Â°
    CelestialBody.JUPITER: (Rashi.DHANU, 0.0, 10.0),       # Jupiter: Sagittarius 0-10Â°
    CelestialBody.VENUS: (Rashi.TULA, 0.0, 15.0),          # Venus: Libra 0-15Â°
    CelestialBody.SATURN: (Rashi.KUMBHA, 0.0, 20.0),       # Saturn: Aquarius 0-20Â°
}

# Own signs (Swakshetra) - where each planet owns
OWN_SIGNS: dict[CelestialBody, tuple[int, ...]] = {
    CelestialBody.SUN: (Rashi.SIMHA,),                           # Leo
    CelestialBody.MOON: (Rashi.KARKA,),                          # Cancer
    CelestialBody.MARS: (Rashi.MESHA, Rashi.VRISCHIKA),          # Aries, Scorpio
    CelestialBody.MERCURY: (Rashi.MITHUNA, Rashi.KANYA),         # Gemini, Virgo
    CelestialBody.JUPITER: (Rashi.DHANU, Rashi.MEENA),           # Sagittarius, Pisces
    CelestialBody.VENUS: (Rashi.VRISHABHA, Rashi.TULA),          # Taurus, Libra
    CelestialBody.SATURN: (Rashi.MAKARA, Rashi.KUMBHA),          # Capricorn, Aquarius
    CelestialBody.RAHU: (),                                       # Rahu has no own sign
    CelestialBody.KETU: (),                                       # Ketu has no own sign
}

# Planetary friendships (Naisargika Maitri - Natural friendships)
# These are permanent relationships based on BPHS
class Relationship(Enum):
    GREAT_FRIEND = "great_friend"    # Adhimitram
    FRIEND = "friend"                 # Mitram
    NEUTRAL = "neutral"               # Samam
    ENEMY = "enemy"                   # Shatru
    GREAT_ENEMY = "great_enemy"       # Adhishatru

# Natural friendships as per BPHS
# Format: {planet: {friend_planets}, {enemy_planets}, {neutral_planets}}
NATURAL_RELATIONSHIPS: dict[CelestialBody, dict[str, tuple[CelestialBody, ...]]] = {
    CelestialBody.SUN: {
        "friends": (CelestialBody.MOON, CelestialBody.MARS, CelestialBody.JUPITER),
        "enemies": (CelestialBody.VENUS, CelestialBody.SATURN),
        "neutrals": (CelestialBody.MERCURY,),
    },
    CelestialBody.MOON: {
        "friends": (CelestialBody.SUN, CelestialBody.MERCURY),
        "enemies": (),  # Moon has no enemies
        "neutrals": (CelestialBody.MARS, CelestialBody.JUPITER, CelestialBody.VENUS, CelestialBody.SATURN),
    },
    CelestialBody.MARS: {
        "friends": (CelestialBody.SUN, CelestialBody.MOON, CelestialBody.JUPITER),
        "enemies": (CelestialBody.MERCURY,),
        "neutrals": (CelestialBody.VENUS, CelestialBody.SATURN),
    },
    CelestialBody.MERCURY: {
        "friends": (CelestialBody.SUN, CelestialBody.VENUS),
        "enemies": (CelestialBody.MOON,),
        "neutrals": (CelestialBody.MARS, CelestialBody.JUPITER, CelestialBody.SATURN),
    },
    CelestialBody.JUPITER: {
        "friends": (CelestialBody.SUN, CelestialBody.MOON, CelestialBody.MARS),
        "enemies": (CelestialBody.MERCURY, CelestialBody.VENUS),
        "neutrals": (CelestialBody.SATURN,),
    },
    CelestialBody.VENUS: {
        "friends": (CelestialBody.MERCURY, CelestialBody.SATURN),
        "enemies": (CelestialBody.SUN, CelestialBody.MOON),
        "neutrals": (CelestialBody.MARS, CelestialBody.JUPITER),
    },
    CelestialBody.SATURN: {
        "friends": (CelestialBody.MERCURY, CelestialBody.VENUS),
        "enemies": (CelestialBody.SUN, CelestialBody.MOON, CelestialBody.MARS),
        "neutrals": (CelestialBody.JUPITER,),
    },
    CelestialBody.RAHU: {
        # Rahu is considered to behave like Saturn
        "friends": (CelestialBody.MERCURY, CelestialBody.VENUS, CelestialBody.SATURN),
        "enemies": (CelestialBody.SUN, CelestialBody.MOON, CelestialBody.MARS),
        "neutrals": (CelestialBody.JUPITER,),
    },
    CelestialBody.KETU: {
        # Ketu is considered to behave like Mars
        "friends": (CelestialBody.SUN, CelestialBody.MOON, CelestialBody.JUPITER),
        "enemies": (CelestialBody.MERCURY,),
        "neutrals": (CelestialBody.VENUS, CelestialBody.SATURN, CelestialBody.MARS),
    },
}


# =============================================================================
# COMBUSTION (ASTA) THRESHOLDS
# =============================================================================

# Degrees from Sun within which a planet is considered combust
# Values from classical texts (may vary slightly between sources)
COMBUSTION_DEGREES: dict[CelestialBody, float] = {
    CelestialBody.MOON: 12.0,      # Moon combust within 12Â° of Sun
    CelestialBody.MARS: 17.0,      # Mars combust within 17Â°
    CelestialBody.MERCURY: 14.0,   # Mercury combust within 14Â° (12Â° when retrograde)
    CelestialBody.JUPITER: 11.0,   # Jupiter combust within 11Â°
    CelestialBody.VENUS: 10.0,     # Venus combust within 10Â° (8Â° when retrograde)
    CelestialBody.SATURN: 15.0,    # Saturn combust within 15Â°
}

# Mercury and Venus have different thresholds when retrograde
COMBUSTION_DEGREES_RETROGRADE: dict[CelestialBody, float] = {
    CelestialBody.MERCURY: 12.0,
    CelestialBody.VENUS: 8.0,
}


# =============================================================================
# DASHA PERIODS (Years for Vimshottari Dasha - Total 120 years)
# =============================================================================

VIMSHOTTARI_PERIODS: dict[CelestialBody, float] = {
    CelestialBody.SUN: 6.0,
    CelestialBody.MOON: 10.0,
    CelestialBody.MARS: 7.0,
    CelestialBody.RAHU: 18.0,
    CelestialBody.JUPITER: 16.0,
    CelestialBody.SATURN: 19.0,
    CelestialBody.MERCURY: 17.0,
    CelestialBody.KETU: 7.0,
    CelestialBody.VENUS: 20.0,
}

# Dasha sequence (order in which Mahadashas follow each other)
VIMSHOTTARI_SEQUENCE: tuple[CelestialBody, ...] = (
    CelestialBody.KETU,
    CelestialBody.VENUS,
    CelestialBody.SUN,
    CelestialBody.MOON,
    CelestialBody.MARS,
    CelestialBody.RAHU,
    CelestialBody.JUPITER,
    CelestialBody.SATURN,
    CelestialBody.MERCURY,
)

# Total Vimshottari Dasha cycle in years
VIMSHOTTARI_TOTAL_YEARS: float = 120.0


# =============================================================================
# ASPECT (DRISHTI) CONSTANTS
# =============================================================================

# Standard aspects - all planets aspect the 7th house from their position
# Special aspects are listed separately

# Full aspects (100% strength)
FULL_ASPECT_HOUSES: tuple[int, ...] = (7)  # All planets fully aspect 7th house

# Special aspects (unique to certain planets)
# Format: {planet: tuple of houses aspected with strength}
SPECIAL_ASPECTS: dict[CelestialBody, dict[int, float]] = {
    # Mars aspects 4th, 7th, and 8th houses
    CelestialBody.MARS: {4: 1.0, 7: 1.0, 8: 1.0},
    
    # Jupiter aspects 5th, 7th, and 9th houses
    CelestialBody.JUPITER: {5: 1.0, 7: 1.0, 9: 1.0},
    
    # Saturn aspects 3rd, 7th, and 10th houses
    CelestialBody.SATURN: {3: 1.0, 7: 1.0, 10: 1.0},
    
    # Rahu and Ketu aspect like Jupiter + Saturn (per some traditions)
    # Using the more common interpretation: 5th, 7th, 9th
    CelestialBody.RAHU: {5: 1.0, 7: 1.0, 9: 1.0},
    CelestialBody.KETU: {5: 1.0, 7: 1.0, 9: 1.0},
}

# For other planets (Sun, Moon, Mercury, Venus) only 7th house aspect
DEFAULT_ASPECTS: dict[int, float] = {7: 1.0}


# =============================================================================
# PLANETARY WAR (GRAHA YUDDHA) THRESHOLDS
# =============================================================================

# Two planets are in war when within 1 degree of each other
PLANETARY_WAR_ORB: float = 1.0

# Planets that can participate in planetary war (Tara Grahas only)
WAR_PARTICIPANTS: tuple[CelestialBody, ...] = (
    CelestialBody.MARS,
    CelestialBody.MERCURY,
    CelestialBody.JUPITER,
    CelestialBody.VENUS,
    CelestialBody.SATURN,
)


# =============================================================================
# DIVISIONAL CHART (VARGA) DIVISORS
# =============================================================================

class VargaChart(IntEnum):
    """Divisional charts and their division factors."""
    D1 = 1       # Rashi - Main birth chart
    D2 = 2       # Hora - Wealth
    D3 = 3       # Drekkana - Siblings, courage
    D4 = 4       # Chaturthamsa - Fortune, property
    D7 = 7       # Saptamsa - Children
    D9 = 9       # Navamsa - Spouse, dharma (most important after D1)
    D10 = 10     # Dasamsa - Career, profession
    D12 = 12     # Dwadasamsa - Parents
    D16 = 16     # Shodasamsa - Vehicles, comforts
    D20 = 20     # Vimsamsa - Spiritual progress
    D24 = 24     # Chaturvimsamsa - Education, learning
    D27 = 27     # Saptavimsamsa - Strength, weakness
    D30 = 30     # Trimsamsa - Evils, misfortune
    D40 = 40     # Khavedamsa - Auspicious/inauspicious effects
    D45 = 45     # Akshavedamsa - General well-being
    D60 = 60     # Shashtyamsa - All matters (most detailed)

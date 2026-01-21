"""
Western Astrology Constants
===========================

Constants for Western/Tropical astrology calculations.
"""

from enum import IntEnum, Enum
from typing import NamedTuple
from src.engines.core.celestial_bodies import CelestialBody


# Zodiac Signs (Tropical)
class ZodiacSign(IntEnum):
    """12 Zodiac signs in Western astrology (Tropical)."""
    ARIES = 0
    TAURUS = 1
    GEMINI = 2
    CANCER = 3
    LEO = 4
    VIRGO = 5
    LIBRA = 6
    SCORPIO = 7
    SAGITTARIUS = 8
    CAPRICORN = 9
    AQUARIUS = 10
    PISCES = 11


# Elements
class Element(Enum):
    """Four elements in astrology."""
    FIRE = "fire"
    EARTH = "earth"
    AIR = "air"
    WATER = "water"


# Modalities
class Modality(Enum):
    """Three modalities (qualities)."""
    CARDINAL = "cardinal"
    FIXED = "fixed"
    MUTABLE = "mutable"


# Polarity
class Polarity(Enum):
    """Two polarities."""
    MASCULINE = "masculine"
    FEMININE = "feminine"


# Essential Dignities
class EssentialDignity(Enum):
    """Essential dignities of planets in signs."""
    DOMICILE = "domicile"          # Ruler
    EXALTATION = "exaltation"       # Exalted
    DETRIMENT = "detriment"         # Opposite of domicile
    FALL = "fall"                   # Opposite of exaltation
    PEREGRINE = "peregrine"         # No dignity


# Sign Info
class SignInfo(NamedTuple):
    """Information about a zodiac sign."""
    sign: ZodiacSign
    name: str
    symbol: str
    element: Element
    modality: Modality
    polarity: Polarity
    ruler: CelestialBody


# Complete sign data
SIGN_DATA = {
    ZodiacSign.ARIES: SignInfo(
        sign=ZodiacSign.ARIES,
        name="Aries",
        symbol="♈",
        element=Element.FIRE,
        modality=Modality.CARDINAL,
        polarity=Polarity.MASCULINE,
        ruler=CelestialBody.MARS
    ),
    ZodiacSign.TAURUS: SignInfo(
        sign=ZodiacSign.TAURUS,
        name="Taurus",
        symbol="♉",
        element=Element.EARTH,
        modality=Modality.FIXED,
        polarity=Polarity.FEMININE,
        ruler=CelestialBody.VENUS
    ),
    ZodiacSign.GEMINI: SignInfo(
        sign=ZodiacSign.GEMINI,
        name="Gemini",
        symbol="♊",
        element=Element.AIR,
        modality=Modality.MUTABLE,
        polarity=Polarity.MASCULINE,
        ruler=CelestialBody.MERCURY
    ),
    ZodiacSign.CANCER: SignInfo(
        sign=ZodiacSign.CANCER,
        name="Cancer",
        symbol="♋",
        element=Element.WATER,
        modality=Modality.CARDINAL,
        polarity=Polarity.FEMININE,
        ruler=CelestialBody.MOON
    ),
    ZodiacSign.LEO: SignInfo(
        sign=ZodiacSign.LEO,
        name="Leo",
        symbol="♌",
        element=Element.FIRE,
        modality=Modality.FIXED,
        polarity=Polarity.MASCULINE,
        ruler=CelestialBody.SUN
    ),
    ZodiacSign.VIRGO: SignInfo(
        sign=ZodiacSign.VIRGO,
        name="Virgo",
        symbol="♍",
        element=Element.EARTH,
        modality=Modality.MUTABLE,
        polarity=Polarity.FEMININE,
        ruler=CelestialBody.MERCURY
    ),
    ZodiacSign.LIBRA: SignInfo(
        sign=ZodiacSign.LIBRA,
        name="Libra",
        symbol="♎",
        element=Element.AIR,
        modality=Modality.CARDINAL,
        polarity=Polarity.MASCULINE,
        ruler=CelestialBody.VENUS
    ),
    ZodiacSign.SCORPIO: SignInfo(
        sign=ZodiacSign.SCORPIO,
        name="Scorpio",
        symbol="♏",
        element=Element.WATER,
        modality=Modality.FIXED,
        polarity=Polarity.FEMININE,
        ruler=CelestialBody.MARS
    ),
    ZodiacSign.SAGITTARIUS: SignInfo(
        sign=ZodiacSign.SAGITTARIUS,
        name="Sagittarius",
        symbol="♐",
        element=Element.FIRE,
        modality=Modality.MUTABLE,
        polarity=Polarity.MASCULINE,
        ruler=CelestialBody.JUPITER
    ),
    ZodiacSign.CAPRICORN: SignInfo(
        sign=ZodiacSign.CAPRICORN,
        name="Capricorn",
        symbol="♑",
        element=Element.EARTH,
        modality=Modality.CARDINAL,
        polarity=Polarity.FEMININE,
        ruler=CelestialBody.SATURN
    ),
    ZodiacSign.AQUARIUS: SignInfo(
        sign=ZodiacSign.AQUARIUS,
        name="Aquarius",
        symbol="♒",
        element=Element.AIR,
        modality=Modality.FIXED,
        polarity=Polarity.MASCULINE,
        ruler=CelestialBody.SATURN
    ),
    ZodiacSign.PISCES: SignInfo(
        sign=ZodiacSign.PISCES,
        name="Pisces",
        symbol="♓",
        element=Element.WATER,
        modality=Modality.MUTABLE,
        polarity=Polarity.FEMININE,
        ruler=CelestialBody.JUPITER
    ),
}


# Element groupings
FIRE_SIGNS = {ZodiacSign.ARIES, ZodiacSign.LEO, ZodiacSign.SAGITTARIUS}
EARTH_SIGNS = {ZodiacSign.TAURUS, ZodiacSign.VIRGO, ZodiacSign.CAPRICORN}
AIR_SIGNS = {ZodiacSign.GEMINI, ZodiacSign.LIBRA, ZodiacSign.AQUARIUS}
WATER_SIGNS = {ZodiacSign.CANCER, ZodiacSign.SCORPIO, ZodiacSign.PISCES}

# Modality groupings
CARDINAL_SIGNS = {ZodiacSign.ARIES, ZodiacSign.CANCER, ZodiacSign.LIBRA, ZodiacSign.CAPRICORN}
FIXED_SIGNS = {ZodiacSign.TAURUS, ZodiacSign.LEO, ZodiacSign.SCORPIO, ZodiacSign.AQUARIUS}
MUTABLE_SIGNS = {ZodiacSign.GEMINI, ZodiacSign.VIRGO, ZodiacSign.SAGITTARIUS, ZodiacSign.PISCES}

# Polarity groupings
MASCULINE_SIGNS = {ZodiacSign.ARIES, ZodiacSign.GEMINI, ZodiacSign.LEO, ZodiacSign.LIBRA, ZodiacSign.SAGITTARIUS, ZodiacSign.AQUARIUS}
FEMININE_SIGNS = {ZodiacSign.TAURUS, ZodiacSign.CANCER, ZodiacSign.VIRGO, ZodiacSign.SCORPIO, ZodiacSign.CAPRICORN, ZodiacSign.PISCES}

# Domicile rulers
DOMICILE_RULERS = {
    ZodiacSign.ARIES: CelestialBody.MARS,
    ZodiacSign.TAURUS: CelestialBody.VENUS,
    ZodiacSign.GEMINI: CelestialBody.MERCURY,
    ZodiacSign.CANCER: CelestialBody.MOON,
    ZodiacSign.LEO: CelestialBody.SUN,
    ZodiacSign.VIRGO: CelestialBody.MERCURY,
    ZodiacSign.LIBRA: CelestialBody.VENUS,
    ZodiacSign.SCORPIO: CelestialBody.MARS,
    ZodiacSign.SAGITTARIUS: CelestialBody.JUPITER,
    ZodiacSign.CAPRICORN: CelestialBody.SATURN,
    ZodiacSign.AQUARIUS: CelestialBody.SATURN,
    ZodiacSign.PISCES: CelestialBody.JUPITER,
}


# Exaltations (planet -> (sign, degree))
EXALTATION = {
    CelestialBody.SUN: (ZodiacSign.ARIES, 19),
    CelestialBody.MOON: (ZodiacSign.TAURUS, 3),
    CelestialBody.MERCURY: (ZodiacSign.VIRGO, 15),
    CelestialBody.VENUS: (ZodiacSign.PISCES, 27),
    CelestialBody.MARS: (ZodiacSign.CAPRICORN, 28),
    CelestialBody.JUPITER: (ZodiacSign.CANCER, 5),
    CelestialBody.SATURN: (ZodiacSign.LIBRA, 21),
}

# Keep EXALTATIONS for backward compatibility
EXALTATIONS = EXALTATION


# Falls (opposite of exaltation)
FALL = {
    CelestialBody.SUN: (ZodiacSign.LIBRA, 19),
    CelestialBody.MOON: (ZodiacSign.SCORPIO, 3),
    CelestialBody.MERCURY: (ZodiacSign.PISCES, 15),
    CelestialBody.VENUS: (ZodiacSign.VIRGO, 27),
    CelestialBody.MARS: (ZodiacSign.CANCER, 28),
    CelestialBody.JUPITER: (ZodiacSign.CAPRICORN, 5),
    CelestialBody.SATURN: (ZodiacSign.ARIES, 21),
}

# Keep DEBILITATIONS for backward compatibility
DEBILITATIONS = FALL


# Detriments (opposite of domicile)
DETRIMENT = {
    CelestialBody.SUN: ZodiacSign.AQUARIUS,
    CelestialBody.MOON: ZodiacSign.CAPRICORN,
    CelestialBody.MERCURY: ZodiacSign.SAGITTARIUS,
    CelestialBody.VENUS: ZodiacSign.ARIES,
    CelestialBody.MARS: ZodiacSign.LIBRA,
    CelestialBody.JUPITER: ZodiacSign.GEMINI,
    CelestialBody.SATURN: ZodiacSign.CANCER,
}


# House Systems
class HouseType(Enum):
    """Supported house systems."""
    PLACIDUS = "P"
    KOCH = "K"
    EQUAL = "E"
    WHOLE_SIGN = "W"
    CAMPANUS = "C"
    REGIOMONTANUS = "R"


HOUSE_TYPES = {
    "PLACIDUS": HouseType.PLACIDUS,
    "KOCH": HouseType.KOCH,
    "EQUAL": HouseType.EQUAL,
    "WHOLE_SIGN": HouseType.WHOLE_SIGN,
    "CAMPANUS": HouseType.CAMPANUS,
    "REGIOMONTANUS": HouseType.REGIOMONTANUS,
}


# Aspect Types
class AspectType(Enum):
    """Major and minor aspects."""
    CONJUNCTION = (0, 8)
    OPPOSITION = (180, 8)
    TRINE = (120, 8)
    SQUARE = (90, 8)
    SEXTILE = (60, 6)
    QUINCUNX = (150, 3)
    SEMISEXTILE = (30, 2)
    SEMISQUARE = (45, 2)
    SESQUIQUADRATE = (135, 2)


# Major aspects only
MAJOR_ASPECTS = {
    AspectType.CONJUNCTION,
    AspectType.OPPOSITION,
    AspectType.TRINE,
    AspectType.SQUARE,
    AspectType.SEXTILE,
}


class AspectInfo(NamedTuple):
    """Aspect information."""
    angle: float
    orb: float
    name: str
    is_major: bool


ASPECT_DATA = {
    AspectType.CONJUNCTION: AspectInfo(0, 8, "Conjunction", True),
    AspectType.OPPOSITION: AspectInfo(180, 8, "Opposition", True),
    AspectType.TRINE: AspectInfo(120, 8, "Trine", True),
    AspectType.SQUARE: AspectInfo(90, 8, "Square", True),
    AspectType.SEXTILE: AspectInfo(60, 6, "Sextile", True),
    AspectType.QUINCUNX: AspectInfo(150, 3, "Quincunx", False),
    AspectType.SEMISEXTILE: AspectInfo(30, 2, "Semi-sextile", False),
    AspectType.SEMISQUARE: AspectInfo(45, 2, "Semi-square", False),
    AspectType.SESQUIQUADRATE: AspectInfo(135, 2, "Sesquiquadrate", False),
}


# Sign Rulers (alias for DOMICILE_RULERS)
SIGN_RULERS = DOMICILE_RULERS


# Sign Elements (for compatibility)
SIGN_ELEMENTS = {
    ZodiacSign.ARIES: "Fire",
    ZodiacSign.TAURUS: "Earth",
    ZodiacSign.GEMINI: "Air",
    ZodiacSign.CANCER: "Water",
    ZodiacSign.LEO: "Fire",
    ZodiacSign.VIRGO: "Earth",
    ZodiacSign.LIBRA: "Air",
    ZodiacSign.SCORPIO: "Water",
    ZodiacSign.SAGITTARIUS: "Fire",
    ZodiacSign.CAPRICORN: "Earth",
    ZodiacSign.AQUARIUS: "Air",
    ZodiacSign.PISCES: "Water",
}


# Sign Modalities (for compatibility)
SIGN_MODALITIES = {
    ZodiacSign.ARIES: "Cardinal",
    ZodiacSign.TAURUS: "Fixed",
    ZodiacSign.GEMINI: "Mutable",
    ZodiacSign.CANCER: "Cardinal",
    ZodiacSign.LEO: "Fixed",
    ZodiacSign.VIRGO: "Mutable",
    ZodiacSign.LIBRA: "Cardinal",
    ZodiacSign.SCORPIO: "Fixed",
    ZodiacSign.SAGITTARIUS: "Mutable",
    ZodiacSign.CAPRICORN: "Cardinal",
    ZodiacSign.AQUARIUS: "Fixed",
    ZodiacSign.PISCES: "Mutable",
}
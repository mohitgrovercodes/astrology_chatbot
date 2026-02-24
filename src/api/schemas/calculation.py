# src/api/schemas/calculation.py
# src\api\schemas\calculation.py
"""
Calculation Schemas - Pydantic Models
======================================

Request and response models for chart calculation endpoints.
"""

from pydantic import BaseModel, Field
from typing import Dict, Optional, List, Any


class ChartRequest(BaseModel):
    """Birth chart calculation request."""
    date_of_birth: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    time_of_birth: str = Field(..., pattern=r"^\d{2}:\d{2}:\d{2}$")
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    timezone: str = Field(default="UTC")
    system: str = Field(default="vedic", pattern="^(vedic|western)$")
    
    class Config:
        json_schema_extra = {
            "example": {
                "date_of_birth": "1990-03-15",
                "time_of_birth": "14:30:00",
                "latitude": 26.9124,
                "longitude": 75.7873,
                "timezone": "Asia/Kolkata",
                "system": "vedic"
            }
        }


class PlanetPosition(BaseModel):
    """Planet position in chart."""
    sign: str
    house: int
    degree: float
    nakshatra: Optional[str] = None
    nakshatra_pada: Optional[int] = None
    is_retrograde: bool = False
    is_combust: bool = False
    speed: float = 0.0
    dignity: str = "neutral"


class DashaPeriod(BaseModel):
    """Dasha period information."""
    level: str
    planet: str
    start_date: str
    end_date: str


class VargaPosition(BaseModel):
    """A planet's position in a divisional chart."""
    sign: str
    house: int
    division_number: int


class YogaData(BaseModel):
    """Vedic Yoga information."""
    name: str
    category: str
    is_present: bool
    forming_planets: List[str]
    forming_houses: List[int]
    strength: float
    description: Optional[str] = None


class AspectData(BaseModel):
    """Aspect information."""
    aspecting_planet: str
    aspected_house: int
    aspect_type: str
    strength: float


# --- Western Astrology Models ---

class WesternPlanetPosition(BaseModel):
    """Western-style planet position."""
    sign: str
    house: int
    degree: float
    is_retrograde: bool
    speed: float
    dignity_score: int
    dignity_status: List[str]


class WesternAspect(BaseModel):
    """Western aspect (planetary angular relationship)."""
    planet1: str
    planet2: str
    aspect_type: str
    orb: float
    strength: float = Field(..., description="Numeric strength: 1.0=exact, 0.75=close, 0.5=moderate, 0.25=wide")
    is_major: bool


class WesternHouseData(BaseModel):
    """Western house cusp and occupancy."""
    number: int
    cusp_degree: float
    cusp_sign: str
    planets: List[str]


class WesternChartResponse(BaseModel):
    """Western natal chart response."""
    sun_sign: str
    moon_sign: str
    ascendant_sign: str
    midheaven_sign: str
    planets: Dict[str, WesternPlanetPosition]
    houses: List[WesternHouseData]
    aspects: List[WesternAspect]
    total_dignity_score: int


# --- Core Astronomical Models ---

class RawPlanetData(BaseModel):
    """Raw astronomical data for a planet."""
    longitude: float
    latitude: float
    distance: float
    speed_longitude: float
    speed_latitude: float
    speed_distance: float
    is_retrograde: bool


class CoreEphemerisResponse(BaseModel):
    """Raw ephemeris data response."""
    julian_day: float
    ayanamsa_value: Optional[float] = None
    planets: Dict[str, RawPlanetData]
    house_cusps: List[float]
    angles: Dict[str, float]


class ChartResponse(BaseModel):
    """Birth chart calculation response."""
    lagna: str = Field(..., description="Ascendant sign")
    lagna_degree: float = Field(0.0, description="Ascendant degree")
    rashi: str = Field(..., description="Moon sign")
    nakshatra: str = Field(..., description="Birth nakshatra")
    planets: Dict[str, PlanetPosition] = Field(..., description="Planet positions")
    houses: List[str] = Field(..., description="House sign placements (1-12)")
    dasha: Dict = Field(..., description="Current dasha periods")
    vargas: Optional[Dict[str, Dict[str, VargaPosition]]] = Field(None, description="Divisional charts (D9, D10, etc.)")
    yogas: Optional[List[YogaData]] = Field(None, description="Important Yogas found in the chart")
    aspect_grid: Optional[Dict[str, List[AspectData]]] = Field(None, description="Planetary aspects per house")
    transits: Optional[Dict] = Field(None, description="Current transits")
    
    class Config:
        json_schema_extra = {
            "example": {
                "lagna": "Karka",
                "rashi": "Tula",
                "nakshatra": "Chitra",
                "planets": {
                    "Sun": {
                        "sign": "Meena",
                        "house": 9,
                        "degree": 24.5,
                        "nakshatra": "Uttara Bhadrapada"
                    }
                },
                "houses": ["Karka", "Simha", "Kanya", "..."],
                "dasha": {
                    "current": "SATURN/MEAN_NODE/MOON",
                    "periods": []
                }
            }
        }

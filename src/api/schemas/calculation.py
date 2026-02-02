"""
Calculation Schemas - Pydantic Models
======================================

Request and response models for chart calculation endpoints.
"""

from pydantic import BaseModel, Field
from typing import Dict, Optional, List


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


class DashaPeriod(BaseModel):
    """Dasha period information."""
    level: str
    planet: str
    start_date: str
    end_date: str


class ChartResponse(BaseModel):
    """Birth chart calculation response."""
    lagna: str = Field(..., description="Ascendant sign")
    rashi: str = Field(..., description="Moon sign")
    nakshatra: str = Field(..., description="Birth nakshatra")
    planets: Dict[str, PlanetPosition] = Field(..., description="Planet positions")
    houses: List[str] = Field(..., description="House cusps")
    dasha: Dict = Field(..., description="Current dasha periods")
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

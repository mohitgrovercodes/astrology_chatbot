# src/utils/serializers.py
# src\utils\serializers.py
"""
JSON Serializers for Astrology Engines
======================================

Converts engine outputs (dataclasses, enums) to LLM-consumable JSON
with rich metadata for RAG retrieval.
"""

from datetime import datetime
from typing import Any, Dict, List
from enum import Enum
import json

# Import from calculation engines
from src.engines.vedic.vedic_engine import VedicChart
from src.engines.western.western_engine import WesternChart
from src.engines.core.celestial_bodies import CelestialBody, VEDIC_GRAHAS, WESTERN_PLANETS


class AstroJSONEncoder(json.JSONEncoder):
    """
    Custom JSON encoder for astrology data structures.
    
    Handles:
    - datetime objects
    - Enums
    - Dataclasses
    - Custom objects with __dict__
    """
    
    def default(self, obj):
        # Handle datetime
        if isinstance(obj, datetime):
            return obj.isoformat()
        
        # Handle Enums
        if isinstance(obj, Enum):
            return obj.value
        
        # Handle dataclasses
        if hasattr(obj, '__dataclass_fields__'):
            return {
                k: getattr(obj, k) 
                for k in obj.__dataclass_fields__.keys()
            }
        
        # Handle CelestialBody
        if isinstance(obj, CelestialBody):
            return obj.name
        
        # Fallback to default
        return super().default(obj)


def deep_serialize_object(obj):
    """Recursively serialize complex objects to JSON-friendly formats."""
    if obj is None:
        return None
    elif isinstance(obj, (str, int, float, bool)):
        return obj
    elif isinstance(obj, (list, tuple)):
        return [deep_serialize_object(item) for item in obj]
    elif isinstance(obj, dict):
        return {k: deep_serialize_object(v) for k, v in obj.items()}
    elif isinstance(obj, Enum):
        return obj.value
    elif isinstance(obj, datetime):
        return obj.isoformat()
    elif hasattr(obj, 'to_dict'):
        return obj.to_dict()
    elif hasattr(obj, '__dict__'):
        return {
            k: deep_serialize_object(v) 
            for k, v in obj.__dict__.items() 
            if not k.startswith('_')
        }
    else:
        return str(obj)


def serialize_vedic_chart(chart: VedicChart) -> Dict[str, Any]:
    """
    Convert VedicChart to LLM-friendly JSON with metadata.
    
    Args:
        chart: VedicChart object from vedic_engine
        
    Returns:
        Dictionary with comprehensive chart data and metadata
    """
    from src.engines.vedic.vedic_constants import RASHI_SANSKRIT_NAMES, NAKSHATRA_NAMES, VargaChart
    
    # Serialize birth data
    birth_data = {
        "datetime": chart.birth_data.date.isoformat(),
        "location": {
            "latitude": chart.birth_data.latitude,
            "longitude": chart.birth_data.longitude,
            "timezone": chart.birth_data.timezone_str or "UTC"
        }
    }
    
    # Serialize Lagna (Ascendant)
    lagna = {
        "sign": chart.lagna.rashi_name,
        "sign_sanskrit": chart.lagna.rashi.name,
        "degree": chart.lagna.degree,
        "minute": chart.lagna.minute,
        "nakshatra": chart.lagna.nakshatra_name,
        "nakshatra_pada": chart.lagna.nakshatra_pada,
        "nakshatra_lord": chart.lagna.nakshatra_lord.name
    }
    
    # Serialize planets
    planets = {}
    for planet in VEDIC_GRAHAS:
        rashi_pos = chart.vedic_mapping.rashi_positions.get(planet)
        nakshatra_pos = chart.vedic_mapping.nakshatra_positions.get(planet)
        dignity = chart.vedic_mapping.dignities.get(planet)
        bhava = chart.vedic_mapping.bhava_placements.get(planet)
        
        if rashi_pos and nakshatra_pos and dignity and bhava:
            planets[planet.name] = {
                "sign": rashi_pos.rashi_name,
                "sign_sanskrit": rashi_pos.rashi.name,
                "degree": rashi_pos.degree,
                "minute": rashi_pos.minute,
                "nakshatra": nakshatra_pos.nakshatra_name,
                "nakshatra_pada": nakshatra_pos.pada,
                "house": bhava.bhava,
                "retrograde": chart.is_planet_retrograde(planet),
                "combust": chart.is_planet_combust(planet),
                "dignity": {
                    "status": dignity.dignity.value,
                    "is_exalted": dignity.is_exalted,
                    "is_debilitated": dignity.is_debilitated,
                    "is_own_sign": dignity.is_in_own_sign,
                    "dispositor": dignity.dispositor.name
                }
            }
    
    # Serialize Divisional Charts (D2-D60) - Simple Format
    vargas = {}
    if hasattr(chart, 'vargas') and chart.vargas:
        for v_type in ['D2', 'D3', 'D4', 'D7', 'D9', 'D10', 'D12', 'D16', 'D20', 'D24', 'D27', 'D30', 'D40', 'D45', 'D60']:
            v_enum = getattr(VargaChart, v_type, None)
            if v_enum:
                varga_planets = {}
                for planet in VEDIC_GRAHAS:
                    if planet in chart.vargas:
                        pos = chart.vargas[planet].get_position(v_enum)
                        if pos:
                            varga_planets[planet.name] = pos.rashi.name
                if varga_planets:
                    vargas[v_type] = {"planets": varga_planets}

    # Serialize Yogas
    yogas = [
        {
            "name": yoga.name,
            "category": yoga.category.value,
            "is_present": yoga.is_present,
            "strength": yoga.strength,
            "forming_planets": [p.name for p in yoga.forming_planets],
            "forming_houses": list(yoga.forming_houses),
            "conditions_met": list(yoga.conditions_met)
        }
        for yoga in chart.yogas.detected_yogas
        if yoga.is_present
    ]
    
    # Serialize Dasha
    current_dasha = chart.get_current_dasha(datetime.now())
    dasha_serialized = deep_serialize_object(current_dasha)
    
    # Planetary Strengths
    strengths = {}
    if hasattr(chart, 'planetary_strengths') and chart.planetary_strengths:
        strengths = deep_serialize_object(chart.planetary_strengths)
    elif hasattr(chart, 'shadbala') and chart.shadbala:
        strengths = deep_serialize_object(chart.shadbala)

    # Aspects
    aspects = {}
    if hasattr(chart, 'aspects') and chart.aspects:
        aspects = deep_serialize_object(chart.aspects)

    # Metadata for RAG retrieval
    metadata = {
        "ayanamsa": chart.ayanamsa.name,
        "ayanamsa_value": round(chart.ayanamsa_value, 4),
        "house_system": chart.house_system.name,
        "computation_timestamp": datetime.now().isoformat(),
        "julian_day": chart.julian_day,
        "chart_system": "vedic",
        "tradition": "jyotish"
    }
    
    # Build divisional_charts_simple — flat {D9: {PLANET: sign, ...}, ...} format
    # required by divisional_chart_helper and schema validation in EnhancedSessionManager
    divisional_charts_simple = {
        vtype: vdata["planets"]
        for vtype, vdata in vargas.items()
        if isinstance(vdata, dict) and "planets" in vdata
    }

    # Compute vargottama planets — same sign in D1 and D9
    vargottama = []
    d9_planets = divisional_charts_simple.get("D9", {})
    for planet_name, planet_data in planets.items():
        d1_sign = planet_data.get("sign_sanskrit") or planet_data.get("sign", "")
        d9_sign = d9_planets.get(planet_name, "")
        if d1_sign and d9_sign and d1_sign.upper() == d9_sign.upper():
            vargottama.append(planet_name)

    # Expose Navamsa (D9) chart explicitly for validation and downstream consumers.
    # Validation helpers look for chart_data['navamsa'] or an explicit 'D9' chart,
    # so we construct a simple structure from the already-computed D9 planets.
    navamsa_chart = None
    if d9_planets:
        navamsa_chart = {
            "lagna": "Unknown",  # Divisional lagna is not yet computed; planets are sufficient for most rules.
            "planets": d9_planets,
        }

    return {
        "chart_type": "vedic",
        "birth_data": birth_data,
        "lagna": lagna,
        "planets": planets,
        "vargas": vargas,
        "divisional_charts_simple": divisional_charts_simple,
        "vargottama": vargottama,
        # Make D9/Navamsa available to validation and analysis layers
        **({"navamsa": navamsa_chart} if navamsa_chart else {}),
        "yogas": yogas,
        "dasha": dasha_serialized,
        "strengths": strengths,
        "aspects": aspects,
        "_metadata": metadata
    }


def serialize_western_chart(chart: WesternChart) -> Dict[str, Any]:
    """
    Convert WesternChart to LLM-friendly JSON with metadata.
    
    Args:
        chart: WesternChart object from western engine
        
    Returns:
        Dictionary with comprehensive chart data and metadata
    """
    
    from src.engines.western.western_constants import WESTERN_PLANETS
    
    # Serialize birth data
    birth_data = {
        "datetime": chart.birth_data.datetime.isoformat(),
        "location": {
            "latitude": chart.birth_data.latitude,
            "longitude": chart.birth_data.longitude,
            "timezone": chart.birth_data.timezone or "UTC"
        }
    }
    
    # Serialize key points
    key_points = {
        "sun_sign": chart.sun_sign_name,
        "moon_sign": chart.moon_sign_name,
        "ascendant": {
            "sign": chart.ascendant_sign_name,
            "degree": round(chart.ascendant % 30, 2)
        },
        "midheaven": {
            "sign": chart.midheaven_sign.name.title(),
            "degree": round(chart.midheaven % 30, 2)
        }
    }
    
    # Serialize planets
    planets = {}
    for planet in WESTERN_PLANETS:
        if planet in chart.positions:
            pos = chart.positions[planet]
            placement = chart.house_placements.get(planet)
            dignity = chart.dignities.dignities.get(planet)
            
            planets[planet.name] = {
                "sign": chart.get_planet_sign(planet).name.title(),
                "degree_in_sign": round(pos.longitude % 30, 2),
                "house": placement.house if placement else None,
                "retrograde": pos.is_retrograde,
                "dignity": {
                    "status": dignity.dignity_type.name if dignity else "UNKNOWN",
                    "score": dignity.score if dignity else 0
                }
            }
    
    # Serialize aspects
    aspects = [
        {
            "planet1": asp.planet1.name,
            "planet2": asp.planet2.name,
            "aspect_type": asp.aspect_type.name,
            "orb": round(asp.orb, 2),
            "is_major": asp.is_major,
            "is_hard": asp.is_hard,
            "strength": asp.strength.value
        }
        for asp in chart.aspects.major_aspects
    ]
    
    # Metadata
    metadata = {
        "house_system": chart.house_system.name,
        "computation_timestamp": datetime.now().isoformat(),
        "julian_day": chart.julian_day,
        "chart_system": "western",
        "tradition": "tropical"
    }
    
    return {
        "chart_type": "western",
        "birth_data": birth_data,
        "key_points": key_points,
        "planets": planets,
        "aspects": aspects,
        "dignities": {
            "total_score": chart.dignity_score,
            "dignified_count": len(chart.dignified_planets),
            "debilitated_count": len(chart.debilitated_planets)
        },
        "_metadata": metadata
    }


def serialize_chart(chart, chart_type: str = "vedic") -> Dict[str, Any]:
    """
    Universal chart serializer - auto-detects type.
    
    Args:
        chart: VedicChart or WesternChart object
        chart_type: "vedic" or "western" (auto-detected if not provided)
    """
    
    from src.engines.vedic.vedic_engine import VedicChart
    from src.engines.western.western_engine import WesternChart
    
    if isinstance(chart, VedicChart):
        return serialize_vedic_chart(chart)
    elif isinstance(chart, WesternChart):
        return serialize_western_chart(chart)
    else:
        raise TypeError(f"Unknown chart type: {type(chart)}")


def serialize_for_storage(chart_json: Dict[str, Any]) -> str:
    """
    Serialize chart to JSON string for database storage.
    
    Args:
        chart_json: Chart dictionary from serialize_*_chart()
        
    Returns:
        JSON string with custom encoder
    """
    return json.dumps(chart_json, cls=AstroJSONEncoder, indent=2)
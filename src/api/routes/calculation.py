# src\api\routes\calculation.py
"""
Calculation Routes
===================

Birth chart and astrological calculation endpoints.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from src.api.schemas.calculation import (
    ChartRequest, ChartResponse, WesternChartResponse, 
    CoreEphemerisResponse, WesternPlanetPosition, WesternAspect,
    WesternHouseData, RawPlanetData, YogaData, VargaPosition, AspectData
)
from src.api.middleware.auth import verify_api_key
from src.api.middleware.rate_limit import check_rate_limit
from src.api.dependencies import get_vedic_engine, get_western_engine
from datetime import datetime
import pytz
import traceback
from src.engines.vedic.vedic_constants import RASHI_SANSKRIT_NAMES
from src.engines.core.ephemeris import (
    get_all_positions, get_house_cusps, get_ayanamsa_value,
    Ayanamsa, HouseSystem
)
from src.engines.core.datetime_utils import datetime_to_julian_day
from src.engines.core.celestial_bodies import WESTERN_PLANETS, VEDIC_GRAHAS, CelestialBody

router = APIRouter()


@router.post("/calculate/chart", response_model=ChartResponse, tags=["Vedic"])
@router.post("/calculate/vedic/chart", response_model=ChartResponse, tags=["Vedic"])
async def calculate_vedic_chart(
    request: Request,
    chart_request: ChartRequest,
    api_key: str = Depends(verify_api_key)
):
    """
    Calculate birth chart.
    
    Generates a complete birth chart including:
    - Lagna (Ascendant)
    - Rashi (Moon sign)
    - Nakshatra
    - Planet positions
    - House cusps
    - Dasha periods
    - Current transits (optional)
    
    **Authentication:** Requires X-API-Key header
    """
    await check_rate_limit(request, api_key)
    
    vedic_engine = get_vedic_engine()
    
    try:
        # Create datetime object
        dt_str = f"{chart_request.date_of_birth} {chart_request.time_of_birth}"
        birth_date = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
        
        # Calculate full chart using the engine
        chart = vedic_engine.generate_chart(
            birth_date=birth_date,
            latitude=chart_request.latitude,
            longitude=chart_request.longitude,
            timezone_str=chart_request.timezone
        )
        
        # Map Planets
        planets_mapped = {}
        for body, pos in chart.positions.items():
            name = body.name.title()
            v_pos = chart.vedic_mapping.rashi_positions[body]
            n_pos = chart.vedic_mapping.nakshatra_positions[body]
            dignity = chart.vedic_mapping.dignities[body]
            bhava = chart.vedic_mapping.bhava_placements[body]
            
            planets_mapped[name] = {
                "sign": v_pos.rashi_name,
                "house": bhava.bhava,
                "degree": float(f"{v_pos.degree}.{v_pos.minute:02d}"),
                "nakshatra": n_pos.nakshatra_name,
                "nakshatra_pada": n_pos.pada,
                "is_retrograde": chart.is_planet_retrograde(body),
                "is_combust": chart.is_planet_combust(body),
                "speed": chart.graha_stats.get_stats(body).speed if hasattr(chart.graha_stats, 'get_stats') else 0.0,
                "dignity": dignity.dignity.value
            }

        # Map Houses (Sign in each house 1-12)
        houses_mapped = []
        for h in range(1, 13):
            sign_index = (chart.lagna.rashi.value + h - 1) % 12
            houses_mapped.append(chart.vedic_mapping.lagna.rashi_name if h == 1 else chart.vedic_mapping.get_house_lord(h).name) # Simple mapping for now
            # Actually, let's just use the sign's name for each house
            from src.engines.vedic.vedic_constants import RASHI_SANSKRIT_NAMES
            houses_mapped[h-1] = RASHI_SANSKRIT_NAMES[sign_index]

        # Map Vargas
        vargas_mapped = {}
        for body, all_vargas in chart.vargas.items():
            p_name = body.name.title()
            vargas_mapped[p_name] = {}
            for v_type, v_pos in all_vargas.positions.items():
                vargas_mapped[p_name][v_type.name] = {
                    "sign": v_pos.rashi.name.title(),
                    "house": 0, # House calculation in Vargas usually relies on Lagnas of those Vargas
                    "division_number": v_pos.division_number
                }

        # Map Yogas
        yogas_mapped = []
        for yoga in chart.yogas.detected_yogas:
            if yoga.is_present:
                yogas_mapped.append({
                    "name": yoga.name,
                    "category": yoga.category.value,
                    "is_present": True,
                    "forming_planets": [p.name.title() for p in yoga.forming_planets] if isinstance(yoga.forming_planets, (list, tuple)) else [yoga.forming_planets.name.title()],
                    "forming_houses": list(yoga.forming_houses) if isinstance(yoga.forming_houses, (list, tuple)) else [yoga.forming_houses],
                    "strength": yoga.strength,
                    "description": None # Can be populated from a database later
                })

        # Map Aspect Grid
        aspects_mapped = {}
        for house, aspects in chart.aspects.house_aspects.items():
            aspects_mapped[str(house)] = [
                {
                    "aspecting_planet": asp.aspecting_planet.name.title(),
                    "aspected_house": asp.aspected_house,
                    "aspect_type": asp.aspect_type,
                    "strength": asp.strength
                } for asp in aspects
            ]

        # Format response
        return ChartResponse(
            lagna=chart.lagna.rashi_name,
            lagna_degree=chart.lagna.longitude % 30,
            rashi=chart.rashi_name,
            nakshatra=chart.lagna.nakshatra_name,
            planets=planets_mapped,
            houses=houses_mapped,
            dasha=chart.get_current_dasha(datetime.now()),
            vargas=vargas_mapped,
            yogas=yogas_mapped,
            aspect_grid=aspects_mapped,
            transits=None
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid date/time format: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error calculating chart: {str(e)}"
        )


@router.post("/calculate/vedic/vargas/{varga_name}", tags=["Vedic"])
@router.post("/calculate/vargas/{varga_name}", tags=["Vedic"])
async def get_specific_varga(
    varga_name: str,
    request: Request,
    chart_request: ChartRequest,
    api_key: str = Depends(verify_api_key)
):
    """
    Get a specific divisional chart (e.g., D9, D10).
    """
    await check_rate_limit(request, api_key)
    vedic_engine = get_vedic_engine()
    
    from src.engines.vedic.vedic_constants import VargaChart
    try:
        v_type = VargaChart[varga_name.upper()]
    except (KeyError, ValueError):
        raise HTTPException(status_code=400, detail=f"Invalid varga name. Supported: {[v.name for v in VargaChart]}")

    dt_str = f"{chart_request.date_of_birth} {chart_request.time_of_birth}"
    birth_date = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
    chart = vedic_engine.generate_chart(birth_date, chart_request.latitude, chart_request.longitude, chart_request.timezone)
    
    varga_data = {}
    for body, all_vargas in chart.vargas.items():
        pos = all_vargas.get_position(v_type)
        if pos:
            varga_data[body.name.title()] = {
                "sign": pos.rashi.name.title(),
                "division": pos.division_number
            }
            
    return {
        "varga": varga_name.upper(),
        "planets": varga_data
    }


@router.post("/calculate/vedic/yogas", tags=["Vedic"])
@router.post("/calculate/yogas", tags=["Vedic"])
async def get_all_yogas(
    request: Request,
    chart_request: ChartRequest,
    api_key: str = Depends(verify_api_key)
):
    """
    Get all detected yogas for a birth chart.
    """
    await check_rate_limit(request, api_key)
    vedic_engine = get_vedic_engine()
    
    dt_str = f"{chart_request.date_of_birth} {chart_request.time_of_birth}"
    birth_date = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
    chart = vedic_engine.generate_chart(birth_date, chart_request.latitude, chart_request.longitude, chart_request.timezone)
    
    return {
        "count": len([y for y in chart.yogas.detected_yogas if y.is_present]),
        "yogas": [
            {
                "name": y.name,
                "category": y.category.value,
                "forming_planets": [p.name.title() for p in y.forming_planets] if isinstance(y.forming_planets, (list, tuple)) else [y.forming_planets.name.title()],
                "strength": y.strength,
                "conditions": y.conditions_met
            } for y in chart.yogas.detected_yogas if y.is_present
        ]
    }


@router.post("/calculate/vedic/dashas", tags=["Vedic"])
@router.post("/calculate/dashas", tags=["Vedic"])
async def get_dasha_timeline(
    request: Request,
    chart_request: ChartRequest,
    api_key: str = Depends(verify_api_key)
):
    """
    Get comprehensive Vimshottari Dasha timeline (Mahadasha & Antardasha).
    """
    await check_rate_limit(request, api_key)
    vedic_engine = get_vedic_engine()
    
    dt_str = f"{chart_request.date_of_birth} {chart_request.time_of_birth}"
    birth_date = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
    chart = vedic_engine.generate_chart(birth_date, chart_request.latitude, chart_request.longitude, chart_request.timezone)
    
    timeline = []
    for md in chart.dasha.mahadashas:
        ads = chart.dasha.get_antardashas(md)
        timeline.append({
            "mahadasha": md.lord.name.title(),
            "start": md.start_date.isoformat(),
            "end": md.end_date.isoformat(),
            "antardashas": [
                {
                    "lord": ad.lord.name.title(),
                    "start": ad.start_date.isoformat(),
                    "end": ad.end_date.isoformat()
                } for ad in ads
            ]
        })
        
    return {
        "moon_nakshatra": chart.lagna.nakshatra_name,
        "dasha_balance": f"{chart.dasha.dasha_balance.remaining_years:.2f} years of {chart.dasha.dasha_balance.first_lord.name.title()}",
        "timeline": timeline
    }


@router.post("/calculate/vedic/aspects", tags=["Vedic"])
@router.post("/calculate/aspects", tags=["Vedic"])
async def get_aspect_analysis(
    request: Request,
    chart_request: ChartRequest,
    api_key: str = Depends(verify_api_key)
):
    """
    Get detailed aspect analysis (Drishti) for all planets and houses.
    """
    await check_rate_limit(request, api_key)
    vedic_engine = get_vedic_engine()
    
    dt_str = f"{chart_request.date_of_birth} {chart_request.time_of_birth}"
    birth_date = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
    chart = vedic_engine.generate_chart(birth_date, chart_request.latitude, chart_request.longitude, chart_request.timezone)
    
    return {
        "house_aspects": {
            str(h): [
                {
                    "aspecting_planet": asp.aspecting_planet.name.title(),
                    "type": asp.aspect_type,
                    "strength": asp.strength
                } for asp in asps
            ] for h, asps in chart.aspects.house_aspects.items()
        },
        "planet_aspecting_houses": {
            p.name.title(): h_list for p, h_list in chart.aspects.planet_to_houses.items()
        }
    }
# =============================================================================
# WESTERN ASTROLOGY ROUTES
# =============================================================================

@router.post("/calculate/western/chart", response_model=WesternChartResponse, tags=["Western"])
async def calculate_western_chart(
    request: Request,
    chart_request: ChartRequest,
    api_key: str = Depends(verify_api_key),
    western_engine=Depends(get_western_engine)
):
    """
    Calculate a Western Natal Chart (Tropical/Placidus).
    """
    await check_rate_limit(request, api_key)
    try:
        dt_str = f"{chart_request.date_of_birth} {chart_request.time_of_birth}"
        birth_date = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
        
        chart = western_engine.generate_chart(
            birth_datetime=birth_date,
            latitude=chart_request.latitude,
            longitude=chart_request.longitude,
            timezone=chart_request.timezone
        )
        
        # Map Planets
        planets_mapped = {}
        for body, pos in chart.positions.items():
            dignity = chart.get_planet_dignity(body)
            # Use dignity_type value for status list
            status = [dignity.dignity_type.value] if dignity else ["neutral"]
            
            planets_mapped[body.name.title()] = WesternPlanetPosition(
                sign=chart.get_planet_sign(body).name.title(),
                house=chart.get_planet_house(body),
                degree=pos.longitude % 30,
                is_retrograde=pos.is_retrograde,
                speed=pos.speed_longitude,
                dignity_score=dignity.score if dignity else 0,
                dignity_status=status
            )
            
        # Map Houses
        houses_mapped = []
        for h_num, occ in chart.house_occupancy.items():
            houses_mapped.append(WesternHouseData(
                number=h_num,
                cusp_degree=chart.get_house_cusp(h_num) % 30,
                cusp_sign=occ.cusp_sign.name.title(),
                planets=[p.name.title() for p in occ.planets]
            ))
            
        # Map Aspects
        aspects_mapped = []
        for asp in chart.aspects.aspects:
            # Convert AspectStrength enum to numeric value for Pydantic
            strength_map = {
                "exact": 1.0,
                "close": 0.75,
                "moderate": 0.5,
                "wide": 0.25
            }
            numeric_strength = strength_map.get(
                asp.strength.value if hasattr(asp.strength, 'value') else "moderate",
                0.5
            )
            
            aspects_mapped.append(WesternAspect(
                planet1=asp.planet1.name.title() if asp.planet1 else "Unknown",
                planet2=asp.planet2.name.title() if asp.planet2 else "Unknown",
                aspect_type=asp.aspect_type.name.title(),
                orb=asp.orb,
                strength=numeric_strength,
                is_major=asp.is_major
            ))
            
        return WesternChartResponse(
            sun_sign=chart.sun_sign_name,
            moon_sign=chart.moon_sign_name,
            ascendant_sign=chart.ascendant_sign_name,
            midheaven_sign=chart.midheaven_sign.name.title(),
            planets=planets_mapped,
            houses=houses_mapped,
            aspects=aspects_mapped,
            total_dignity_score=chart.dignity_score
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/calculate/western/aspects", tags=["Western"])
async def get_western_aspects(
    request: Request,
    chart_request: ChartRequest,
    api_key: str = Depends(verify_api_key),
    western_engine=Depends(get_western_engine)
):
    """Get all Western aspects for a natal chart."""
    await check_rate_limit(request, api_key)
    dt_str = f"{chart_request.date_of_birth} {chart_request.time_of_birth}"
    birth_date = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
    chart = western_engine.generate_chart(birth_date, chart_request.latitude, chart_request.longitude, chart_request.timezone)
    
    return {
        "aspect_count": chart.aspects.aspect_count,
        "aspects": [
            {
                "p1": asp.planet1.name.title() if asp.planet1 else "Unknown",
                "p2": asp.planet2.name.title() if asp.planet2 else "Unknown",
                "type": asp.aspect_type.name.title(),
                "orb": round(asp.orb, 2),
                "exact": asp.is_exact
            } for asp in chart.aspects.aspects
        ]
    }


# =============================================================================
# CORE ASTRONOMICAL ROUTES
# =============================================================================

@router.post("/calculate/core/ephemeris", response_model=CoreEphemerisResponse, tags=["Core"])
async def get_core_ephemeris(
    request: Request,
    chart_request: ChartRequest,
    ayanamsa: Optional[str] = None,
    api_key: str = Depends(verify_api_key)
):
    """
    Get raw high-precision astronomical positions via Swiss Ephemeris.
    """
    await check_rate_limit(request, api_key)
    try:
        dt_str = f"{chart_request.date_of_birth} {chart_request.time_of_birth}"
        dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
        
        jd = datetime_to_julian_day(dt, timezone_str=chart_request.timezone, latitude=chart_request.latitude, longitude=chart_request.longitude)
        
        # Calculate sidereal if ayanamsa is provided
        aya_val = None
        if ayanamsa:
            try:
                aya_enum = Ayanamsa[ayanamsa.upper()]
                aya_val = get_ayanamsa_value(jd, aya_enum)
                positions = get_all_positions(jd, VEDIC_GRAHAS + WESTERN_PLANETS) # Get all for comprehensive output
            except KeyError:
                raise HTTPException(status_code=400, detail="Invalid Ayanamsa name")
        else:
            positions = get_all_positions(jd, WESTERN_PLANETS)

        # Get cusps (defaulting to Placidus for core)
        cusps = get_house_cusps(jd, chart_request.latitude, chart_request.longitude, HouseSystem.PLACIDUS)
        
        planets_mapped = {}
        for body, pos in positions.items():
            planets_mapped[body.name.title()] = RawPlanetData(
                longitude=pos.longitude,
                latitude=pos.latitude,
                distance=pos.distance,
                speed_longitude=pos.speed_longitude,
                speed_latitude=pos.speed_latitude,
                speed_distance=pos.speed_distance,
                is_retrograde=pos.is_retrograde
            )
            
        return CoreEphemerisResponse(
            julian_day=jd,
            ayanamsa_value=aya_val,
            planets=planets_mapped,
            house_cusps=list(cusps.cusps),
            angles={
                "Ascendant": cusps.ascendant,
                "MC": cusps.mc,
                "Vertex": cusps.vertex,
                "IC": cusps.ic,
                "Descendant": cusps.descendant
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

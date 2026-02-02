"""
Calculation Routes
===================

Birth chart and astrological calculation endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from src.api.schemas.calculation import ChartRequest, ChartResponse
from src.api.middleware.auth import verify_api_key
from src.api.middleware.rate_limit import check_rate_limit
from src.api.dependencies import get_vedic_engine
from datetime import datetime

router = APIRouter()


@router.post("/calculate/chart", response_model=ChartResponse)
async def calculate_chart(
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
        # Parse date and time
        dob_parts = chart_request.date_of_birth.split('-')
        year = int(dob_parts[0])
        month = int(dob_parts[1])
        day = int(dob_parts[2])
        
        tob_parts = chart_request.time_of_birth.split(':')
        hour = int(tob_parts[0])
        minute = int(tob_parts[1])
        second = int(tob_parts[2])
        
        # Calculate chart
        chart_data = vedic_engine.calculate_chart(
            year=year,
            month=month,
            day=day,
            hour=hour,
            minute=minute,
            second=second,
            latitude=chart_request.latitude,
            longitude=chart_request.longitude,
            timezone_offset=0  # Will need to convert timezone string
        )
        
        # Calculate dasha
        dasha_data = vedic_engine.calculate_vimshottari_dasha(
            year=year,
            month=month,
            day=day,
            hour=hour,
            minute=minute,
            second=second,
            latitude=chart_request.latitude,
            longitude=chart_request.longitude
        )
        
        # Format response
        return ChartResponse(
            lagna=chart_data.get('lagna', 'Unknown'),
            rashi=chart_data.get('moon_sign', 'Unknown'),
            nakshatra=chart_data.get('nakshatra', 'Unknown'),
            planets=chart_data.get('planets', {}),
            houses=chart_data.get('houses', []),
            dasha={
                "current": dasha_data.get('current_dasha', 'Unknown'),
                "periods": dasha_data.get('periods', [])
            },
            transits=None  # Can add transit calculation if needed
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


@router.get("/calculate/current-transits")
async def get_current_transits(
    request: Request,
    api_key: str = Depends(verify_api_key)
):
    """
    Get current planetary transits.
    
    Returns current positions of all planets.
    
    **Authentication:** Requires X-API-Key header
    """
    await check_rate_limit(request, api_key)
    
    vedic_engine = get_vedic_engine()
    
    try:
        now = datetime.now()
        
        transits = vedic_engine.calculate_chart(
            year=now.year,
            month=now.month,
            day=now.day,
            hour=now.hour,
            minute=now.minute,
            second=now.second,
            latitude=0,  # For transits, location doesn't matter for planets
            longitude=0,
            timezone_offset=0
        )
        
        return {
            "timestamp": now.isoformat(),
            "planets": transits.get('planets', {})
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error calculating transits: {str(e)}"
        )

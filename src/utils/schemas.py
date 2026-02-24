# src/utils/schemas.py
# src\utils\schemas.py
"""
Pydantic Schemas for Type-Safe Data Flow
=========================================

All data contracts between system components are defined here using Pydantic.
This ensures type safety, automatic validation, and clear API contracts.
"""

from pydantic import BaseModel, Field, validator, field_validator
from datetime import datetime
from typing import Optional, Literal, Dict, List, Any
from enum import Enum


class ChartType(str, Enum):
    """Supported chart calculation types."""
    VEDIC = "vedic"
    WESTERN = "western"
    BOTH = "both"


class BirthDataInput(BaseModel):
    """
    Validated user input for birth data.
    
    This is the primary input schema for all chart calculations.
    All fields are validated for correctness.
    """
    
    date: str = Field(
        ..., 
        description="Birth date in YYYY-MM-DD format",
        examples=["1990-03-15"]
    )
    
    time: str = Field(
        ..., 
        description="Birth time in HH:MM or HH:MM:SS format (24-hour)",
        examples=["15:30", "15:30:00"]
    )
    
    latitude: float = Field(
        ..., 
        ge=-90, 
        le=90,
        description="Geographic latitude (-90 to +90)"
    )
    
    longitude: float = Field(
        ..., 
        ge=-180, 
        le=180,
        description="Geographic longitude (-180 to +180)"
    )
    
    timezone: Optional[str] = Field(
        None,
        description="IANA timezone (e.g., 'Asia/Kolkata'). Auto-detected if not provided.",
        examples=["Asia/Kolkata", "America/New_York", "UTC"]
    )
    
    place_name: Optional[str] = Field(
        None,
        description="Optional place name for display purposes",
        examples=["Jaipur, India", "New York, USA"]
    )
    
    @field_validator('date')
    @classmethod
    def validate_date(cls, v: str) -> str:
        """Validate date format."""
        try:
            datetime.strptime(v, '%Y-%m-%d')
            return v
        except ValueError:
            raise ValueError('Date must be in YYYY-MM-DD format')
    
    @field_validator('time')
    @classmethod
    def validate_time(cls, v: str) -> str:
        """Validate time format."""
        for fmt in ['%H:%M:%S', '%H:%M']:
            try:
                datetime.strptime(v, fmt)
                return v
            except ValueError:
                continue
        raise ValueError('Time must be in HH:MM or HH:MM:SS format (24-hour)')
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "date": "1990-03-15",
                    "time": "15:30",
                    "latitude": 26.9124,
                    "longitude": 75.7873,
                    "timezone": "Asia/Kolkata",
                    "place_name": "Jaipur, India"
                }
            ]
        }
    }


class ChartOptions(BaseModel):
    """Optional configuration for chart calculation."""
    
    ayanamsa: Optional[str] = Field(
        "LAHIRI",
        description="Ayanamsa for Vedic charts"
    )
    
    house_system: Optional[str] = Field(
        "WHOLE_SIGN",
        description="House system (WHOLE_SIGN, PLACIDUS, etc.)"
    )
    
    include_yogas: bool = Field(
        True,
        description="Calculate yogas (Vedic only)"
    )
    
    include_dasha: bool = Field(
        True,
        description="Calculate dasha periods (Vedic only)"
    )
    
    include_divisional: bool = Field(
        False,
        description="Calculate divisional charts (resource intensive)"
    )
    
    include_aspects: bool = Field(
        True,
        description="Calculate planetary aspects"
    )


class ChartRequest(BaseModel):
    """Complete request for chart calculation."""
    
    birth_data: BirthDataInput
    chart_type: ChartType = Field(
        ChartType.VEDIC,
        description="Type of chart to calculate"
    )
    options: Optional[ChartOptions] = Field(
        default_factory=ChartOptions,
        description="Optional calculation parameters"
    )
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "birth_data": {
                        "date": "1990-03-15",
                        "time": "15:30",
                        "latitude": 26.9124,
                        "longitude": 75.7873,
                        "timezone": "Asia/Kolkata"
                    },
                    "chart_type": "vedic",
                    "options": {
                        "include_yogas": True,
                        "include_dasha": True
                    }
                }
            ]
        }
    }


class CalculationMetadata(BaseModel):
    """Metadata about the calculation process."""
    
    computation_time_ms: float
    julian_day: float
    ayanamsa_value: Optional[float] = None
    house_system: str
    timestamp: datetime = Field(default_factory=datetime.now)
    engine_version: str = "1.0.0"


class ChartResponse(BaseModel):
    """Response containing calculated chart data."""
    
    chart_type: ChartType
    chart_data: Dict[str, Any]
    summary: Optional[str] = Field(
        None,
        description="Human-readable summary"
    )
    metadata: CalculationMetadata
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "chart_type": "vedic",
                    "chart_data": {
                        "lagna": {
                            "sign": "Taurus",
                            "degree": 15
                        }
                    },
                    "summary": "Vedic chart calculated successfully",
                    "metadata": {
                        "computation_time_ms": 245.5,
                        "julian_day": 2448000.5,
                        "house_system": "WHOLE_SIGN"
                    }
                }
            ]
        }
    }


class ChatMessage(BaseModel):
    """Message in a conversation."""
    
    role: Literal["user", "assistant", "system"]
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: Optional[Dict[str, Any]] = None


class ChatRequest(BaseModel):
    """Request for chat-based interaction."""
    
    message: str = Field(
        ...,
        description="User's message/query",
        min_length=1,
        max_length=2000
    )
    
    birth_data: Optional[BirthDataInput] = Field(
        None,
        description="Birth data if relevant to query"
    )
    
    conversation_id: Optional[str] = Field(
        None,
        description="ID for continuing a conversation"
    )
    
    context: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional context for the query"
    )
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "message": "What does my Sun in Aries mean?",
                    "birth_data": {
                        "date": "1990-03-15",
                        "time": "15:30",
                        "latitude": 26.9124,
                        "longitude": 75.7873
                    }
                }
            ]
        }
    }


class ChatResponse(BaseModel):
    """Response from the chatbot."""
    
    message: str
    chart_data: Optional[Dict[str, Any]] = None
    sources: Optional[List[Dict[str, str]]] = Field(
        None,
        description="RAG sources used for the response"
    )
    confidence: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Confidence score for the response"
    )
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    """Standardized error response."""
    
    error: str
    error_code: str
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.now)
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "error": "Invalid birth date format",
                    "error_code": "INVALID_INPUT",
                    "details": {
                        "field": "date",
                        "provided_value": "15-03-1990"
                    }
                }
            ]
        }
    }

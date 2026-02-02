"""
User Schemas - Pydantic Models
================================

Request and response models for user management endpoints.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict
import re


class BirthData(BaseModel):
    """Birth data model."""
    date_of_birth: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="Date in YYYY-MM-DD format")
    time_of_birth: str = Field(..., pattern=r"^\d{2}:\d{2}:\d{2}$", description="Time in HH:MM:SS format")
    place_of_birth: Optional[str] = Field(None, description="Birth place name")
    latitude: float = Field(..., ge=-90, le=90, description="Latitude")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude")
    timezone: str = Field(default="UTC", description="Timezone (e.g., 'Asia/Kolkata')")
    
    class Config:
        json_schema_extra = {
            "example": {
                "date_of_birth": "1990-03-15",
                "time_of_birth": "14:30:00",
                "place_of_birth": "Jaipur, India",
                "latitude": 26.9124,
                "longitude": 75.7873,
                "timezone": "Asia/Kolkata"
            }
        }


class UserPreferences(BaseModel):
    """User preferences."""
    astrology_system: str = Field(default="vedic", pattern="^(vedic|western)$")
    language: str = Field(default="en")


class UserProfile(BaseModel):
    """User profile model."""
    user_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    email: Optional[str] = Field(None)
    birth_data: BirthData
    preferences: Optional[UserPreferences] = Field(default_factory=UserPreferences)
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "user123",
                "name": "Arjun Kumar",
                "email": "arjun@example.com",
                "birth_data": {
                    "date_of_birth": "1990-03-15",
                    "time_of_birth": "14:30:00",
                    "latitude": 26.9124,
                    "longitude": 75.7873,
                    "timezone": "Asia/Kolkata"
                },
                "preferences": {
                    "astrology_system": "vedic",
                    "language": "en"
                }
            }
        }


class UserUpdate(BaseModel):
    """User update request."""
    name: Optional[str] = Field(None, min_length=1)
    email: Optional[str] = None
    birth_data: Optional[BirthData] = None
    preferences: Optional[UserPreferences] = None


class UserResponse(BaseModel):
    """User response model."""
    user_id: str
    name: str
    email: Optional[str]
    birth_data: BirthData
    preferences: UserPreferences
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

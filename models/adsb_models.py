"""
Pydantic models for ADS-B aircraft tracking API.
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

class AircraftResponse(BaseModel):
    """Aircraft data response model."""

    icao24: str = Field(..., description="ICAO 24-bit aircraft identifier (hex code)")
    callsign: Optional[str] = Field(None, description="Flight callsign/identifier")
    latitude: Optional[float] = Field(None, description="Aircraft latitude in decimal degrees")
    longitude: Optional[float] = Field(None, description="Aircraft longitude in decimal degrees")
    altitude: Optional[float] = Field(None, description="Aircraft altitude in feet")
    ground_speed: Optional[float] = Field(None, description="Ground speed in knots")
    track: Optional[float] = Field(None, description="Track angle in degrees (0-360)")
    vertical_rate: Optional[float] = Field(None, description="Vertical rate in feet per minute")
    is_on_ground: Optional[bool] = Field(None, description="Whether aircraft is on ground")
    last_seen: datetime = Field(..., description="Last time aircraft was observed")
    first_seen: datetime = Field(..., description="First time aircraft was observed in current session")

    # Optional enriched data (if available)
    registration: Optional[str] = Field(None, description="Aircraft registration/tail number")
    aircraft_type: Optional[str] = Field(None, description="Aircraft type/model")
    airline: Optional[str] = Field(None, description="Operating airline")
    photo_url: Optional[str] = Field(None, description="Aircraft thumbnail photo URL")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
        json_schema_extra = {
            "example": {
                "icao24": "40621D",
                "callsign": "BAW123",
                "latitude": 51.4706,
                "longitude": -0.4619,
                "altitude": 35000.0,
                "ground_speed": 450.5,
                "track": 89.2,
                "vertical_rate": 0.0,
                "is_on_ground": False,
                "last_seen": "2026-02-11T12:00:00Z",
                "first_seen": "2026-02-11T11:45:00Z",
                "registration": "G-STBC",
                "aircraft_type": "Boeing 777-36N",
                "airline": "British Airways",
                "photo_url": "https://image.airport-data.com/aircraft/001912010.jpg"
            }
        }

class AircraftListResponse(BaseModel):
    """Response model for multiple aircraft."""

    aircraft: List[AircraftResponse] = Field(..., description="List of aircraft")
    total_count: int = Field(..., description="Total number of aircraft returned")
    timestamp: datetime = Field(default_factory=datetime.now, description="Response timestamp")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
        json_schema_extra = {
            "example": {
                "aircraft": [
                    {
                        "icao24": "40621D",
                        "callsign": "BAW123",
                        "latitude": 51.4706,
                        "longitude": -0.4619,
                        "altitude": 35000.0,
                        "ground_speed": 450.5,
                        "track": 89.2,
                        "vertical_rate": 0.0,
                        "is_on_ground": False,
                        "last_seen": "2026-02-11T12:00:00Z",
                        "first_seen": "2026-02-11T11:45:00Z",
                        "registration": "G-STBC",
                        "aircraft_type": "Boeing 777-36N",
                        "airline": "British Airways",
                        "photo_url": "https://image.airport-data.com/aircraft/001912010.jpg"
                    },
                    {
                        "icao24": "A0B1C2",
                        "callsign": "AAL456",
                        "latitude": 40.7128,
                        "longitude": -74.0060,
                        "altitude": 28000.0,
                        "ground_speed": 420.0,
                        "track": 270.5,
                        "vertical_rate": -500.0,
                        "is_on_ground": False,
                        "last_seen": "2026-02-11T12:00:15Z",
                        "first_seen": "2026-02-11T11:30:00Z",
                        "registration": "N123AA",
                        "aircraft_type": "Airbus A321neo",
                        "airline": "American Airlines",
                        "photo_url": "https://image.airport-data.com/aircraft/001800123.jpg"
                    }
                ],
                "total_count": 2,
                "timestamp": "2026-02-11T12:00:30Z"
            }
        }

class GeographicFilter(BaseModel):
    """Geographic filtering parameters."""
    
    latitude: float = Field(..., ge=-90, le=90, description="Center latitude in decimal degrees")
    longitude: float = Field(..., ge=-180, le=180, description="Center longitude in decimal degrees")
    radius: float = Field(..., gt=0, le=1000, description="Search radius in kilometers")

class BoundingBoxFilter(BaseModel):
    """Bounding box filtering parameters."""
    
    lat1: float = Field(..., ge=-90, le=90, description="Southwest latitude")
    lon1: float = Field(..., ge=-180, le=180, description="Southwest longitude")
    lat2: float = Field(..., ge=-90, le=90, description="Northeast latitude") 
    lon2: float = Field(..., ge=-180, le=180, description="Northeast longitude")
    
    @validator('lat2')
    def lat2_must_be_greater_than_lat1(cls, v, values):
        if 'lat1' in values and v <= values['lat1']:
            raise ValueError('lat2 must be greater than lat1')
        return v
    
    @validator('lon2')
    def lon2_must_be_greater_than_lon1(cls, v, values):
        if 'lon1' in values and v <= values['lon1']:
            raise ValueError('lon2 must be greater than lon1')
        return v

class AltitudeFilter(BaseModel):
    """Altitude filtering parameters."""
    
    min_altitude: Optional[int] = Field(None, ge=0, le=60000, description="Minimum altitude in feet")
    max_altitude: Optional[int] = Field(None, ge=0, le=60000, description="Maximum altitude in feet")
    
    @validator('max_altitude')
    def max_altitude_must_be_greater_than_min(cls, v, values):
        if v is not None and 'min_altitude' in values and values['min_altitude'] is not None:
            if v <= values['min_altitude']:
                raise ValueError('max_altitude must be greater than min_altitude')
        return v

class SpeedFilter(BaseModel):
    """Ground speed filtering parameters."""
    
    min_speed: Optional[float] = Field(None, ge=0, le=1000, description="Minimum ground speed in knots")
    max_speed: Optional[float] = Field(None, ge=0, le=1000, description="Maximum ground speed in knots")
    
    @validator('max_speed')
    def max_speed_must_be_greater_than_min(cls, v, values):
        if v is not None and 'min_speed' in values and values['min_speed'] is not None:
            if v <= values['min_speed']:
                raise ValueError('max_speed must be greater than min_speed')
        return v

class SquawkCodeType(str, Enum):
    """Common squawk codes."""
    VFR = "1200"  # Standard VFR
    EMERGENCY = "7700"  # Emergency
    RADIO_FAILURE = "7600"  # Radio failure
    HIJACK = "7500"  # Hijack/unlawful interference

class ErrorResponse(BaseModel):
    """Standard error response model."""
    
    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Additional error details")
    timestamp: datetime = Field(default_factory=datetime.now, description="Error timestamp")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class HealthResponse(BaseModel):
    """ADS-B service health response."""
    
    status: str = Field(..., description="Service status")
    connected: bool = Field(..., description="Whether connected to ADS-B Hub")
    active_aircraft_count: int = Field(..., description="Number of currently tracked aircraft")
    connection_uptime: Optional[float] = Field(None, description="Connection uptime in seconds")
    last_message_received: Optional[datetime] = Field(None, description="Timestamp of last received message")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
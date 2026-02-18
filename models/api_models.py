"""
Pydantic models for API request/response schemas to ensure proper OpenAPI type generation
"""

from pydantic import BaseModel, Field
from typing import Optional


class ICAOParameter(BaseModel):
    """ICAO airport code parameter model"""
    icao: str = Field(..., description="4-letter ICAO airport code", min_length=4, max_length=4, regex="^[A-Z]{4}$", example="KJFK")


class FlightNumberParameter(BaseModel):
    """Flight number parameter model"""
    flight_number: str = Field(..., description="Flight number", min_length=2, max_length=10, regex="^[A-Z0-9]+$", example="BAW123")


class AirportSearchParams(BaseModel):
    """Airport search parameters"""
    icao: Optional[str] = Field(None, description="4-letter ICAO airport code", min_length=4, max_length=4, regex="^[A-Z]{4}$", example="KJFK")
    iata: Optional[str] = Field(None, description="3-letter IATA airport code", min_length=3, max_length=3, regex="^[A-Z]{3}$", example="JFK")


class AirlineSearchParams(BaseModel):
    """Airline search parameters"""
    icao: Optional[str] = Field(None, description="3-letter ICAO airline code", min_length=3, max_length=3, regex="^[A-Z]{3}$", example="BAW")
    iata: Optional[str] = Field(None, description="2-letter IATA airline code", min_length=2, max_length=2, regex="^[A-Z]{2}$", example="BA")
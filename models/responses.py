from pydantic import BaseModel, Field
from typing import List, Optional, Any, Dict
from datetime import datetime

class ErrorResponse(BaseModel):
    """Standard error response model"""
    error: str = Field(description="Error type")
    message: str = Field(description="Detailed error message")
    timestamp: datetime = Field(default_factory=datetime.now, description="Error timestamp")
    
    class Config:
        json_schema_extra = {
            "example": {
                "error": "NOT_FOUND",
                "message": "Airport with code 'INVALID' not found",
                "timestamp": "2024-01-01T12:00:00Z"
            }
        }

class SuccessResponse(BaseModel):
    """Standard success response model"""
    success: bool = Field(True, description="Operation success status")
    data: Optional[Any] = Field(None, description="Response data")
    count: Optional[int] = Field(None, description="Number of items returned")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "data": [],
                "count": 0
            }
        }

class HealthResponse(BaseModel):
    """Health check response model"""
    status: str = Field(description="Service status")
    version: str = Field(description="API version")
    timestamp: datetime = Field(default_factory=datetime.now, description="Health check timestamp")
    services: Dict[str, str] = Field(description="Status of dependent services")
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "version": "1.0.0",
                "timestamp": "2024-01-01T12:00:00Z",
                "services": {
                    "database": "connected",
                    "external_apis": "operational"
                }
            }
        }

class PaginationResponse(BaseModel):
    """Paginated response model"""
    items: List[Any] = Field(description="List of items")
    total: int = Field(description="Total number of items")
    page: int = Field(description="Current page number")
    per_page: int = Field(description="Items per page")
    total_pages: int = Field(description="Total number of pages")
    has_next: bool = Field(description="Whether there is a next page")
    has_prev: bool = Field(description="Whether there is a previous page")
    
    class Config:
        json_schema_extra = {
            "example": {
                "items": [],
                "total": 100,
                "page": 1,
                "per_page": 10,
                "total_pages": 10,
                "has_next": True,
                "has_prev": False
            }
        }

class WeatherResponse(BaseModel):
    """Weather data response model"""
    airport_code: str = Field(description="Airport ICAO code")
    metar: Optional[str] = Field(None, description="METAR weather report")
    taf: Optional[str] = Field(None, description="TAF weather forecast")
    timestamp: datetime = Field(default_factory=datetime.now, description="Data timestamp")
    
    class Config:
        json_schema_extra = {
            "example": {
                "airport_code": "KJFK",
                "metar": "KJFK 121251Z 23016KT 10SM FEW250 06/M08 A3014 RMK AO2 SLP223 T00611083",
                "taf": "KJFK 121120Z 1212/1318 23015KT P6SM FEW250...",
                "timestamp": "2024-01-01T12:00:00Z"
            }
        }

class FlightStatusResponse(BaseModel):
    """Flight status response model"""
    flight_number: str = Field(description="Flight number")
    airline: Optional[str] = Field(None, description="Airline name")
    status: str = Field(description="Flight status")
    departure: Optional[Dict[str, Any]] = Field(None, description="Departure information")
    arrival: Optional[Dict[str, Any]] = Field(None, description="Arrival information")
    aircraft: Optional[Dict[str, Any]] = Field(None, description="Aircraft information")
    timestamp: datetime = Field(default_factory=datetime.now, description="Status timestamp")
    
    class Config:
        json_schema_extra = {
            "example": {
                "flight_number": "AA123",
                "airline": "American Airlines",
                "status": "On Time",
                "departure": {
                    "airport": "KJFK",
                    "scheduled": "2024-01-01T10:00:00Z",
                    "estimated": "2024-01-01T10:00:00Z"
                },
                "arrival": {
                    "airport": "KLAX",
                    "scheduled": "2024-01-01T13:30:00Z",
                    "estimated": "2024-01-01T13:30:00Z"
                },
                "aircraft": {
                    "type": "Boeing 737-800",
                    "registration": "N123AA"
                },
                "timestamp": "2024-01-01T12:00:00Z"
            }
        }
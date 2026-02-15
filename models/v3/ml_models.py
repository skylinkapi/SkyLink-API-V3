# ML-specific models
from pydantic import BaseModel
from typing import Dict, Any, List
from datetime import datetime

class MLModelInfo(BaseModel):
    name: str
    version: str
    trained_date: datetime
    features: List[str]
    target: str
    performance_metrics: Dict[str, float]

class FlightTimePredictionInput(BaseModel):
    distance_km: float
    aircraft_type: str
    departure_time: Optional[str] = None
    weather_conditions: Optional[Dict[str, Any]] = None

class DelayPredictionInput(BaseModel):
    flight_number: str
    departure_icao: str
    arrival_icao: str
    scheduled_departure: datetime
    airline: str
    aircraft_type: Optional[str] = None
    historical_delays: Optional[List[int]] = None
    weather_data: Optional[Dict[str, Any]] = None
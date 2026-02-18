"""Pydantic models for ML flight time prediction."""

from typing import Optional

from pydantic import BaseModel, Field


class FlightTimePrediction(BaseModel):
    """Predicted flight time between two airports."""

    origin: str = Field(..., description="Origin airport ICAO code")
    destination: str = Field(..., description="Destination airport ICAO code")
    aircraft_type: Optional[str] = Field(None, description="Aircraft type code (e.g. B738, A320)")
    distance_nm: float = Field(..., description="Great-circle distance in nautical miles")
    estimated_minutes: int = Field(..., description="Estimated flight time in minutes")
    estimated_hours_display: str = Field(
        ..., description="Human-readable flight time (e.g. '7h 23m')"
    )
    min_minutes: int = Field(..., description="Lower bound estimate in minutes")
    max_minutes: int = Field(..., description="Upper bound estimate in minutes")
    model_version: str = Field(..., description="Model artifact version")

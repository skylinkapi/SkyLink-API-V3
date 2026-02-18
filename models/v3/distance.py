from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class DistanceUnit(str, Enum):
    NAUTICAL_MILES = "nm"
    KILOMETERS = "km"
    MILES = "mi"


class Coordinates(BaseModel):
    latitude: float = Field(..., description="Latitude in decimal degrees")
    longitude: float = Field(..., description="Longitude in decimal degrees")
    icao_code: Optional[str] = Field(None, description="ICAO airport code (if resolved from airport)")
    iata_code: Optional[str] = Field(None, description="IATA airport code (if available)")
    name: Optional[str] = Field(None, description="Airport/waypoint name")


class DistanceResponse(BaseModel):
    from_point: Coordinates = Field(..., description="Origin point")
    to_point: Coordinates = Field(..., description="Destination point")
    distance: float = Field(..., description="Great circle distance")
    unit: DistanceUnit = Field(..., description="Distance unit")
    bearing: float = Field(..., description="Initial bearing in degrees from north (0-360)")
    bearing_cardinal: str = Field(..., description="Cardinal direction (e.g. NE, SW)")
    midpoint: Coordinates = Field(..., description="Geographic midpoint of the route")

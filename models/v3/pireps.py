"""Pydantic models for PIREPs (Pilot Reports)."""

from typing import List, Optional

from pydantic import BaseModel, Field


class PIREPReport(BaseModel):
    raw: str = Field(..., description="Raw PIREP text")
    report_type: Optional[str] = Field(None, description="UA (routine) or UUA (urgent)")
    location: Optional[str] = Field(None, description="Location identifier or bearing/distance from navaid")
    time: Optional[str] = Field(None, description="Observation time (UTC)")
    altitude: Optional[str] = Field(None, description="Flight level or altitude")
    aircraft_type: Optional[str] = Field(None, description="Aircraft type code")
    sky_conditions: Optional[str] = Field(None, description="Sky/cloud conditions")
    turbulence: Optional[str] = Field(None, description="Turbulence intensity and type")
    icing: Optional[str] = Field(None, description="Icing intensity and type")
    temperature: Optional[str] = Field(None, description="Outside air temperature")
    wind: Optional[str] = Field(None, description="Wind direction and speed")
    remarks: Optional[str] = Field(None, description="Additional remarks")
    latitude: Optional[float] = Field(None, description="Latitude of the report")
    longitude: Optional[float] = Field(None, description="Longitude of the report")


class PIREPResponse(BaseModel):
    icao: str = Field(..., description="Requested ICAO airport code")
    radius_nm: int = Field(..., description="Search radius in nautical miles")
    hours: int = Field(..., description="Time window in hours")
    reports: List[PIREPReport] = Field(default_factory=list, description="PIREP reports found")
    total: int = Field(0, description="Total number of PIREPs returned")

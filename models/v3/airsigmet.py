"""Pydantic models for AIRMET/SIGMET advisories."""

from typing import List, Optional

from pydantic import BaseModel, Field


class AirSigmetCoord(BaseModel):
    lat: float = Field(..., description="Latitude")
    lon: float = Field(..., description="Longitude")


class AirSigmetMovement(BaseModel):
    direction: Optional[str] = Field(None, description="Movement direction (degrees or repr)")
    speed: Optional[str] = Field(None, description="Movement speed")


class AirSigmetObservation(BaseModel):
    type: Optional[str] = Field(None, description="Weather phenomenon type (e.g. TURB, ICE, IFR)")
    intensity: Optional[str] = Field(None, description="Intensity (e.g. MOD, SEV)")
    floor: Optional[str] = Field(None, description="Lower altitude bound")
    ceiling: Optional[str] = Field(None, description="Upper altitude bound")
    coords: List[AirSigmetCoord] = Field(default_factory=list, description="Boundary polygon coordinates")
    movement: Optional[AirSigmetMovement] = Field(None, description="Movement direction and speed")


class AirSigmetReport(BaseModel):
    raw: str = Field(..., description="Raw AIRMET/SIGMET text")
    bulletin_type: Optional[str] = Field(None, description="Bulletin type (SIGMET or AIRMET)")
    country: Optional[str] = Field(None, description="Issuing country code")
    issuer: Optional[str] = Field(None, description="Issuing authority")
    area: Optional[str] = Field(None, description="Affected area identifier")
    report_type: Optional[str] = Field(None, description="Advisory type (AIRMET, SIGMET, CONVECTIVE SIGMET)")
    start_time: Optional[str] = Field(None, description="Valid from (UTC)")
    end_time: Optional[str] = Field(None, description="Valid until (UTC)")
    body: Optional[str] = Field(None, description="Report body text")
    region: Optional[str] = Field(None, description="Affected FIR/region")
    observation: Optional[AirSigmetObservation] = Field(None, description="Observed conditions")
    forecast: Optional[AirSigmetObservation] = Field(None, description="Forecast conditions")


class AirSigmetResponse(BaseModel):
    reports: List[AirSigmetReport] = Field(default_factory=list, description="AIRMET/SIGMET advisories")
    total: int = Field(0, description="Total number of advisories returned")
    filter_type: Optional[str] = Field(None, description="Type filter applied (airmet, sigmet, or all)")

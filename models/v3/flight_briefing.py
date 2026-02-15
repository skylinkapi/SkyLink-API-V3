"""Pydantic models for AI-powered flight briefings."""

from typing import List, Optional

from pydantic import BaseModel, Field


class BriefingRestriction(BaseModel):
    icao: str = Field(..., description="Airport ICAO code")
    description: str = Field(..., description="Plain-language description of the restriction")
    affected: Optional[str] = Field(None, description="Affected element (e.g. RWY 29 · TWY E3)")
    notam_id: Optional[str] = Field(None, description="NOTAM ID if applicable")


class BriefingNotam(BaseModel):
    title: str = Field(..., description="Brief title of the NOTAM")
    description: str = Field(..., description="Plain-language operational explanation")
    affected: Optional[str] = Field(None, description="Affected element")
    notam_id: Optional[str] = Field(None, description="NOTAM identifier")


class BriefingPirep(BaseModel):
    raw: str = Field(..., description="Raw PIREP text")
    summary: str = Field(..., description="Plain-language summary")


class BriefingWeather(BaseModel):
    metar_raw: Optional[str] = Field(None, description="Raw METAR text")
    taf_raw: Optional[str] = Field(None, description="Raw TAF text")
    conditions: Optional[str] = Field(None, description="Plain-language weather summary")


class AirportBriefing(BaseModel):
    icao: str = Field(..., description="Airport ICAO code")
    weather: Optional[BriefingWeather] = Field(None, description="Weather data")
    notams: Optional[List[BriefingNotam]] = Field(None, description="Operationally relevant NOTAMs")
    pireps: Optional[List[BriefingPirep]] = Field(None, description="Pilot reports near airport")



class FlightBriefingTextResponse(BaseModel):
    origin: str = Field(..., description="Origin ICAO code")
    destination: str = Field(..., description="Destination ICAO code")
    format: str = Field(..., description="Output format (markdown, plain_text, or html)")
    briefing: str = Field(..., description="AI-generated flight briefing in the requested format")
    data_included: List[str] = Field(
        default_factory=list,
        description="Data sources included (e.g. ['metar', 'taf', 'notams', 'pireps'])",
    )
    disclaimer: str = Field(
        default="This briefing is AI-generated and for informational purposes only. "
                "Always verify with official sources before flight operations.",
        description="Legal disclaimer",
    )


class FlightBriefingResponse(BaseModel):
    origin: str = Field(..., description="Origin ICAO code")
    destination: str = Field(..., description="Destination ICAO code")
    summary: str = Field(..., description="2-3 sentence overview of the flight")
    critical_restrictions: List[BriefingRestriction] = Field(
        default_factory=list,
        description="Items that could prevent or significantly alter the flight",
    )
    origin_briefing: AirportBriefing = Field(..., description="Origin airport briefing")
    destination_briefing: AirportBriefing = Field(..., description="Destination airport briefing")
    data_included: List[str] = Field(
        default_factory=list,
        description="Data sources included (e.g. ['metar', 'taf', 'notams', 'pireps'])",
    )
    disclaimer: str = Field(
        default="This briefing is AI-generated and for informational purposes only. "
                "Always verify with official sources before flight operations.",
        description="Legal disclaimer",
    )

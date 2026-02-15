"""Pydantic models for NOTAMs (Notices to Air Missions)."""

from typing import List, Optional

from pydantic import BaseModel, Field


class NOTAMEntry(BaseModel):
    raw: str = Field(..., description="Full raw NOTAM text")
    notam_id: Optional[str] = Field(None, description="NOTAM identifier (e.g. A0001/24)")
    type: Optional[str] = Field(None, description="NOTAM type: N (new), R (replace), C (cancel)")
    location: Optional[str] = Field(None, description="Affected location identifier")
    effective: Optional[str] = Field(None, description="Effective (start) date/time UTC")
    expiration: Optional[str] = Field(None, description="Expiration (end) date/time UTC")
    body: Optional[str] = Field(None, description="NOTAM body text (E field)")


class NOTAMResponse(BaseModel):
    icao: str = Field(..., description="Requested ICAO airport code")
    notams: List[NOTAMEntry] = Field(default_factory=list, description="Active NOTAMs")
    total: int = Field(0, description="Total number of NOTAMs returned")

"""Pydantic models for FAA Delay alerts."""

from typing import List, Optional

from pydantic import BaseModel, Field


class GroundDelay(BaseModel):
    airport: str = Field(..., description="Airport ICAO or FAA identifier")
    airport_name: Optional[str] = Field(None, description="Airport name")
    reason: str = Field(..., description="Reason for the delay")
    avg_delay: Optional[str] = Field(None, description="Average delay duration")
    max_delay: Optional[str] = Field(None, description="Maximum delay duration")


class GroundStop(BaseModel):
    airport: str = Field(..., description="Airport ICAO or FAA identifier")
    airport_name: Optional[str] = Field(None, description="Airport name")
    reason: str = Field(..., description="Reason for the ground stop")
    end_time: Optional[str] = Field(None, description="Expected end time (UTC)")


class Closure(BaseModel):
    airport: str = Field(..., description="Airport ICAO or FAA identifier")
    airport_name: Optional[str] = Field(None, description="Airport name")
    reason: str = Field(..., description="Reason for closure")
    begin: Optional[str] = Field(None, description="Closure start time (UTC)")
    reopen: Optional[str] = Field(None, description="Expected reopen time (UTC)")


class AirspaceFlowProgram(BaseModel):
    facility: str = Field(..., description="ATC facility (ARTCC) identifier")
    reason: str = Field(..., description="Reason for the program")
    fca_start: Optional[str] = Field(None, description="Flow constrained area start time")
    fca_end: Optional[str] = Field(None, description="Flow constrained area end time")


class FAADelayResponse(BaseModel):
    ground_delays: List[GroundDelay] = Field(default_factory=list, description="Active ground delay programs")
    ground_stops: List[GroundStop] = Field(default_factory=list, description="Active ground stops")
    closures: List[Closure] = Field(default_factory=list, description="Airport closures")
    airspace_flow_programs: List[AirspaceFlowProgram] = Field(
        default_factory=list, description="Airspace flow programs"
    )
    total_alerts: int = Field(0, description="Total number of active alerts")
    message: Optional[str] = Field(None, description="Status message when no delays exist")

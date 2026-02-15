from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class ChartCategory(str, Enum):
    GEN = "GEN"    # General information
    GND = "GND"    # Ground charts / airport diagrams
    SID = "SID"    # Standard Instrument Departure
    STAR = "STAR"  # Standard Terminal Arrival Route
    APP = "APP"    # Approach procedures


class Chart(BaseModel):
    name: str = Field(..., description="Chart name/title")
    url: str = Field(..., description="Direct URL to chart PDF")
    category: ChartCategory = Field(..., description="Chart category")


class ChartsResponse(BaseModel):
    icao_code: str = Field(..., description="ICAO airport code")
    source: str = Field(..., description="Chart data source identifier")
    charts: Dict[ChartCategory, List[Chart]] = Field(
        default_factory=dict,
        description="Charts organized by category"
    )
    total_count: int = Field(..., description="Total number of charts found")
    fetched_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp of when charts were fetched"
    )


class SourceInfo(BaseModel):
    source_id: str = Field(..., description="Source identifier")
    name: str = Field(..., description="Human-readable source name")
    icao_prefixes: List[str] = Field(..., description="ICAO prefixes handled by this source")


class SourcesResponse(BaseModel):
    sources: List[SourceInfo]
    total_count: int

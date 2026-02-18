from typing import Optional, List

from pydantic import BaseModel, Field


class AircraftPhoto(BaseModel):
    image: str = Field(..., description="Full-size photo URL")
    link: str = Field(..., description="Link to photo page on airport-data.com")
    photographer: str = Field(..., description="Photographer name")


class AircraftDetails(BaseModel):
    registration: Optional[str] = Field(None, description="Aircraft registration / tail number")
    icao24: Optional[str] = Field(None, description="ICAO 24-bit transponder address")
    icao_type: Optional[str] = Field(None, description="ICAO aircraft type designator")
    type_name: Optional[str] = Field(None, description="Aircraft model name")
    manufacturer: Optional[str] = Field(None, description="Aircraft manufacturer")
    owner_operator: Optional[str] = Field(None, description="Owner or operator")
    is_military: bool = Field(False, description="Military aircraft flag")
    year_built: Optional[str] = Field(None, description="Year of manufacture")
    photos: List[AircraftPhoto] = Field(default_factory=list, description="Aircraft photos")


class AircraftLookupResponse(BaseModel):
    query: str = Field(..., description="The registration or ICAO24 that was looked up")
    found: bool = Field(..., description="Whether the aircraft was found")
    aircraft: Optional[AircraftDetails] = Field(None, description="Aircraft details (if found)")


class AircraftDatabaseStats(BaseModel):
    loaded: bool
    total_icao_entries: int
    total_registration_entries: int
    database_file: str

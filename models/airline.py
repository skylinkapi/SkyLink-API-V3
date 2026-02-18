from pydantic import BaseModel, Field
from typing import Optional

class Airline(BaseModel):
    """Airline information model"""
    id: int = Field(description="Unique airline identifier")
    name: str = Field(description="Full airline name")
    alias: Optional[str] = Field(None, description="Alternative airline name")
    iata: Optional[str] = Field(None, description="2-letter IATA airline code")
    icao: Optional[str] = Field(None, description="3-letter ICAO airline code")
    callsign: Optional[str] = Field(None, description="Radio callsign used by pilots")
    country: Optional[str] = Field(None, description="Country where airline is based")
    active: Optional[str] = Field(None, description="Whether airline is currently active (Y/N)")
    logo: Optional[str] = Field(None, description="URL to airline logo image")
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": 1,
                "name": "American Airlines",
                "alias": "American",
                "iata": "AA",
                "icao": "AAL",
                "callsign": "AMERICAN",
                "country": "United States",
                "active": "Y",
                "logo": "https://media.skylinkapi.com/logos/AA.png"
            }
        }

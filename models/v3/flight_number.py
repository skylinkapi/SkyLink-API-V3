from typing import Optional

from pydantic import BaseModel, Field


class ParsedFlightNumber(BaseModel):
    original: str = Field(..., description="Original input string")
    airline_code: str = Field(..., description="Extracted airline code (IATA or ICAO)")
    flight_number: str = Field(..., description="Numeric flight number portion")
    iata_code: Optional[str] = Field(None, description="2-letter IATA airline code")
    icao_code: Optional[str] = Field(None, description="3-letter ICAO airline code")
    iata_format: Optional[str] = Field(None, description="Flight in IATA format (e.g. BA123)")
    icao_format: Optional[str] = Field(None, description="Flight in ICAO format (e.g. BAW123)")
    airline_name: Optional[str] = Field(None, description="Full airline name")
    callsign: Optional[str] = Field(None, description="Airline radio callsign")
    country: Optional[str] = Field(None, description="Airline country of registration")

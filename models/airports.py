from pydantic import BaseModel, Field, validator
from typing import Optional, List

class Airport(BaseModel):
    """Airport information model"""
    id: int = Field(description="Unique airport identifier")
    ident: str = Field(description="Airport identifier (usually ICAO code)")
    type: str = Field(description="Type of airport (large_airport, medium_airport, etc.)")
    name: str = Field(description="Full airport name")
    latitude_deg: Optional[float] = Field(None, description="Latitude in decimal degrees")
    longitude_deg: Optional[float] = Field(None, description="Longitude in decimal degrees")
    elevation_ft: Optional[float] = Field(None, description="Elevation in feet above sea level")
    continent: Optional[str] = Field(None, description="Continent code (AF, AN, AS, EU, NA, OC, SA)")
    iso_country: Optional[str] = Field(None, description="ISO country code")
    iso_region: Optional[str] = Field(None, description="ISO region code")
    municipality: Optional[str] = Field(None, description="City or municipality name")
    scheduled_service: Optional[str] = Field(None, description="Whether airport has scheduled service (yes/no)")
    gps_code: Optional[str] = Field(None, description="GPS code for navigation")
    iata_code: Optional[str] = Field(None, description="3-letter IATA airport code")
    local_code: Optional[str] = Field(None, description="Local airport code")
    home_link: Optional[str] = Field(None, description="Airport website URL")
    wikipedia_link: Optional[str] = Field(None, description="Wikipedia page URL")
    keywords: Optional[str] = Field(None, description="Keywords associated with airport")
    
    @validator('iata_code')
    def validate_iata_code(cls, v):
        """Validate IATA code format"""
        if v and len(v) != 3:
            raise ValueError('IATA code must be 3 characters long')
        return v.upper() if v else v
    
    @validator('ident')
    def validate_ident(cls, v):
        """Validate airport identifier format"""
        if v and len(v) < 2:
            raise ValueError('Airport identifier must be at least 2 characters')
        return v.upper() if v else v
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": 3682,
                "ident": "KJFK",
                "type": "large_airport",
                "name": "John F Kennedy International Airport",
                "latitude_deg": 40.63980103,
                "longitude_deg": -73.77890015,
                "elevation_ft": 13,
                "continent": "NA",
                "iso_country": "US",
                "iso_region": "US-NY",
                "municipality": "New York",
                "scheduled_service": "yes",
                "gps_code": "KJFK",
                "iata_code": "JFK",
                "local_code": "JFK",
                "home_link": "https://www.jfkairport.com/",
                "wikipedia_link": "https://en.wikipedia.org/wiki/John_F._Kennedy_International_Airport",
                "keywords": "New York, JFK, international"
            }
        }

class LocationData(BaseModel):
    """IP geolocation data model"""
    latitude: Optional[float] = Field(None, description="Latitude in decimal degrees")
    longitude: Optional[float] = Field(None, description="Longitude in decimal degrees")
    city: Optional[str] = Field(None, description="City name")
    region: Optional[str] = Field(None, description="Region/state name")
    country: Optional[str] = Field(None, description="Country name")
    country_code: Optional[str] = Field(None, description="ISO country code")
    postal: Optional[str] = Field(None, description="Postal/ZIP code")
    timezone: Optional[str] = Field(None, description="Timezone identifier")
    ip: Optional[str] = Field(None, description="IP address")

class AirportWithDistance(BaseModel):
    """Airport model with distance information"""
    id: int = Field(description="Unique airport identifier")
    ident: str = Field(description="Airport identifier (usually ICAO code)")
    type: str = Field(description="Type of airport")
    name: str = Field(description="Full airport name")
    latitude_deg: Optional[float] = Field(None, description="Latitude in decimal degrees")
    longitude_deg: Optional[float] = Field(None, description="Longitude in decimal degrees")
    elevation_ft: Optional[float] = Field(None, description="Elevation in feet")
    municipality: Optional[str] = Field(None, description="City or municipality")
    iso_country: Optional[str] = Field(None, description="ISO country code")
    iso_region: Optional[str] = Field(None, description="ISO region code")
    iata_code: Optional[str] = Field(None, description="3-letter IATA code")
    distance_km: float = Field(description="Distance from search location in kilometers")

class AirportWithRelevance(BaseModel):
    """Airport model with relevance score for text search"""
    id: int = Field(description="Unique airport identifier")
    ident: str = Field(description="Airport identifier (usually ICAO code)")
    type: str = Field(description="Type of airport")
    name: str = Field(description="Full airport name")
    latitude_deg: Optional[float] = Field(None, description="Latitude in decimal degrees")
    longitude_deg: Optional[float] = Field(None, description="Longitude in decimal degrees")
    municipality: Optional[str] = Field(None, description="City or municipality")
    iso_country: Optional[str] = Field(None, description="ISO country code")
    iata_code: Optional[str] = Field(None, description="3-letter IATA code")
    relevance_score: int = Field(description="Relevance score for search ranking")

class AirportsByLocationResponse(BaseModel):
    """Response model for airports by location search"""
    search_location: dict = Field(description="Search coordinates and parameters")
    airports: List[AirportWithDistance] = Field(description="List of nearby airports")
    airports_found: int = Field(description="Number of airports found")

class AirportsByIPResponse(BaseModel):
    """Response model for airports by IP geolocation search"""
    ip_address: str = Field(description="IP address that was geolocated")
    location: Optional[LocationData] = Field(None, description="Geolocation data for the IP")
    airports: List[AirportWithDistance] = Field(description="List of nearby airports")
    search_radius_km: int = Field(description="Search radius in kilometers")
    airports_found: int = Field(description="Number of airports found")
    error: Optional[str] = Field(None, description="Error message if geolocation failed")

class AirportsTextSearchResponse(BaseModel):
    """Response model for free-text airport search"""
    query: str = Field(description="Search query that was used")
    airports: List[AirportWithRelevance] = Field(description="List of matching airports")
    airports_found: int = Field(description="Number of airports found")

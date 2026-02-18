from pydantic import BaseModel, Field, validator
from typing import Optional

class Navaid(BaseModel):
    """Navigation aid model for VOR, NDB, ILS, etc."""
    id: int = Field(description="Unique navaid identifier")
    filename: Optional[str] = Field(None, description="Source filename")
    ident: str = Field(description="Navaid identifier code")
    name: str = Field(description="Full name of the navigation aid")
    type: str = Field(description="Type of navaid (VOR, NDB, ILS, DME, etc.)")
    frequency_khz: Optional[float] = Field(None, description="Primary frequency in kHz")
    latitude_deg: Optional[float] = Field(None, description="Latitude in decimal degrees")
    longitude_deg: Optional[float] = Field(None, description="Longitude in decimal degrees")
    elevation_ft: Optional[float] = Field(None, description="Elevation in feet above sea level")
    iso_country: Optional[str] = Field(None, description="ISO country code")
    dme_frequency_khz: Optional[float] = Field(None, description="DME frequency in kHz")
    dme_channel: Optional[str] = Field(None, description="DME channel")
    dme_latitude_deg: Optional[float] = Field(None, description="DME latitude in decimal degrees")
    dme_longitude_deg: Optional[float] = Field(None, description="DME longitude in decimal degrees")
    dme_elevation_ft: Optional[float] = Field(None, description="DME elevation in feet")
    slaved_variation_deg: Optional[float] = Field(None, description="Slaved variation in degrees")
    magnetic_variation_deg: Optional[float] = Field(None, description="Magnetic variation in degrees")
    usageType: Optional[str] = Field(None, description="Usage type (HI, LO, BOTH, TERMINAL)")
    power: Optional[str] = Field(None, description="Power level (HIGH, MEDIUM, LOW)")
    associated_airport: Optional[str] = Field(None, description="Associated airport identifier")
    
    @validator('type')
    def validate_navaid_type(cls, v):
        """Validate navaid type"""
        valid_types = [
            'VOR', 'VORTAC', 'VOR-DME', 'NDB', 'NDB-DME', 'TACAN', 'ILS', 
            'ILS-DME', 'LOC', 'LOC-DME', 'GS', 'OM', 'MM', 'IM', 'DME'
        ]
        if v and v.upper() not in valid_types:
            raise ValueError(f'Navaid type must be one of: {", ".join(valid_types)}')
        return v.upper() if v else v
    
    @validator('usageType')
    def validate_usage_type(cls, v):
        """Validate usage type"""
        valid_usage = ['HI', 'LO', 'BOTH', 'TERMINAL']
        if v and v.upper() not in valid_usage:
            raise ValueError(f'Usage type must be one of: {", ".join(valid_usage)}')
        return v.upper() if v else v
    
    @validator('power')
    def validate_power(cls, v):
        """Validate power level"""
        valid_power = ['HIGH', 'MEDIUM', 'LOW']
        if v and v.upper() not in valid_power:
            raise ValueError(f'Power level must be one of: {", ".join(valid_power)}')
        return v.upper() if v else v
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": 1,
                "filename": "navaids.csv",
                "ident": "JFK",
                "name": "Kennedy",
                "type": "VOR-DME",
                "frequency_khz": 115800.0,
                "latitude_deg": 40.64119911,
                "longitude_deg": -73.77919769,
                "elevation_ft": 13,
                "iso_country": "US",
                "dme_frequency_khz": 115800.0,
                "dme_channel": "115X",
                "usageType": "BOTH",
                "power": "HIGH",
                "associated_airport": "KJFK"
            }
        }

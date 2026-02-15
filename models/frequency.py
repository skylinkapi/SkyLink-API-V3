from pydantic import BaseModel, Field, validator
from typing import Optional

class Frequency(BaseModel):
    """Airport radio frequency model"""
    id: int = Field(description="Unique frequency identifier")
    airport_ref: int = Field(description="Reference to airport ID")
    airport_ident: str = Field(description="Airport identifier (ICAO code)")
    type: str = Field(description="Type of frequency (TWR, GND, APP, etc.)")
    description: Optional[str] = Field(None, description="Detailed description of frequency usage")
    frequency_mhz: Optional[float] = Field(None, description="Frequency in MHz")
    
    @validator('frequency_mhz')
    def validate_frequency(cls, v):
        """Validate frequency is within valid aviation range"""
        if v is not None and (v < 108.0 or v > 137.0):
            raise ValueError('Aviation frequency must be between 108.0 and 137.0 MHz')
        return v
    
    @validator('type')
    def validate_frequency_type(cls, v):
        """Validate frequency type"""
        valid_types = ['TWR', 'GND', 'APP', 'DEP', 'ATIS', 'CTAF', 'UNICOM', 'AWOS', 'ASOS', 'FSS', 'RDO']
        if v and v.upper() not in valid_types:
            raise ValueError(f'Frequency type must be one of: {", ".join(valid_types)}')
        return v.upper() if v else v
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": 1,
                "airport_ref": 3682,
                "airport_ident": "KJFK",
                "type": "TWR",
                "description": "John F Kennedy Tower",
                "frequency_mhz": 119.1
            }
        }

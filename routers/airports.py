from fastapi import APIRouter, Query, HTTPException, status
from typing import Dict, Any, Optional
from services.airport_service import airport_service
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/airports", tags=["Airports"])

@router.get(
    "/search",
    responses={
        200: {
            "description": "Airport information with runways, frequencies, and navaids",
            "content": {
                "application/json": {
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
                        "runways": [
                            {
                                "length_ft": 14511,
                                "width_ft": 150,
                                "surface": "ASP",
                                "lighted": "1",
                                "closed": "0",
                                "le_ident": "04L",
                                "he_ident": "22R"
                            }
                        ],
                        "frequencies": [
                            {
                                "type": "TWR",
                                "description": "JFK TWR",
                                "frequency_mhz": "119.1"
                            }
                        ],
                        "navaids": [
                            {
                                "ident": "JFK",
                                "name": "Kennedy",
                                "type": "VOR-DME",
                                "frequency_khz": "115900"
                            }
                        ]
                    }
                }
            }
        }
    }
)
async def search_airport(
    icao: Optional[str] = Query(None, description="4-letter ICAO airport code (e.g., KJFK, EGLL)", min_length=4, max_length=4),
    iata: Optional[str] = Query(None, description="3-letter IATA airport code (e.g., JFK, LHR)", min_length=3, max_length=3)
) -> Dict[str, Any]:
    """
    Get comprehensive airport information by ICAO or IATA code.
    
    Returns detailed airport data including:
    - Basic airport information (name, location, coordinates)
    - Runway details and specifications
    - Communication frequencies 
    - Navigation aids (navaids)
    - Country and region information
    
    - **icao**: 4-letter ICAO airport code (e.g., KJFK, EGLL)
    - **iata**: 3-letter IATA airport code (e.g., JFK, LHR)
    
    Provide either ICAO or IATA code, not both.
    """
    try:
        # Validate that exactly one parameter is provided
        if not icao and not iata:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either ICAO or IATA code must be provided"
            )
        
        if icao and iata:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Provide either ICAO or IATA code, not both"
            )
        
        # Determine which code to use
        airport_code = icao if icao else iata
        airport_code = airport_code.upper().strip()
        
        # Validate code format
        if icao and len(airport_code) != 4:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="ICAO code must be exactly 4 characters"
            )
        
        if iata and len(airport_code) != 3:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="IATA code must be exactly 3 characters"
            )
        
        # Fetch airport data
        enriched_data = await airport_service.get_enriched_airport_data(airport_code)
        if not enriched_data:
            code_type = "ICAO" if icao else "IATA"
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Airport not found for {code_type} code: {airport_code}"
            )
        
        # Add the original search parameter to response for clarity
        enriched_data['search_code'] = airport_code
        enriched_data['search_type'] = "ICAO" if icao else "IATA"
        
        return enriched_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error searching airport - ICAO: {icao}, IATA: {iata}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to fetch airport data at this time"
        )

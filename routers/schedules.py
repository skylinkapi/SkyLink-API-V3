

from fastapi import APIRouter, HTTPException, status, Path, Query
from typing import Dict, Any, Optional
from data_ingestion.schedules import fetch_schedule
from services.airport_service import airport_service
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/schedules", tags=["Schedules"])

async def _get_iata_from_params(icao: Optional[str] = None, iata: Optional[str] = None) -> tuple[Optional[str], str]:
    """Get IATA code from either ICAO or IATA parameter and return the airport identifier used"""
    try:
        # Check that exactly one parameter is provided
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
        
        # If IATA provided, validate and use it
        if iata:
            iata = iata.upper().strip()
            if len(iata) != 3:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="IATA code must be exactly 3 characters"
                )
            
            # Validate that airport exists
            airport = await airport_service.find_airport_by_code(iata)
            if not airport:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Airport not found for IATA code: {iata}"
                )
            
            return iata, iata
        
        # If ICAO provided, convert to IATA
        if icao:
            icao = icao.upper().strip()
            if len(icao) != 4:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="ICAO code must be exactly 4 characters"
                )
            
            airport = await airport_service.find_airport_by_code(icao)
            if not airport:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Airport not found for ICAO code: {icao}"
                )
            
            airport_iata = airport.get('iata_code')
            if not airport_iata:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"No IATA code available for airport: {icao}"
                )
            
            return airport_iata, icao
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing airport codes - ICAO: {icao}, IATA: {iata}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to process airport code"
        )

@router.get(
    "/departures",
    responses={
        200: {
            "description": "Airport departure schedule",
            "content": {
                "application/json": {
                    "example": {
                        "airport": "KJFK",
                        "airport_name": "John F Kennedy International Airport", 
                        "flights": [
                            {
                                "flight_number": "BAW115",
                                "airline": "British Airways",
                                "destination": "EGLL",
                                "destination_name": "London Heathrow",
                                "scheduled_departure": "2025-09-27T14:30:00Z",
                                "actual_departure": "2025-09-27T14:35:00Z",
                                "status": "Departed",
                                "gate": "A12",
                                "terminal": "7",
                                "aircraft_type": "Boeing 777-300ER"
                            }
                        ],
                        "total_flights": 1,
                        "timestamp": "2025-09-27T12:00:00Z"
                    }
                }
            }
        }
    }
)
async def get_departures(
    icao: Optional[str] = Query(None, description="4-letter ICAO airport code (e.g., KJFK, EGLL)", min_length=4, max_length=4),
    iata: Optional[str] = Query(None, description="3-letter IATA airport code (e.g., JFK, LHR)", min_length=3, max_length=3)
) -> Dict[str, Any]:
    """
    Get real-time departure schedule for an airport.
    
    - **icao**: 4-letter ICAO airport code (e.g., KJFK, EGLL)
    - **iata**: 3-letter IATA airport code (e.g., JFK, LHR)
    
    Provide either ICAO or IATA code, not both.
    """
    try:
        # Get IATA code for the schedule API and the airport identifier used
        iata_code, airport_identifier = await _get_iata_from_params(icao=icao, iata=iata)
        
        # Fetch schedule data
        result = await fetch_schedule(iata_code, direction="departures")
        if not result or "error" in result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Departure schedule not available for {airport_identifier}"
            )
        
        # Add the original airport identifier to response for clarity
        result['airport_code'] = airport_identifier
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching departures - ICAO: {icao}, IATA: {iata}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to fetch departure schedule at this time"
        )

@router.get(
    "/arrivals",
    responses={
        200: {
            "description": "Airport arrival schedule",
            "content": {
                "application/json": {
                    "example": {
                        "airport": "KJFK",
                        "airport_name": "John F Kennedy International Airport",
                        "flights": [
                            {
                                "flight_number": "BAW179",
                                "airline": "British Airways", 
                                "origin": "EGLL",
                                "origin_name": "London Heathrow",
                                "scheduled_arrival": "2025-09-27T16:15:00Z",
                                "estimated_arrival": "2025-09-27T16:20:00Z",
                                "status": "En Route",
                                "gate": "B15",
                                "terminal": "7",
                                "aircraft_type": "Boeing 777-300ER"
                            }
                        ],
                        "total_flights": 1,
                        "timestamp": "2025-09-27T12:00:00Z"
                    }
                }
            }
        }
    }
)
async def get_arrivals(
    icao: Optional[str] = Query(None, description="4-letter ICAO airport code (e.g., KJFK, EGLL)", min_length=4, max_length=4),
    iata: Optional[str] = Query(None, description="3-letter IATA airport code (e.g., JFK, LHR)", min_length=3, max_length=3)
) -> Dict[str, Any]:
    """
    Get real-time arrival schedule for an airport.
    
    - **icao**: 4-letter ICAO airport code (e.g., KJFK, EGLL)
    - **iata**: 3-letter IATA airport code (e.g., JFK, LHR)
    
    Provide either ICAO or IATA code, not both.
    """
    try:
        # Get IATA code for the schedule API and the airport identifier used
        iata_code, airport_identifier = await _get_iata_from_params(icao=icao, iata=iata)
        
        # Fetch schedule data
        result = await fetch_schedule(iata_code, direction="arrivals")
        if not result or "error" in result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Arrival schedule not available for {airport_identifier}"
            )
        
        # Add the original airport identifier to response for clarity
        result['airport_code'] = airport_identifier
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching arrivals - ICAO: {icao}, IATA: {iata}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to fetch arrival schedule at this time"
        )

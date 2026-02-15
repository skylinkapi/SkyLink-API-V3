

from fastapi import APIRouter, HTTPException, status, Path
from typing import Dict, Any
from data_ingestion.flight_status import get_flight_status_avionio

router = APIRouter(prefix="/flight_status", tags=["Flight Status"])

@router.get(
    "/{flight_number}",
    responses={
        200: {
            "description": "Real-time flight status and details",
            "content": {
                "application/json": {
                    "example": {
                        "flight_number": "BAW123",
                        "airline": "British Airways",
                        "status": "En Route",
                        "departure": {
                            "airport": "EGLL",
                            "scheduled": "2025-09-27T10:30:00Z",
                            "actual": "2025-09-27T10:35:00Z",
                            "terminal": "5",
                            "gate": "A12"
                        },
                        "arrival": {
                            "airport": "KJFK",
                            "scheduled": "2025-09-27T14:45:00Z",
                            "estimated": "2025-09-27T14:50:00Z",
                            "terminal": "7",
                            "gate": "B15"
                        },
                        "aircraft": {
                            "type": "Boeing 777-300ER",
                            "registration": "G-STBC"
                        }
                    }
                }
            }
        }
    }
)
async def get_flight_status(
    flight_number: str = Path(..., description="Flight number (e.g., BAW123, UA456)", min_length=2, max_length=10)
) -> Dict[str, Any]:
    """
    Get real-time flight status and details by flight number.
    
    - **flight_number**: Flight number (e.g., AA123, BA456, AF789)
    
    Returns flight status, departure/arrival times, gates, terminals, and airline information.
    """
    try:
        flight_number = flight_number.upper().strip()
        if not flight_number:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Flight number is required"
            )
        
        result = get_flight_status_avionio(flight_number)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Flight {flight_number} not found"
            )
        
        if isinstance(result, dict) and "error" in result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=result["error"]
            )
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch flight status: {str(e)}"
        )

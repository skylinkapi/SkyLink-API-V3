"""
v3 Flight Status router.

Supports both IATA (BA123) and ICAO (BAW123) flight number formats.
ICAO codes are automatically converted to IATA for lookup.
"""

from fastapi import APIRouter, HTTPException, status, Path
from typing import Dict, Any
from data_ingestion.v3.flight_status import get_flight_status_v3

router = APIRouter(prefix="/flight_status", tags=["Flight Status"])


@router.get(
    "/{flight_number}",
    responses={
        200: {
            "description": "Real-time flight status and details",
            "content": {
                "application/json": {
                    "example": {
                        "flight_number": "BA 123",
                        "airline": "British Airways",
                        "status": "En Route",
                        "departure": {
                            "airport": "EGLL",
                            "airport_full": "London Heathrow Airport",
                            "scheduled_time": "10:30",
                            "scheduled_date": "11 Feb",
                            "actual_time": "10:35",
                            "actual_date": "11 Feb",
                            "terminal": "5",
                            "gate": "A12",
                            "checkin": ""
                        },
                        "arrival": {
                            "airport": "KJFK",
                            "airport_full": "John F Kennedy International Airport",
                            "scheduled_time": "14:45",
                            "scheduled_date": "11 Feb",
                            "estimated_time": "14:50",
                            "estimated_date": "11 Feb",
                            "terminal": "7",
                            "gate": "B15",
                            "baggage": ""
                        }
                    }
                }
            }
        }
    }
)
async def get_flight_status(
    flight_number: str = Path(
        ...,
        description="Flight number in IATA (BA123) or ICAO (BAW123, CCA933) format",
        min_length=2,
        max_length=10,
    )
) -> Dict[str, Any]:
    """
    Get real-time flight status and details by flight number.

    Supports both **IATA** (BA123, CA933) and **ICAO** (BAW123, CCA933) formats.
    ICAO codes are automatically converted to IATA for lookup.

    Returns flight status, departure/arrival times, gates, terminals, and
    airline information.
    """
    try:
        flight_number = flight_number.upper().strip()
        if not flight_number:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Flight number is required"
            )

        result = await get_flight_status_v3(flight_number)
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

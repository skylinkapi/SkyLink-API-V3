"""
v3 PIREPs (Pilot Reports) router.

Pilot weather reports including turbulence, icing, and sky conditions.
Primary source: avwx-engine; fallback: aviationweather.gov.
"""

import logging

from fastapi import APIRouter, HTTPException, Path, Query, status

from models.v3.pireps import PIREPResponse
from services.airport_service import airport_service
from services.v3.pirep_service import get_pireps

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/weather",
    tags=["PIREPs"],
)


@router.get(
    "/pireps/{icao}",
    response_model=PIREPResponse,
    summary="Get PIREPs near an airport",
    description=(
        "Returns pilot reports (PIREPs) within a given radius and time window of an airport.\n\n"
        "Reports include turbulence, icing, sky conditions, temperature, and wind observations "
        "filed by pilots in flight.\n\n"
        "- **UA** = routine PIREP\n"
        "- **UUA** = urgent PIREP (significant weather hazard)\n\n"
        "**Source:** avwx-engine (primary), aviationweather.gov (fallback)"
    ),
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {
                        "icao": "KJFK",
                        "radius_nm": 100,
                        "hours": 2,
                        "reports": [
                            {
                                "raw": "UA /OV JFK/TM 1845/FL085/TP B738/TB MOD/RM CONT MOD CHOP",
                                "report_type": "UA",
                                "location": "JFK",
                                "time": "2025-01-15T18:45:00Z",
                                "altitude": "FL085",
                                "aircraft_type": "B738",
                                "turbulence": "Moderate",
                                "icing": None,
                                "remarks": "CONT MOD CHOP",
                            }
                        ],
                        "total": 1,
                    }
                }
            }
        },
        404: {"description": "Airport not found"},
    },
)
async def get_pireps_for_airport(
    icao: str = Path(
        ..., description="4-letter ICAO airport code (e.g. KJFK, EGLL)", min_length=4, max_length=4
    ),
    radius_nm: int = Query(
        100, description="Search radius in nautical miles", ge=10, le=500
    ),
    hours: int = Query(
        2, description="Time window in hours (how far back to look)", ge=1, le=24
    ),
):
    """Get PIREPs near an airport."""
    icao = icao.upper().strip()

    # Resolve airport coordinates
    airport = await airport_service.find_airport_by_code(icao)
    if not airport:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Airport not found for ICAO code: {icao}",
        )

    lat = airport.get("latitude_deg")
    lon = airport.get("longitude_deg")
    if lat is None or lon is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No coordinates available for airport {icao}",
        )

    try:
        data = await get_pireps(icao, float(lat), float(lon), radius_nm=radius_nm, hours=hours)
    except Exception as e:
        logger.error(f"Error fetching PIREPs for {icao}: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="PIREP service temporarily unavailable",
        )

    return PIREPResponse(**data)

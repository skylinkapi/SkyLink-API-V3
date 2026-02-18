"""
v3 AIRMET/SIGMET router.

Aviation weather advisories — AIRMETs, SIGMETs, and Convective SIGMETs.
"""

import logging

from fastapi import APIRouter, HTTPException, Path, Query, status
from typing import Optional

from models.v3.airsigmet import AirSigmetResponse
from services.airport_service import airport_service
from services.v3.airsigmet_service import get_airsigmets

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/weather",
    tags=["AIRMET/SIGMET"],
)


@router.get(
    "/airsigmet/{icao}",
    response_model=AirSigmetResponse,
    summary="Get AIRMETs and SIGMETs affecting an airport",
    description=(
        "Returns AIRMET/SIGMET advisories whose affected area contains the given airport.\n\n"
        "Uses the airport's coordinates to check containment against each advisory's polygon boundary."
    ),
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {
                        "reports": [
                            {
                                "raw": "WAUS46 KKCI 151445 WA6S AIRMET SIERRA ...",
                                "bulletin_type": "AIRMET",
                                "report_type": "AIRMET",
                                "area": "S",
                                "body": "AIRMET IFR...",
                                "observation": {
                                    "type": "IFR",
                                    "intensity": None,
                                    "floor": "SFC",
                                    "ceiling": "FL180",
                                },
                            }
                        ],
                        "total": 1,
                        "filter_type": None,
                    }
                }
            }
        },
        404: {"description": "Airport not found"},
    },
)
async def get_airsigmets_for_airport(
    icao: str = Path(
        ..., description="4-letter ICAO airport code (e.g. KJFK, EGLL)", min_length=4, max_length=4
    ),
    type: Optional[str] = Query(
        None, description="Filter by type: 'airmet' or 'sigmet'", pattern="^(airmet|sigmet)$"
    ),
):
    """Get AIRMETs/SIGMETs affecting an airport."""
    icao = icao.upper().strip()

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
        data = await get_airsigmets(lat=float(lat), lon=float(lon), filter_type=type)
    except Exception as e:
        logger.error(f"Error fetching AIRMETs/SIGMETs for {icao}: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AIRMET/SIGMET service temporarily unavailable",
        )

    return AirSigmetResponse(**data)

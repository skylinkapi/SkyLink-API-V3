"""
v3 NOTAMs router.

Notices to Air Missions via FAA SWIM FNS (Solace messaging).
Real-time NOTAM feed — NOTAMs accumulate in memory from the background consumer.
"""

import logging

from fastapi import APIRouter, HTTPException, Path, status

from models.v3.notams import NOTAMResponse
from services.v3.notam_service import get_notams

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/notams",
    tags=["NOTAMs"],
)


@router.get(
    "/{icao}",
    response_model=NOTAMResponse,
    summary="Get NOTAMs for an airport",
    description=(
        "Returns active Notices to Air Missions (NOTAMs) for the given ICAO code.\n\n"
        "NOTAMs are received in real-time from the FAA SWIM Flight Notification Service. "
        "Each NOTAM includes the raw text and parsed fields such as effective/expiration "
        "times and the NOTAM body.\n\n"
        "**Source:** FAA SWIM FNS via Solace messaging (AIXM 5.1)"
    ),
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {
                        "icao": "KJFK",
                        "notams": [
                            {
                                "raw": "!JFK 01/001 JFK RWY 04L/22R CLSD 2501150800-2501152000",
                                "notam_id": "01/001",
                                "type": "N",
                                "location": "KJFK",
                                "effective": "2025-01-15T08:00:00Z",
                                "expiration": "2025-01-15T20:00:00Z",
                                "body": "RWY 04L/22R CLSD",
                            }
                        ],
                        "total": 1,
                    }
                }
            }
        },
    },
)
async def get_notams_for_airport(
    icao: str = Path(
        ..., description="4-letter ICAO airport code (e.g. KJFK, EGLL)", min_length=4, max_length=4
    ),
):
    """Get active NOTAMs for an airport or FIR."""
    icao = icao.upper().strip()

    try:
        data = await get_notams(icao)
    except Exception as e:
        logger.error(f"Error fetching NOTAMs for {icao}: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="NOTAM service temporarily unavailable",
        )

    return NOTAMResponse(**data)

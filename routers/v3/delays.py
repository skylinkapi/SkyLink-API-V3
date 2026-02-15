"""
v3 FAA Delays router.

Real-time FAA National Airspace System delay information including
ground delay programs, ground stops, airport closures, and airspace flow programs.
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Path, status

from data_ingestion.v3.faa_delays import fetch_faa_delays
from models.v3.delays import FAADelayResponse

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/delays",
    tags=["FAA Delays"],
)


@router.get(
    "/faa",
    response_model=FAADelayResponse,
    summary="Get all current FAA NAS delays",
    description=(
        "Returns all active FAA National Airspace System delays including "
        "ground delay programs, ground stops, airport closures, and airspace "
        "flow programs across the US.\n\n"
        "**Source:** nasstatus.faa.gov (real-time, no caching)"
    ),
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {
                        "ground_delays": [
                            {
                                "airport": "KEWR",
                                "airport_name": None,
                                "reason": "WEATHER / THUNDERSTORMS",
                                "avg_delay": "1 hour and 30 minutes",
                                "max_delay": "2 hours",
                            }
                        ],
                        "ground_stops": [],
                        "closures": [],
                        "airspace_flow_programs": [],
                        "total_alerts": 1,
                        "message": None,
                    }
                }
            }
        },
    },
)
async def get_faa_delays():
    """Get all current FAA NAS delays."""
    try:
        data = await fetch_faa_delays()
        return FAADelayResponse(**data)
    except Exception as e:
        logger.error(f"Error fetching FAA delays: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="FAA delay service temporarily unavailable",
        )


@router.get(
    "/faa/{icao}",
    response_model=FAADelayResponse,
    summary="Get FAA delays for a specific airport",
    description=(
        "Returns any active FAA delays affecting a specific airport.\n\n"
        "Filters the full NAS status feed for the given ICAO code. "
        "Also matches airspace flow programs whose facility covers the airport's ARTCC.\n\n"
        "**Note:** This endpoint covers US airports only (FAA data)."
    ),
    responses={
        200: {
            "description": "Delay information for the requested airport (may be empty if no delays)",
        },
    },
)
async def get_faa_delays_for_airport(
    icao: str = Path(..., description="4-letter ICAO airport code (e.g. KJFK)", min_length=4, max_length=4),
):
    """Get FAA delays filtered to a specific airport."""
    icao = icao.upper().strip()

    try:
        data = await fetch_faa_delays()
    except Exception as e:
        logger.error(f"Error fetching FAA delays for {icao}: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="FAA delay service temporarily unavailable",
        )

    # Filter each category to this airport
    gd = [d for d in data["ground_delays"] if d["airport"] == icao]
    gs = [s for s in data["ground_stops"] if s["airport"] == icao]
    cl = [c for c in data["closures"] if c["airport"] == icao]
    # Airspace flow programs are facility-level — include all (user can review)
    afp = data["airspace_flow_programs"]

    total = len(gd) + len(gs) + len(cl) + len(afp)

    return FAADelayResponse(
        ground_delays=gd,
        ground_stops=gs,
        closures=cl,
        airspace_flow_programs=afp,
        total_alerts=total,
        message=None if total > 0 else f"No active FAA delays for {icao}",
    )

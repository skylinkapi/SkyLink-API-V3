"""
v3 Distance & Bearing API router.

Calculate great-circle distance and initial bearing between two aviation
waypoints (airports or arbitrary lat/lon coordinates).
"""

from typing import Optional

from fastapi import APIRouter, Query, HTTPException, status

from models.v3.distance import Coordinates, DistanceUnit, DistanceResponse
from services.v3.distance_service import distance_service

router = APIRouter(
    prefix="/distance",
    tags=["Distance & Bearing"],
)


@router.get(
    "",
    response_model=DistanceResponse,
    summary="Calculate distance and bearing between two points",
    description=(
        "Calculate the great-circle distance and initial bearing between two "
        "aviation waypoints. You can specify each point as an ICAO/IATA airport "
        "code **or** as latitude/longitude coordinates.\n\n"
        "**Examples:**\n"
        "- `/distance?from_icao=KJFK&to_icao=EGLL`\n"
        "- `/distance?from_lat=40.6413&from_lon=-73.7781&to_icao=EGLL`\n"
        "- `/distance?from_lat=40.64&from_lon=-73.78&to_lat=51.47&to_lon=-0.46&unit=km`"
    ),
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {
                        "from_point": {
                            "latitude": 40.639751,
                            "longitude": -73.778925,
                            "icao_code": "KJFK",
                            "iata_code": "JFK",
                            "name": "John F Kennedy International Airport"
                        },
                        "to_point": {
                            "latitude": 51.4706,
                            "longitude": -0.461941,
                            "icao_code": "EGLL",
                            "iata_code": "LHR",
                            "name": "London Heathrow Airport"
                        },
                        "distance": 2991.01,
                        "unit": "nm",
                        "bearing": 51.35,
                        "bearing_cardinal": "NE",
                        "midpoint": {
                            "latitude": 52.216674,
                            "longitude": -41.302671,
                            "icao_code": None,
                            "iata_code": None,
                            "name": None
                        }
                    }
                }
            }
        },
        400: {"description": "Invalid or missing point specification"},
        404: {"description": "Airport code not found"},
    },
)
async def calculate_distance(
    from_icao: Optional[str] = Query(
        None, description="Origin airport ICAO or IATA code (e.g. KJFK, JFK)"
    ),
    to_icao: Optional[str] = Query(
        None, description="Destination airport ICAO or IATA code (e.g. EGLL, LHR)"
    ),
    from_lat: Optional[float] = Query(
        None, ge=-90, le=90, description="Origin latitude (-90 to 90)"
    ),
    from_lon: Optional[float] = Query(
        None, ge=-180, le=180, description="Origin longitude (-180 to 180)"
    ),
    to_lat: Optional[float] = Query(
        None, ge=-90, le=90, description="Destination latitude (-90 to 90)"
    ),
    to_lon: Optional[float] = Query(
        None, ge=-180, le=180, description="Destination longitude (-180 to 180)"
    ),
    unit: DistanceUnit = Query(
        DistanceUnit.NAUTICAL_MILES,
        description="Distance unit: nm (nautical miles), km, or mi",
    ),
):
    """Calculate distance and bearing between two points."""

    # ── resolve origin ───────────────────────────────────────────────
    if from_icao:
        from_point = from_icao
    elif from_lat is not None and from_lon is not None:
        from_point = Coordinates(latitude=from_lat, longitude=from_lon)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide either from_icao or both from_lat and from_lon.",
        )

    # ── resolve destination ──────────────────────────────────────────
    if to_icao:
        to_point = to_icao
    elif to_lat is not None and to_lon is not None:
        to_point = Coordinates(latitude=to_lat, longitude=to_lon)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide either to_icao or both to_lat and to_lon.",
        )

    # ── calculate ────────────────────────────────────────────────────
    try:
        result = await distance_service.calculate(from_point, to_point, unit)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    return DistanceResponse(**result)

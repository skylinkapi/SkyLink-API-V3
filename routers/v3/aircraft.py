"""
v3 Aircraft Registration Lookup router.

Look up aircraft details by registration (tail number) or ICAO24 hex
address using the 615 K+ aircraft JSON database.  Includes full-size
photos from airport-data.com.
"""

from fastapi import APIRouter, Path, Query

from models.v3.aircraft import AircraftLookupResponse, AircraftDatabaseStats
from services.v3.aircraft_lookup import aircraft_lookup_service
from services.aircraft_db_service import get_aircraft_db_service

router = APIRouter(
    prefix="/aircraft",
    tags=["Aircraft Lookup"],
)


@router.get(
    "/registration/{registration}",
    response_model=AircraftLookupResponse,
    summary="Look up aircraft by registration",
    description=(
        "Look up aircraft details and photos by registration / tail number.\n\n"
        "**Examples:** N12345, G-STBC, D-AIZY, VH-OQA"
    ),
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {
                        "query": "G-STBC",
                        "found": True,
                        "aircraft": {
                            "registration": "G-STBC",
                            "icao24": "40621d",
                            "icao_type": "B77W",
                            "type_name": "Boeing 777-36N",
                            "manufacturer": None,
                            "owner_operator": "British Airways",
                            "is_military": False,
                            "year_built": "2013",
                            "photos": [
                                {
                                    "image": "https://image.airport-data.com/aircraft/001912010.jpg",
                                    "link": "https://airport-data.com/aircraft/photo/001912010.html",
                                    "photographer": "Roberto Cassar"
                                }
                            ]
                        }
                    }
                }
            }
        }
    },
)
async def lookup_by_registration(
    registration: str = Path(
        ...,
        description="Aircraft registration (e.g. N12345, G-STBC)",
        min_length=2,
        max_length=10,
    ),
    photos: bool = Query(
        True,
        description="Include aircraft photos from airport-data.com",
    ),
):
    """Look up aircraft by registration number."""
    details = await aircraft_lookup_service.lookup_by_registration(registration, include_photos=photos)
    return AircraftLookupResponse(
        query=registration.upper(),
        found=details is not None,
        aircraft=details,
    )


@router.get(
    "/icao24/{icao24}",
    response_model=AircraftLookupResponse,
    summary="Look up aircraft by ICAO24 hex address",
    description=(
        "Look up aircraft details and photos by ICAO 24-bit transponder hex address.\n\n"
        "**Example:** 40621D"
    ),
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {
                        "query": "40621D",
                        "found": True,
                        "aircraft": {
                            "registration": "G-STBC",
                            "icao24": "40621d",
                            "icao_type": "B77W",
                            "type_name": "Boeing 777-36N",
                            "manufacturer": None,
                            "owner_operator": "British Airways",
                            "is_military": False,
                            "year_built": "2013",
                            "photos": [
                                {
                                    "image": "https://image.airport-data.com/aircraft/001912010.jpg",
                                    "link": "https://airport-data.com/aircraft/photo/001912010.html",
                                    "photographer": "Roberto Cassar"
                                }
                            ]
                        }
                    }
                }
            }
        }
    },
)
async def lookup_by_icao24(
    icao24: str = Path(
        ...,
        description="ICAO24 hex address (e.g. 40621D)",
        min_length=4,
        max_length=6,
    ),
    photos: bool = Query(
        True,
        description="Include aircraft photos from airport-data.com",
    ),
):
    """Look up aircraft by ICAO24 hex code."""
    details = await aircraft_lookup_service.lookup_by_icao24(icao24, include_photos=photos)
    return AircraftLookupResponse(
        query=icao24.upper(),
        found=details is not None,
        aircraft=details,
    )


@router.get(
    "/database/stats",
    response_model=AircraftDatabaseStats,
    summary="Get aircraft database statistics",
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {
                        "loaded": True,
                        "total_icao_entries": 615656,
                        "total_registration_entries": 613252,
                        "database_file": "basic-ac-db.json"
                    }
                }
            }
        }
    },
)
async def database_stats():
    """Return statistics about the loaded aircraft database."""
    db = get_aircraft_db_service()
    stats = db.get_database_stats()
    return AircraftDatabaseStats(**stats)

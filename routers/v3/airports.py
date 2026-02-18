"""
v3 Airport Search router.

Three search modes:
  GET /airports/search/location  — by coordinates + radius
  GET /airports/search/ip        — by requester (or explicit) IP
  GET /airports/search/text      — free-text query
"""

from fastapi import APIRouter, Query, Request, HTTPException
from typing import Optional

from models.v3.airports import AirportType
from models.airports import (
    AirportsByLocationResponse,
    AirportsByIPResponse,
    AirportsTextSearchResponse,
)
from services.v3.airport_search_service import airport_search_service

router = APIRouter(
    prefix="/airports/search",
    tags=["Airport Search"],
)


def _get_client_ip(request: Request) -> str:
    """Extract the real client IP, respecting reverse-proxy headers."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "127.0.0.1"


# ── Location search ──────────────────────────────────────────────────

@router.get(
    "/location",
    response_model=AirportsByLocationResponse,
    summary="Find airports near coordinates",
    description=(
        "Search for airports within a radius of the given latitude/longitude.\n\n"
        "Results are sorted by distance (nearest first)."
    ),
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {
                        "search_location": {
                            "latitude": 40.64,
                            "longitude": -73.78,
                            "radius_km": 50,
                            "type_filter": None,
                        },
                        "airports": [
                            {
                                "id": 3682,
                                "ident": "KJFK",
                                "type": "large_airport",
                                "name": "John F Kennedy International Airport",
                                "latitude_deg": 40.6398,
                                "longitude_deg": -73.7789,
                                "elevation_ft": 13,
                                "municipality": "New York",
                                "iso_country": "US",
                                "iso_region": "US-NY",
                                "iata_code": "JFK",
                                "distance_km": 0.15,
                            }
                        ],
                        "airports_found": 1,
                    }
                }
            }
        }
    },
)
async def search_by_location(
    lat: float = Query(..., ge=-90, le=90, description="Latitude in decimal degrees"),
    lon: float = Query(..., ge=-180, le=180, description="Longitude in decimal degrees"),
    radius: float = Query(50, gt=0, le=500, description="Search radius in kilometers"),
    type: Optional[AirportType] = Query(None, description="Filter by airport type"),
    limit: int = Query(50, ge=1, le=200, description="Maximum results to return"),
):
    """Find airports within a radius of the given coordinates."""
    result = await airport_search_service.search_by_location(
        lat, lon, radius,
        airport_type=type.value if type else None,
        limit=limit,
    )
    return result


# ── IP-based search ──────────────────────────────────────────────────

@router.get(
    "/ip",
    response_model=AirportsByIPResponse,
    summary="Find airports near an IP address",
    description=(
        "Geolocate the requester's IP (or an explicit IP) and find nearby airports.\n\n"
        "When no `ip` parameter is provided, the requester's own IP is used."
    ),
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {
                        "ip_address": "8.8.8.8",
                        "location": {
                            "latitude": 37.751,
                            "longitude": -97.822,
                            "city": "Wichita",
                            "region": "Kansas",
                            "country": "United States",
                            "country_code": "US",
                            "postal": "67202",
                            "timezone": "America/Chicago",
                            "ip": "8.8.8.8",
                        },
                        "airports": [],
                        "search_radius_km": 100,
                        "airports_found": 0,
                        "error": None,
                    }
                }
            }
        }
    },
)
async def search_by_ip(
    request: Request,
    ip: Optional[str] = Query(None, description="IP address to geolocate (defaults to requester's IP)"),
    radius: float = Query(100, gt=0, le=500, description="Search radius in kilometers"),
    type: Optional[AirportType] = Query(None, description="Filter by airport type"),
    limit: int = Query(50, ge=1, le=200, description="Maximum results to return"),
):
    """Geolocate an IP and return nearby airports."""
    resolved_ip = ip or _get_client_ip(request)
    result = await airport_search_service.search_by_ip(
        resolved_ip, radius,
        airport_type=type.value if type else None,
        limit=limit,
    )
    return result


# ── Text search ──────────────────────────────────────────────────────

@router.get(
    "/text",
    response_model=AirportsTextSearchResponse,
    summary="Free-text airport search",
    description=(
        "Search airports by name, city, ICAO/IATA code, country, or keywords.\n\n"
        "Results are ranked by relevance (exact code matches rank highest)."
    ),
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {
                        "query": "London",
                        "airports": [
                            {
                                "id": None,
                                "ident": "EGLL",
                                "type": "large_airport",
                                "name": "London Heathrow Airport",
                                "latitude_deg": 51.4706,
                                "longitude_deg": -0.4619,
                                "municipality": "London",
                                "iso_country": "GB",
                                "iata_code": "LHR",
                                "relevance_score": 80,
                            }
                        ],
                        "airports_found": 1,
                    }
                }
            }
        }
    },
)
async def search_by_text(
    q: str = Query(..., min_length=2, max_length=100, description="Search query"),
    limit: int = Query(20, ge=1, le=100, description="Maximum results to return"),
    type: Optional[AirportType] = Query(None, description="Filter by airport type"),
):
    """Search airports by name, code, city, or keywords."""
    result = await airport_search_service.search_by_text(
        q, limit=limit,
        airport_type=type.value if type else None,
    )
    return result

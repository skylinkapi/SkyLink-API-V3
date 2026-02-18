"""
v3 ADS-B Aircraft Tracking router.

Same functionality as v2 plus explicit photos toggle parameter.
"""

from fastapi import APIRouter, Query, HTTPException
from typing import Optional, List, Dict, Any
from datetime import datetime
import re
import asyncio

from models.adsb_models import (
    AircraftResponse, AircraftListResponse, ErrorResponse, HealthResponse,
)
from data_ingestion.adsb_client import get_adsb_client, Aircraft
from utils.adsb_utils import (
    filter_aircraft_by_radius, filter_aircraft_by_bounding_box,
    filter_aircraft_by_callsign, filter_aircraft_by_altitude,
    filter_aircraft_by_speed,
    convert_aircraft_to_response, get_aircraft_statistics as calculate_aircraft_statistics,
    fetch_aircraft_photo,
)

router = APIRouter(
    prefix="/adsb",
    tags=["ADS-B Aircraft Tracking"],
    responses={
        404: {"model": ErrorResponse, "description": "Aircraft not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)


def _validate_icao24(icao24: str) -> str:
    icao24_upper = icao24.upper()
    if not re.match(r'^[0-9A-F]{6}$', icao24_upper):
        raise HTTPException(
            status_code=400,
            detail="Invalid ICAO24 format. Must be 6 hexadecimal characters."
        )
    return icao24_upper


@router.get("/")
async def adsb_root():
    """ADS-B service root endpoint"""
    return {
        "service": "ADS-B Aircraft Tracking (v3)",
        "endpoints": {
            "aircraft": "/v3/adsb/aircraft",
            "statistics": "/v3/adsb/aircraft/statistics",
            "health": "/v3/adsb/health",
        }
    }


@router.get(
    "/aircraft",
    response_model=AircraftListResponse,
    summary="Get all tracked aircraft",
    description=(
        "Returns a list of all currently tracked aircraft with their latest position and flight data.\n\n"
        "Set **photos=true** to include aircraft photos from airport-data.com (slower, capped at 50 aircraft)."
    ),
    responses={
        200: {
            "description": "List of tracked aircraft",
            "content": {
                "application/json": {
                    "example": {
                        "aircraft": [
                            {
                                "icao24": "40621D",
                                "callsign": "BAW123",
                                "latitude": 51.4706,
                                "longitude": -0.4619,
                                "altitude": 35000.0,
                                "ground_speed": 450.5,
                                "track": 89.2,
                                "vertical_rate": 0.0,
                                "is_on_ground": False,
                                "last_seen": "2026-02-11T12:00:00Z",
                                "first_seen": "2026-02-11T11:45:00Z",
                                "registration": "G-STBC",
                                "aircraft_type": "Boeing 777-36N",
                                "airline": "British Airways",
                                "photo_url": "https://image.airport-data.com/aircraft/001912010.jpg"
                            }
                        ],
                        "total_count": 4691,
                        "timestamp": "2026-02-11T12:00:30Z"
                    }
                }
            }
        }
    }
)
async def get_all_aircraft(
    icao24: Optional[str] = Query(None, description="Filter by ICAO 24-bit aircraft identifier (6 hex characters)"),
    callsign: Optional[str] = Query(None, description="Filter by flight callsign (partial match, case-insensitive)"),
    lat: Optional[float] = Query(None, ge=-90, le=90, description="Center latitude for radius search"),
    lon: Optional[float] = Query(None, ge=-180, le=180, description="Center longitude for radius search"),
    radius: Optional[float] = Query(None, gt=0, le=1000, description="Search radius in kilometers"),
    bbox: Optional[str] = Query(None, description="Bounding box as 'lat1,lon1,lat2,lon2' (SW,NE corners)"),
    min_alt: Optional[float] = Query(None, ge=0, le=60000, description="Minimum altitude in feet"),
    max_alt: Optional[float] = Query(None, ge=0, le=60000, description="Maximum altitude in feet"),
    min_speed: Optional[float] = Query(None, ge=0, le=1000, description="Minimum ground speed in knots"),
    max_speed: Optional[float] = Query(None, ge=0, le=1000, description="Maximum ground speed in knots"),
    registration: Optional[str] = Query(None, description="Filter by aircraft registration"),
    airline: Optional[str] = Query(None, description="Filter by operating airline"),
    photos: bool = Query(False, description="Fetch aircraft photos from airport-data.com (slower, max 50 aircraft)"),
):
    """Get all tracked aircraft with optional filtering."""
    try:
        adsb_client = get_adsb_client()
        aircraft_dict = adsb_client.get_aircraft(clean_old=False)

        filtered_aircraft = list(aircraft_dict.values())

        if icao24:
            icao24_validated = _validate_icao24(icao24)
            aircraft = adsb_client.get_aircraft_by_icao24(icao24_validated)
            filtered_aircraft = [aircraft] if aircraft else []

        if callsign:
            filtered_aircraft = filter_aircraft_by_callsign(
                {a.icao24: a for a in filtered_aircraft}, callsign
            )

        if lat is not None and lon is not None and radius is not None:
            filtered_aircraft = filter_aircraft_by_radius(
                {a.icao24: a for a in filtered_aircraft}, lat, lon, radius
            )
        elif (lat is not None) != (lon is not None) or (lat is not None and radius is None):
            raise HTTPException(status_code=400, detail="Radius search requires lat, lon, and radius parameters")

        if bbox:
            try:
                coords = [float(x.strip()) for x in bbox.split(',')]
                if len(coords) != 4:
                    raise ValueError("Bounding box must have 4 coordinates")
                lat1, lon1, lat2, lon2 = coords
                if not (-90 <= lat1 <= 90 and -90 <= lat2 <= 90):
                    raise ValueError("Latitude must be between -90 and 90")
                if not (-180 <= lon1 <= 180 and -180 <= lon2 <= 180):
                    raise ValueError("Longitude must be between -180 and 180")
                if lat1 >= lat2 or lon1 >= lon2:
                    raise ValueError("Invalid bounding box: lat1 < lat2 and lon1 < lon2")
                filtered_aircraft = filter_aircraft_by_bounding_box(
                    {a.icao24: a for a in filtered_aircraft}, lat1, lon1, lat2, lon2
                )
            except ValueError as e:
                raise HTTPException(status_code=400, detail=f"Invalid bounding box format: {str(e)}")

        if min_alt is not None or max_alt is not None:
            if min_alt is not None and max_alt is not None and min_alt >= max_alt:
                raise HTTPException(status_code=400, detail="min_alt must be less than max_alt")
            filtered_aircraft = filter_aircraft_by_altitude(
                {a.icao24: a for a in filtered_aircraft}, min_alt, max_alt
            )

        if min_speed is not None or max_speed is not None:
            if min_speed is not None and max_speed is not None and min_speed >= max_speed:
                raise HTTPException(status_code=400, detail="min_speed must be less than max_speed")
            filtered_aircraft = filter_aircraft_by_speed(
                {a.icao24: a for a in filtered_aircraft}, min_speed, max_speed
            )

        if registration:
            registration_validated = registration.upper().strip()
            aircraft = adsb_client.get_aircraft_by_registration(registration_validated)
            filtered_aircraft = [aircraft] if aircraft else []

        if airline:
            filtered_aircraft = [
                ac for ac in filtered_aircraft
                if ac.airline and airline.lower() in ac.airline.lower()
            ]

        # Convert to response format
        aircraft_responses = []
        for ac in filtered_aircraft:
            resp_data = convert_aircraft_to_response(ac)
            aircraft_responses.append(AircraftResponse(**resp_data))

        # Fetch photos only when explicitly requested
        if photos and aircraft_responses:
            batch = aircraft_responses[:50]
            photo_tasks = [
                fetch_aircraft_photo(ac.icao24, ac.registration)
                for ac in batch
            ]
            photo_results = await asyncio.gather(*photo_tasks, return_exceptions=True)
            for ac_resp, photo in zip(batch, photo_results):
                if isinstance(photo, str):
                    ac_resp.photo_url = photo

        return AircraftListResponse(
            aircraft=aircraft_responses,
            total_count=len(aircraft_responses),
            timestamp=datetime.now()
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve aircraft data: {str(e)}")


@router.get(
    "/aircraft/statistics",
    response_model=Dict[str, Any],
    summary="Get aircraft tracking statistics",
)
async def get_aircraft_statistics():
    """Get statistics about tracked aircraft."""
    try:
        adsb_client = get_adsb_client()
        aircraft_dict = adsb_client.get_aircraft(clean_old=True)
        return calculate_aircraft_statistics(aircraft_dict)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve aircraft statistics: {str(e)}")


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="ADS-B service health check",
)
async def get_adsb_health():
    """Get ADS-B service health status."""
    try:
        adsb_client = get_adsb_client()
        connection_status = adsb_client.get_connection_status()
        aircraft_dict = adsb_client.get_aircraft(clean_old=False)

        last_message_time = None
        if aircraft_dict:
            last_message_time = max(aircraft.last_seen for aircraft in aircraft_dict.values())

        if not connection_status["running"]:
            health_status = "offline"
        elif connection_status["recent_aircraft"] > 0:
            health_status = "healthy"
        elif connection_status["connected"]:
            health_status = "connected_no_data"
        else:
            health_status = "degraded"

        return HealthResponse(
            status=health_status,
            connected=connection_status["connected"],
            active_aircraft_count=connection_status["total_aircraft"],
            connection_uptime=None,
            last_message_received=last_message_time
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve health status: {str(e)}")

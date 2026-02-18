"""
v3 Schedules router.

Paginated departure/arrival schedules with historical/future support via
date/time or raw Unix timestamp parameters.
"""

from fastapi import APIRouter, HTTPException, status, Query
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from data_ingestion.v3.schedules import fetch_schedule
from services.airport_service import airport_service
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/schedules", tags=["Schedules"])

# Avionio keeps 5 days of history and 1 day ahead
MAX_DAYS_BACK = 5
MAX_DAYS_FORWARD = 1


def _resolve_timestamp(
    date: Optional[str],
    time: Optional[str],
    ts: Optional[int],
) -> Optional[int]:
    """
    Resolve date/time parameters to a Unix timestamp in milliseconds.

    Priority: ``ts`` (raw) > ``date`` + optional ``time``.
    """
    if ts is not None:
        return ts

    if date is None:
        return None

    try:
        dt = datetime.strptime(date, "%d-%m-%Y")
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid date format. Use DD-MM-YYYY (e.g. 11-02-2026).",
        )

    if time:
        try:
            t = datetime.strptime(time, "%H:%M")
            dt = dt.replace(hour=t.hour, minute=t.minute)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid time format. Use HH:MM (e.g. 14:30).",
            )

    now = datetime.now()
    earliest = now - timedelta(days=MAX_DAYS_BACK)
    latest = now + timedelta(days=MAX_DAYS_FORWARD)

    if dt < earliest or dt > latest:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Date out of range. Schedules are available from "
                f"{earliest.strftime('%d-%m-%Y')} to {latest.strftime('%d-%m-%Y')}."
            ),
        )

    return int(dt.timestamp() * 1000)


async def _get_iata_from_params(
    icao: Optional[str] = None,
    iata: Optional[str] = None,
) -> tuple[Optional[str], str]:
    """Get IATA code from either ICAO or IATA parameter."""
    if not icao and not iata:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either ICAO or IATA code must be provided",
        )
    if icao and iata:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide either ICAO or IATA code, not both",
        )

    if iata:
        iata = iata.upper().strip()
        if len(iata) != 3:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="IATA code must be exactly 3 characters",
            )
        airport = await airport_service.find_airport_by_code(iata)
        if not airport:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Airport not found for IATA code: {iata}",
            )
        return iata, iata

    icao = icao.upper().strip()
    if len(icao) != 4:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ICAO code must be exactly 4 characters",
        )
    airport = await airport_service.find_airport_by_code(icao)
    if not airport:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Airport not found for ICAO code: {icao}",
        )
    airport_iata = airport.get("iata_code")
    if not airport_iata:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No IATA code available for airport: {icao}",
        )
    return airport_iata, icao


@router.get(
    "/departures",
    responses={
        200: {
            "description": "Airport departure schedule (up to 12 hours)",
            "content": {
                "application/json": {
                    "example": {
                        "iata": "MXP",
                        "direction": "departures",
                        "airport_code": "LIMC",
                        "flights": [
                            {
                                "Time": "16:05",
                                "Date": "11 Feb",
                                "IATA": "ICN",
                                "Destination": "Seoul",
                                "Flight": "C84093",
                                "Airline": "Federal Airlines",
                                "Status": "Estimated 16:39",
                            }
                        ],
                        "total_flights": 85,
                        "pages_fetched": 3,
                    }
                }
            },
        }
    },
)
async def get_departures(
    icao: Optional[str] = Query(
        None, description="4-letter ICAO airport code (e.g. KJFK, EGLL)",
        min_length=4, max_length=4,
    ),
    iata: Optional[str] = Query(
        None, description="3-letter IATA airport code (e.g. JFK, LHR)",
        min_length=3, max_length=3,
    ),
    date: Optional[str] = Query(
        None,
        description="Date in DD-MM-YYYY format (e.g. 11-02-2026). Range: 5 days back to 1 day forward.",
    ),
    time: Optional[str] = Query(
        None,
        description="Time in HH:MM format (e.g. 14:30). Requires date parameter.",
    ),
    ts: Optional[int] = Query(
        None,
        description="Unix timestamp in milliseconds (alternative to date/time).",
    ),
) -> Dict[str, Any]:
    """
    Get departure schedule for an airport (next ~12 hours by default).

    - **icao** or **iata**: Airport code (provide one, not both)
    - **date** / **time**: Human-readable date and time (DD-MM-YYYY, HH:MM)
    - **ts**: Unix timestamp in ms (alternative to date/time)

    History is available up to 5 days back and 1 day forward.
    """
    try:
        iata_code, airport_identifier = await _get_iata_from_params(icao=icao, iata=iata)
        resolved_ts = _resolve_timestamp(date, time, ts)

        result = await fetch_schedule(iata_code, direction="departures", ts=resolved_ts)
        if not result or "error" in result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Departure schedule not available for {airport_identifier}",
            )

        result["airport_code"] = airport_identifier
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error fetching departures - ICAO: %s, IATA: %s: %s", icao, iata, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to fetch departure schedule at this time",
        )


@router.get(
    "/arrivals",
    responses={
        200: {
            "description": "Airport arrival schedule (up to 12 hours)",
            "content": {
                "application/json": {
                    "example": {
                        "iata": "MXP",
                        "direction": "arrivals",
                        "airport_code": "LIMC",
                        "flights": [
                            {
                                "Time": "16:20",
                                "Date": "11 Feb",
                                "IATA": "RAK",
                                "Origin": "Marrakech",
                                "Flight": "EC3929",
                                "Airline": "easyJet Europe",
                                "Status": "Landed 16:15",
                            }
                        ],
                        "total_flights": 72,
                        "pages_fetched": 3,
                    }
                }
            },
        }
    },
)
async def get_arrivals(
    icao: Optional[str] = Query(
        None, description="4-letter ICAO airport code (e.g. KJFK, EGLL)",
        min_length=4, max_length=4,
    ),
    iata: Optional[str] = Query(
        None, description="3-letter IATA airport code (e.g. JFK, LHR)",
        min_length=3, max_length=3,
    ),
    date: Optional[str] = Query(
        None,
        description="Date in DD-MM-YYYY format (e.g. 11-02-2026). Range: 5 days back to 1 day forward.",
    ),
    time: Optional[str] = Query(
        None,
        description="Time in HH:MM format (e.g. 14:30). Requires date parameter.",
    ),
    ts: Optional[int] = Query(
        None,
        description="Unix timestamp in milliseconds (alternative to date/time).",
    ),
) -> Dict[str, Any]:
    """
    Get arrival schedule for an airport (next ~12 hours by default).

    - **icao** or **iata**: Airport code (provide one, not both)
    - **date** / **time**: Human-readable date and time (DD-MM-YYYY, HH:MM)
    - **ts**: Unix timestamp in ms (alternative to date/time)

    History is available up to 5 days back and 1 day forward.
    """
    try:
        iata_code, airport_identifier = await _get_iata_from_params(icao=icao, iata=iata)
        resolved_ts = _resolve_timestamp(date, time, ts)

        result = await fetch_schedule(iata_code, direction="arrivals", ts=resolved_ts)
        if not result or "error" in result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Arrival schedule not available for {airport_identifier}",
            )

        result["airport_code"] = airport_identifier
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error fetching arrivals - ICAO: %s, IATA: %s: %s", icao, iata, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to fetch arrival schedule at this time",
        )

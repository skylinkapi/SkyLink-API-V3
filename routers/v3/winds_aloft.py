"""
v3 Winds Aloft router.

FB Winds (Winds and Temperatures Aloft Forecast) for US airports.
Data from aviationweather.gov — free, no authentication.
"""

import logging

from fastapi import APIRouter, HTTPException, Path, Query, status

from data_ingestion.v3.winds_aloft import fetch_winds_aloft, get_station_for_icao
from models.v3.winds_aloft import WindsAloftResponse

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/weather",
    tags=["Winds Aloft"],
)


@router.get(
    "/winds-aloft/{icao}",
    response_model=WindsAloftResponse,
    summary="Get winds aloft forecast for an airport",
    description=(
        "Returns wind direction, speed, and temperature at standard altitude levels "
        "for the FB winds station nearest to the given ICAO code.\n\n"
        "**Coverage:** US airports only (FAA FD product).\n\n"
        "**Altitudes (low):** 3,000 – 39,000 ft\n"
        "**Altitudes (high):** 6,000 – 45,000 ft\n\n"
        "**Source:** aviationweather.gov (real-time, no caching)"
    ),
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {
                        "station": "JFK",
                        "icao": "KJFK",
                        "forecast_hour": 12,
                        "level": "low",
                        "valid_time": "130000Z",
                        "winds": [
                            {
                                "altitude_ft": 3000,
                                "wind_direction": 270,
                                "wind_speed_kt": 9,
                                "temperature_c": 15,
                                "light_and_variable": False,
                                "raw": "2709+15",
                            }
                        ],
                        "raw_text": "JFK      2709+15 3012+08 ...",
                    }
                }
            }
        },
        404: {"description": "No winds aloft data found for this airport"},
    },
)
async def get_winds_aloft(
    icao: str = Path(
        ..., description="4-letter ICAO airport code (US airports, e.g. KJFK)", min_length=4, max_length=4
    ),
    forecast: int = Query(
        12, description="Forecast period in hours (6, 12, or 24)", ge=6, le=24
    ),
    level: str = Query(
        "low", description="Altitude range: 'low' (3K-39K ft) or 'high' (6K-45K ft)", pattern="^(low|high)$"
    ),
):
    """Get winds aloft forecast for a US airport."""
    icao = icao.upper().strip()

    # Normalize forecast to valid values
    if forecast <= 6:
        forecast = 6
    elif forecast <= 12:
        forecast = 12
    else:
        forecast = 24

    station = get_station_for_icao(icao)
    if not station:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"No FB winds station mapping found for {icao}. "
                "Winds aloft data is available for US airports only."
            ),
        )

    try:
        data = await fetch_winds_aloft(station, forecast=forecast, level=level)
    except Exception as e:
        logger.error(f"Error fetching winds aloft for {icao} (station {station}): {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Winds aloft service temporarily unavailable",
        )

    if data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Station {station} not found in the current FB winds product for forecast={forecast}h, level={level}",
        )

    data["icao"] = icao
    return WindsAloftResponse(**data)

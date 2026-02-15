"""
Router for ML-based flight time predictions.

GET /v3/ml/flight-time?from=KJFK&to=EGLL&aircraft=B738
"""

from fastapi import APIRouter, Query, HTTPException

from models.v3.flight_time import FlightTimePrediction
from services.v3.flight_time_service import predict_flight_time

router = APIRouter(prefix="/ml", tags=["ML Predictions"])


@router.get(
    "/flight-time",
    response_model=FlightTimePrediction,
    summary="Estimate flight time between airports",
    description=(
        "Predict gate-to-gate flight time using a trained ML model. "
        "Accepts ICAO or IATA airport codes and an optional aircraft type. "
        "Falls back to a distance/speed calculation if the ML model is unavailable."
    ),
)
async def get_flight_time(
    from_airport: str = Query(
        ..., alias="from", min_length=3, max_length=4,
        description="Origin airport ICAO or IATA code",
    ),
    to_airport: str = Query(
        ..., alias="to", min_length=3, max_length=4,
        description="Destination airport ICAO or IATA code",
    ),
    aircraft: str = Query(
        None, max_length=4,
        description="Aircraft type code (e.g. B738, A320, C172)",
    ),
):
    try:
        return await predict_flight_time(from_airport, to_airport, aircraft)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction error: {e}")

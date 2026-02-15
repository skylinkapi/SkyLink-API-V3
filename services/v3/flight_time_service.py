"""
ML-based flight time prediction service.

Loads a trained GradientBoostingRegressor from a .joblib artifact and
predicts gate-to-gate flight times.  Falls back to a simple distance/speed
calculation when the model file is unavailable.
"""

import logging
from pathlib import Path
from typing import Optional

import numpy as np

from models.v3.distance import DistanceUnit
from services.v3.distance_service import distance_service

logger = logging.getLogger(__name__)

# ── Model loading (singleton) ──────────────────────────────────────────────

MODEL_PATH = Path(__file__).resolve().parent.parent.parent / "ml_models" / "flight_time_model.joblib"

_artifact: Optional[dict] = None
_model_loaded = False


def _load_model():
    """Attempt to load the model artifact once."""
    global _artifact, _model_loaded
    if _model_loaded:
        return
    _model_loaded = True

    if not MODEL_PATH.exists():
        logger.warning("Flight time model not found at %s — using fallback", MODEL_PATH)
        return

    try:
        import joblib
        _artifact = joblib.load(MODEL_PATH)
        logger.info(
            "Loaded flight time model v%s (aircraft types: %s)",
            _artifact.get("version", "?"),
            len(_artifact.get("aircraft_classes", [])),
        )
    except Exception as e:
        logger.error("Failed to load flight time model: %s", e)


_load_model()


# ── Default cruise parameters by aircraft category ─────────────────────────

_DEFAULTS = {
    # Narrowbody jets
    "B738": (460, 36000), "A320": (450, 36000), "A321": (450, 36000),
    "B752": (460, 38000), "B737": (460, 36000),
    # Widebody jets
    "B77W": (490, 39000), "A388": (490, 39000), "B789": (490, 41000),
    "B744": (490, 37000), "B763": (470, 37000), "A332": (480, 38000),
    "A359": (490, 41000),
    # Regional jets
    "E175": (430, 35000), "E190": (440, 36000), "CRJ9": (430, 35000),
    # Piston / GA
    "C172": (110, 8000),
}
_DEFAULT_JET = (460, 36000)  # fallback for unknown jet types


def _get_cruise_defaults(aircraft_type: Optional[str]) -> tuple[int, int]:
    """Return (cruise_speed_kts, cruise_altitude_ft) for an aircraft type."""
    if aircraft_type and aircraft_type.upper() in _DEFAULTS:
        return _DEFAULTS[aircraft_type.upper()]
    return _DEFAULT_JET


# ── Route deviation factors for airspace restrictions ──────────────────────
# Accounts for Russian airspace closure, conflict zones, oceanic routing, etc.
# Format: (origin_region, dest_region) → approximate deviation factor
# where region is determined by ICAO prefix.

_REGION_DEVIATIONS: dict[tuple[str, str], float] = {
    # Europe ↔ East Asia (Russian airspace ban — major detour via polar/southern)
    ("EU", "EA"): 1.25, ("EA", "EU"): 1.25,
    # Europe ↔ Japan/Korea specifically (longest detours)
    ("EU", "JP"): 1.30, ("JP", "EU"): 1.30,
    ("EU", "KR"): 1.28, ("KR", "EU"): 1.28,
    # North America ↔ Central Asia (routing around Russia)
    ("NA", "CA"): 1.15, ("CA", "NA"): 1.15,
}

_ICAO_REGION_MAP: dict[str, str] = {
    # Europe
    "E": "EU", "L": "EU", "BI": "EU", "UL": "EU", "UM": "EU",
    # East Asia (China)
    "Z": "EA",
    # Japan
    "RJ": "JP",
    # Korea
    "RK": "KR",
    # SE Asia
    "V": "EA", "W": "EA", "RP": "EA",
    # North America
    "K": "NA", "C": "NA", "M": "NA", "PA": "NA",
    # South America
    "S": "SA",
    # Africa
    "F": "AF", "H": "AF", "G": "AF", "D": "AF",
    # Middle East
    "O": "ME",
    # Oceania
    "Y": "OC", "N": "OC",
    # Central Asia
    "U": "CA",
}


def _get_region(icao: str) -> Optional[str]:
    """Map an ICAO code to a region key."""
    icao = icao.upper()
    # Try 2-char prefix first, then 1-char
    if icao[:2] in _ICAO_REGION_MAP:
        return _ICAO_REGION_MAP[icao[:2]]
    if icao[:1] in _ICAO_REGION_MAP:
        return _ICAO_REGION_MAP[icao[:1]]
    return None


def _estimate_deviation(from_icao: str, to_icao: str) -> float:
    """Estimate route deviation factor based on origin/destination regions."""
    r1 = _get_region(from_icao)
    r2 = _get_region(to_icao)
    if r1 and r2:
        return _REGION_DEVIATIONS.get((r1, r2), 1.0)
    return 1.0


def _format_duration(minutes: int) -> str:
    """Format minutes as 'Xh Ym'."""
    h, m = divmod(minutes, 60)
    if h == 0:
        return f"{m}m"
    return f"{h}h {m}m"


# ── Fallback estimator ─────────────────────────────────────────────────────

def _fallback_estimate(distance_nm: float, aircraft_type: Optional[str], deviation: float = 1.0) -> int:
    """Simple distance / speed + taxi estimate, adjusted for routing deviation."""
    speed, _ = _get_cruise_defaults(aircraft_type)
    actual_distance = distance_nm * deviation
    # Add 20 min for taxi, climb, descent
    cruise_time = (actual_distance / speed) * 60
    return max(int(round(cruise_time + 20)), 15)


# ── Public API ──────────────────────────────────────────────────────────────

async def predict_flight_time(
    from_icao: str,
    to_icao: str,
    aircraft_type: Optional[str] = None,
) -> dict:
    """
    Predict flight time between two airports.

    Returns a dict matching FlightTimePrediction fields.
    """
    # Resolve distance
    result = await distance_service.calculate(
        from_icao, to_icao, unit=DistanceUnit.NAUTICAL_MILES
    )
    distance_nm = result["distance"]

    acft = aircraft_type.upper().strip() if aircraft_type else None
    speed, altitude = _get_cruise_defaults(acft)
    deviation = _estimate_deviation(from_icao, to_icao)

    # Try ML model
    version = "fallback"
    fallback_est = _fallback_estimate(distance_nm, acft, deviation)

    # Short hops (<50 nm) — always use fallback; the ML model was trained
    # on airline routes and produces nonsense for very short distances.
    if _artifact is not None and distance_nm >= 50:
        try:
            model = _artifact["model"]
            scaler = _artifact["scaler"]
            le = _artifact["label_encoder"]
            feature_cols = _artifact.get("feature_cols", [])
            version = _artifact.get("version", "1.0.0")

            # Encode aircraft type — use first known class if unknown
            if acft and acft in le.classes_:
                acft_encoded = le.transform([acft])[0]
            else:
                acft_encoded = le.transform([le.classes_[0]])[0]

            # Build feature vector matching training columns
            if "route_deviation_factor" in feature_cols:
                features = np.array([[distance_nm, acft_encoded, speed, altitude, deviation]])
            else:
                features = np.array([[distance_nm, acft_encoded, speed, altitude]])

            features_scaled = scaler.transform(features)
            predicted = model.predict(features_scaled)[0]
            estimated = max(int(round(predicted)), 15)

            # Sanity check: if ML prediction is wildly off vs. physics-based
            # fallback, discard it (model extrapolating outside training data)
            if estimated > fallback_est * 2:
                logger.warning(
                    "ML prediction %d min vs fallback %d min for %s→%s (%s) — "
                    "using fallback (ratio %.1fx)",
                    estimated, fallback_est, from_icao, to_icao, acft,
                    estimated / fallback_est,
                )
                estimated = fallback_est
                version = "fallback"
        except Exception as e:
            logger.warning("ML prediction failed, using fallback: %s", e)
            estimated = fallback_est
    else:
        estimated = fallback_est

    # Compute range (±12% for ML, ±15% for fallback)
    margin = 0.12 if _artifact is not None else 0.15
    min_min = max(int(round(estimated * (1 - margin))), 10)
    max_min = int(round(estimated * (1 + margin)))

    return {
        "origin": from_icao.upper(),
        "destination": to_icao.upper(),
        "aircraft_type": acft,
        "distance_nm": distance_nm,
        "estimated_minutes": estimated,
        "estimated_hours_display": _format_duration(estimated),
        "min_minutes": min_min,
        "max_minutes": max_min,
        "model_version": version,
    }

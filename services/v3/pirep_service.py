"""
PIREPs (Pilot Reports) service.

Primary: avwx-engine (avwx.Pireps)
Fallback: aviationweather.gov JSON API
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

AWC_PIREP_URL = "https://aviationweather.gov/api/data/pirep"

# Turbulence intensity mapping
_TB_INTENSITY = {
    0: "None", 1: "Light", 2: "Light", 3: "Moderate",
    4: "Moderate", 5: "Severe", 6: "Severe", 7: "Extreme", 8: "Extreme",
}

# Icing intensity mapping
_IC_INTENSITY = {
    0: "None", 1: "Trace", 2: "Trace", 3: "Light",
    4: "Light", 5: "Moderate", 6: "Moderate", 7: "Heavy", 8: "Heavy",
}


def _safe_str(obj: Any) -> Optional[str]:
    """Convert to string if not None/empty."""
    if obj is None:
        return None
    s = str(obj).strip()
    return s if s else None


async def _fetch_via_avwx(lat: float, lon: float) -> Optional[List[Dict]]:
    """Try fetching PIREPs via avwx-engine."""
    try:
        import avwx
        from avwx.structs import Coord

        pireps = avwx.Pireps(coord=Coord(lat=lat, lon=lon))
        success = await pireps.async_update()

        if not success or not pireps.data:
            return None

        results = []
        for report in pireps.data:
            if report is None:
                continue
            results.append({
                "raw": getattr(report, "raw", "") or "",
                "report_type": _safe_str(getattr(report, "type", None)),
                "location": _safe_str(getattr(report, "location", None)),
                "time": _safe_str(getattr(report, "time", None)),
                "altitude": _safe_str(getattr(report, "altitude", None)),
                "aircraft_type": _safe_str(getattr(report, "aircraft", None)),
                "sky_conditions": _safe_str(getattr(report, "clouds", None)),
                "turbulence": _safe_str(getattr(report, "turbulence", None)),
                "icing": _safe_str(getattr(report, "icing", None)),
                "temperature": _safe_str(getattr(report, "temperature", None)),
                "wind": None,
                "remarks": _safe_str(getattr(report, "remarks", None)),
                "latitude": None,
                "longitude": None,
            })

        return results if results else None

    except Exception as e:
        logger.warning(f"avwx PIREPs failed: {e}")
        return None


async def _fetch_via_awc(icao: str, radius_nm: int, hours: int) -> Optional[List[Dict]]:
    """Fallback: fetch PIREPs from aviationweather.gov JSON API."""
    try:
        params = {
            "id": icao,
            "distance": min(radius_nm, 500),
            "format": "json",
            "hours": min(hours, 24),
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(AWC_PIREP_URL, params=params)
            resp.raise_for_status()

        data = resp.json()
        if not isinstance(data, list):
            return None

        results = []
        for item in data:
            # Build turbulence string
            tb_parts = []
            for i in (1, 2):
                intensity = item.get(f"tbInt{i}")
                if intensity is not None:
                    tb_str = _TB_INTENSITY.get(intensity, str(intensity))
                    tb_base = item.get(f"tbBas{i}")
                    tb_top = item.get(f"tbTop{i}")
                    if tb_base is not None and tb_top is not None:
                        tb_str += f" FL{tb_base}-FL{tb_top}"
                    tb_parts.append(tb_str)
            turbulence = "; ".join(tb_parts) if tb_parts else None

            # Build icing string
            ic_parts = []
            for i in (1, 2):
                intensity = item.get(f"icgInt{i}")
                if intensity is not None:
                    ic_str = _IC_INTENSITY.get(intensity, str(intensity))
                    ic_base = item.get(f"icgBas{i}")
                    ic_top = item.get(f"icgTop{i}")
                    if ic_base is not None and ic_top is not None:
                        ic_str += f" FL{ic_base}-FL{ic_top}"
                    ic_parts.append(ic_str)
            icing = "; ".join(ic_parts) if ic_parts else None

            # Wind string
            wdir = item.get("wdir")
            wspd = item.get("wspd")
            wind = f"{wdir:03d}/{wspd}kt" if wdir is not None and wspd is not None else None

            # Observation time
            obs_time = item.get("obsTime")
            time_str = None
            if obs_time:
                try:
                    dt = datetime.fromtimestamp(obs_time, tz=timezone.utc)
                    time_str = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
                except (ValueError, OSError):
                    pass

            # PIREP type
            pirep_type = item.get("pirepType", "")
            report_type = "UUA" if "Urgent" in pirep_type else "UA"

            results.append({
                "raw": item.get("rawOb", ""),
                "report_type": report_type,
                "location": item.get("icaoId"),
                "time": time_str,
                "altitude": f"FL{item['fltLvl']}" if item.get("fltLvl") is not None else None,
                "aircraft_type": item.get("acType"),
                "sky_conditions": _safe_str(item.get("clouds")),
                "turbulence": turbulence,
                "icing": icing,
                "temperature": f"{item['temp']}C" if item.get("temp") is not None else None,
                "wind": wind,
                "remarks": item.get("brkAction") or None,
                "latitude": item.get("lat"),
                "longitude": item.get("lon"),
            })

        return results if results else None

    except Exception as e:
        logger.warning(f"AWC PIREPs fallback failed: {e}")
        return None


async def get_pireps(
    icao: str,
    lat: float,
    lon: float,
    radius_nm: int = 100,
    hours: int = 2,
) -> Dict:
    """Fetch PIREPs near an airport.

    Tries avwx first, falls back to aviationweather.gov.
    Returns dict ready for PIREPResponse.
    """
    reports = await _fetch_via_avwx(lat, lon)

    if reports is None:
        reports = await _fetch_via_awc(icao, radius_nm, hours)

    if reports is None:
        reports = []

    return {
        "icao": icao,
        "radius_nm": radius_nm,
        "hours": hours,
        "reports": reports,
        "total": len(reports),
    }

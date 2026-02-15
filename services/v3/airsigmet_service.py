"""
AIRMET/SIGMET service.

Fetches AIRMET/SIGMET advisories from aviationweather.gov JSON API and
optionally filters by coordinate (point-in-polygon) or advisory type.

Domestic: https://aviationweather.gov/api/data/airsigmet
International: https://aviationweather.gov/api/data/isigmet
"""

import logging
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

_AWG_AIRSIGMET_URL = "https://aviationweather.gov/api/data/airsigmet"
_AWG_ISIGMET_URL = "https://aviationweather.gov/api/data/isigmet"


def _coords_in_polygon(lat: float, lon: float, coords: List[Dict]) -> bool:
    """Ray-casting point-in-polygon check."""
    n = len(coords)
    if n < 3:
        return False
    inside = False
    j = n - 1
    for i in range(n):
        yi, xi = coords[i]["lat"], coords[i]["lon"]
        yj, xj = coords[j]["lat"], coords[j]["lon"]
        if ((yi > lat) != (yj > lat)) and (lon < (xj - xi) * (lat - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def _parse_domestic(item: Dict) -> Dict:
    """Convert a domestic airsigmet JSON object to our response format."""
    coords = [{"lat": c["lat"], "lon": c["lon"]} for c in (item.get("coords") or [])]

    movement = None
    if item.get("movementDir") or item.get("movementSpd"):
        movement = {
            "direction": str(item["movementDir"]) if item.get("movementDir") is not None else None,
            "speed": str(item["movementSpd"]) + " kt" if item.get("movementSpd") is not None else None,
        }

    floor = None
    ceiling = None
    if item.get("altitudeLow1") is not None or item.get("altitudeLow2") is not None:
        alt = item.get("altitudeLow1") or item.get("altitudeLow2")
        floor = f"FL{alt // 100}" if alt and alt >= 18000 else f"{alt} ft" if alt else "SFC"
    if item.get("altitudeHi1") is not None or item.get("altitudeHi2") is not None:
        alt = item.get("altitudeHi2") or item.get("altitudeHi1")
        ceiling = f"FL{alt // 100}" if alt and alt >= 18000 else f"{alt} ft" if alt else None

    return {
        "raw": item.get("rawAirSigmet", ""),
        "bulletin_type": item.get("airSigmetType"),
        "country": "US",
        "issuer": item.get("icaoId"),
        "area": item.get("alphaChar"),
        "report_type": item.get("airSigmetType"),
        "start_time": item.get("validTimeFrom"),
        "end_time": item.get("validTimeTo"),
        "body": item.get("rawAirSigmet", ""),
        "region": None,
        "observation": {
            "type": item.get("hazard"),
            "intensity": item.get("severity"),
            "floor": floor,
            "ceiling": ceiling,
            "coords": coords,
            "movement": movement,
        },
        "forecast": None,
    }


def _parse_international(item: Dict) -> Dict:
    """Convert an international SIGMET JSON object to our response format."""
    raw_coords = item.get("coords") or []
    # Some items have nested lists (multiple polygons) — flatten to first polygon
    coords = []
    for c in raw_coords:
        if isinstance(c, dict):
            coords.append({"lat": c["lat"], "lon": c["lon"]})
        elif isinstance(c, list) and c:
            # Nested polygon — use first one
            for inner in c:
                if isinstance(inner, dict):
                    coords.append({"lat": inner["lat"], "lon": inner["lon"]})
            break

    movement = None
    if item.get("dir") or item.get("spd"):
        movement = {
            "direction": str(item["dir"]) if item.get("dir") is not None else None,
            "speed": str(item["spd"]) + " kt" if item.get("spd") is not None else None,
        }

    floor = None
    ceiling = None
    if item.get("base") is not None:
        b = item["base"]
        floor = f"FL{b // 100}" if b >= 18000 else f"{b} ft" if b > 0 else "SFC"
    if item.get("top") is not None:
        t = item["top"]
        ceiling = f"FL{t // 100}" if t >= 18000 else f"{t} ft" if t else None

    return {
        "raw": item.get("rawSigmet", ""),
        "bulletin_type": "SIGMET",
        "country": item.get("icaoId"),
        "issuer": item.get("icaoId"),
        "area": item.get("firId"),
        "report_type": "SIGMET",
        "start_time": item.get("validTimeFrom"),
        "end_time": item.get("validTimeTo"),
        "body": item.get("rawSigmet", ""),
        "region": item.get("firName"),
        "observation": {
            "type": item.get("hazard"),
            "intensity": item.get("qualifier"),
            "floor": floor,
            "ceiling": ceiling,
            "coords": coords,
            "movement": movement,
        },
        "forecast": None,
    }


async def get_airsigmets(
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    filter_type: Optional[str] = None,
) -> Dict:
    """Fetch AIRMET/SIGMETs, optionally filtering by coord or type."""
    results: List[Dict] = []

    async with httpx.AsyncClient(timeout=15.0) as client:
        # Domestic AIRMETs/SIGMETs
        try:
            resp = await client.get(_AWG_AIRSIGMET_URL, params={"format": "json"})
            resp.raise_for_status()
            for item in resp.json():
                results.append(_parse_domestic(item))
        except Exception as e:
            logger.warning(f"Failed to fetch domestic AIRMETs/SIGMETs: {e}")

        # International SIGMETs
        try:
            resp = await client.get(_AWG_ISIGMET_URL, params={"format": "json"})
            resp.raise_for_status()
            for item in resp.json():
                if not item:
                    continue
                results.append(_parse_international(item))
        except Exception as e:
            logger.warning(f"Failed to fetch international SIGMETs: {e}")

    # Filter by type
    if filter_type:
        ft = filter_type.upper()
        results = [
            r for r in results
            if ft in (r.get("report_type") or "").upper()
        ]

    # Filter by coordinate containment
    if lat is not None and lon is not None:
        filtered = []
        for r in results:
            obs = r.get("observation") or {}
            coords = obs.get("coords", [])
            if coords and _coords_in_polygon(lat, lon, coords):
                filtered.append(r)
        results = filtered

    return {
        "reports": results,
        "total": len(results),
        "filter_type": filter_type,
    }

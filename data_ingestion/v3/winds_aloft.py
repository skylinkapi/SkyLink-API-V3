"""
Fetch and parse FB Winds Aloft forecasts from aviationweather.gov.

Source: https://aviationweather.gov/api/data/windtemp
Free, no authentication. Returns plain text in FAA FB winds format.

Encoding (per altitude): DDSSTT or DDSS+TT or DDSS-TT
  DD = wind direction / 10 (e.g. 27 = 270°)
  SS = wind speed in knots
  TT = temperature in °C (sign indicated by +/- or position)

Special cases:
  - Speed >= 100 kt: DD has 50 added (e.g. 7509 = 250° at 109 kt)
  - "9900" = light and variable (< 5 kt)
  - Blank = no data at that altitude (e.g. 3000 ft at far stations)
"""

import logging
import re
from typing import Dict, List, Optional, Tuple

import httpx

logger = logging.getLogger(__name__)

WINDS_URL = "https://aviationweather.gov/api/data/windtemp"

# Standard altitude levels (feet MSL) for low and high products
LOW_ALTITUDES = [3000, 6000, 9000, 12000, 18000, 24000, 30000, 34000, 39000]
HIGH_ALTITUDES = [6000, 9000, 12000, 18000, 24000, 30000, 34000, 39000, 45000]

# ── ICAO → FB Winds station mapping ──────────────────────────────────────────
# The FB winds product uses 3-letter station IDs. This maps ICAO prefixes and
# specific codes to the nearest FB winds station.

# Major airports → their exact FB station
_ICAO_TO_STATION: Dict[str, str] = {
    "KJFK": "JFK", "KLGA": "LGA", "KEWR": "EWR", "KBOS": "BOS",
    "KPHL": "PHL", "KIAD": "IAD", "KDCA": "DCA", "KBWI": "BWI",
    "KATL": "ATL", "KMIA": "MIA", "KFLL": "FLL", "KMCO": "MCO",
    "KTPA": "TPA", "KJAX": "JAX", "KCLT": "CLT", "KRDU": "RDU",
    "KORD": "ORD", "KMDW": "MDW", "KDTW": "DTW", "KMSP": "MSP",
    "KMKE": "MKE", "KCLE": "CLE", "KCVG": "CVG", "KCMH": "CMH",
    "KIND": "IND", "KSTL": "STL", "KMCI": "MCI", "KOMA": "OMA",
    "KBNA": "BNA", "KMEM": "MEM", "KPIT": "PIT", "KBUF": "BUF",
    "KDFW": "DFW", "KIAH": "IAH", "KHOU": "HOU", "KSAT": "SAT",
    "KAUS": "AUS", "KDEN": "DEN", "KSLC": "SLC", "KABQ": "ABQ",
    "KPHX": "PHX", "KTUS": "TUS", "KELP": "ELP", "KLAS": "LAS",
    "KLAX": "LAX", "KSFO": "SFO", "KOAK": "OAK", "KSJC": "SJC",
    "KSAN": "SAN", "KSEA": "SEA", "KPDX": "PDX", "KBOI": "BOI",
    "KGEG": "GEG", "PANC": "ANC", "PAFA": "FAI", "PHNL": "HNL",
    "PHOG": "OGG", "PHKO": "ITO",
    "KMSN": "MSN", "KDSM": "DSM", "KLIT": "LIT", "KJAN": "JAN",
    "KLEX": "LEX", "KSDF": "SDF", "KRIC": "RIC", "KORF": "ORF",
    "KPWM": "PWM", "KBTV": "BTV", "KBDL": "BDL", "KALB": "ALB",
    "KSYR": "SYR", "KROC": "ROC", "KBGR": "BGR", "KPBI": "PBI",
    "KRSW": "RSW", "KSAV": "SAV", "KCHS": "CHS", "KGSO": "GSO",
    "KCRW": "CRW", "KTYS": "TYS", "KBHM": "BHM", "KMOB": "MOB",
    "KMSY": "MSY", "KSHV": "SHV", "KOKC": "OKC", "KTUL": "TUL",
    "KICT": "ICT", "KFSD": "FSD", "KBIS": "BIS", "KFAR": "FAR",
    "KRAP": "RAP", "KGJT": "GJT", "KCYS": "CYS", "KBIL": "BIL",
    "KGTF": "GTF", "KMSO": "MSO", "KHLN": "HLN", "KFCA": "FCA",
    "KRNO": "RNO", "KSMF": "SMF", "KFAT": "FAT", "KBFL": "BFL",
    "KSBA": "SBA", "KONT": "ONT", "KMED": "MFR", "KRDM": "RDM",
    "KEUG": "EUG", "KYKM": "YKM",
}


def _icao_to_station(icao: str) -> Optional[str]:
    """Map an ICAO code to its nearest FB winds station identifier."""
    icao = icao.upper().strip()

    # Direct mapping
    if icao in _ICAO_TO_STATION:
        return _ICAO_TO_STATION[icao]

    # For US K-prefix airports, try the 3-letter FAA code
    if icao.startswith("K") and len(icao) == 4:
        return icao[1:]

    # Alaska / Hawaii
    if icao.startswith("PA") and len(icao) == 4:
        return _ICAO_TO_STATION.get(icao)
    if icao.startswith("PH") and len(icao) == 4:
        return _ICAO_TO_STATION.get(icao)

    return None


def _determine_region(icao: str) -> str:
    """Pick the best aviationweather.gov region for an ICAO code."""
    # Always use "all" to get the complete dataset — simplest approach
    return "all"


def _parse_wind_group(group: str) -> Tuple[Optional[int], Optional[int], Optional[int], bool]:
    """Parse a single wind/temp group (e.g. '2709+15', '277638', '9900-08').

    Returns (direction_deg, speed_kt, temp_c, light_and_variable).
    """
    group = group.strip()
    if not group:
        return None, None, None, False

    # Light and variable
    if group.startswith("9900"):
        temp_c = None
        rest = group[4:]
        if rest:
            rest = rest.lstrip("+-")
            if rest.lstrip("-").isdigit():
                val = int(rest)
                # Temps above FL240 are always negative
                temp_c = -val if val > 0 and group[4:5] == "-" else (val if group[4:5] == "+" else -val)
        return None, None, temp_c, True

    # Standard format: DDSS or DDSSTT or DDSS+TT or DDSS-TT
    # Strip sign for temperature parsing
    match = re.match(r'^(\d{4})(([+-]?\d{1,2})?)$', group)
    if not match:
        return None, None, None, False

    dd_ss = match.group(1)
    temp_part = match.group(2)

    dd = int(dd_ss[:2])
    ss = int(dd_ss[2:4])

    # If DD >= 51, subtract 50 and add 100 to speed
    if dd >= 51:
        dd -= 50
        ss += 100

    direction = dd * 10
    if direction == 0 and ss == 0:
        return None, None, None, False

    # Temperature
    temp_c = None
    if temp_part:
        temp_str = temp_part.lstrip("+")
        if temp_str and (temp_str.lstrip("-").isdigit()):
            temp_c = int(temp_str)

    return direction, ss, temp_c, False


def _parse_6char_group(group: str) -> Tuple[Optional[int], Optional[int], Optional[int], bool]:
    """Parse a 6-character wind group where temp is embedded (e.g. '277638' = 270° 76kt -38°C)."""
    group = group.strip()
    if len(group) != 6 or not group.isdigit():
        return _parse_wind_group(group)

    dd = int(group[0:2])
    ss = int(group[2:4])
    tt = int(group[4:6])

    if dd >= 51:
        dd -= 50
        ss += 100

    direction = dd * 10
    # Temperatures at upper levels (30000+) are always negative
    temp_c = -tt if tt > 0 else 0

    if group.startswith("9900"):
        return None, None, -tt if tt > 0 else None, True

    return direction, ss, temp_c, False


def _parse_station_line(line: str, altitudes: List[int]) -> Optional[Dict]:
    """Parse a single station line from the FB winds text.

    Example line:
    ABQ      2709+15 3012+08 2921+03 2644-12 2763-25 277638 277648 268956
    """
    line = line.rstrip()
    if len(line) < 10:
        return None

    # Station ID is the first non-space token
    parts = line.split()
    if not parts:
        return None

    station = parts[0]
    # Station IDs are 2-4 alpha chars
    if not re.match(r'^[A-Z]{2,4}$', station):
        return None

    # The rest of the line contains wind groups in fixed-width columns
    # The data portion starts after the station ID
    # Column positions are roughly: station(0-4), then 8-char columns per altitude
    # But it's easier to parse by splitting on whitespace and matching count
    data_tokens = parts[1:]

    winds = []
    for i, alt in enumerate(altitudes):
        if i < len(data_tokens):
            token = data_tokens[i]
            # 6-char groups have embedded temp, 4-char have separate or no temp
            if len(token) == 6 and token.isdigit():
                direction, speed, temp, lv = _parse_6char_group(token)
            else:
                direction, speed, temp, lv = _parse_wind_group(token)

            winds.append({
                "altitude_ft": alt,
                "wind_direction": direction,
                "wind_speed_kt": speed,
                "temperature_c": temp,
                "light_and_variable": lv,
                "raw": token,
            })
        else:
            # No data at this altitude
            winds.append({
                "altitude_ft": alt,
                "wind_direction": None,
                "wind_speed_kt": None,
                "temperature_c": None,
                "light_and_variable": False,
                "raw": "",
            })

    return {"station": station, "winds": winds}


def _find_valid_time(text: str) -> Optional[str]:
    """Extract the VALID time from the header, e.g. 'VALID 130000Z'."""
    m = re.search(r'VALID\s+(\d{6}Z)', text)
    return m.group(1) if m else None


async def fetch_winds_aloft(
    station: str,
    forecast: int = 12,
    level: str = "low",
) -> Dict:
    """Fetch FB winds for a specific station.

    Args:
        station: 3-letter FB winds station ID
        forecast: Forecast period — 6, 12, or 24
        level: "low" (3K-39K) or "high" (6K-45K)

    Returns dict ready for WindsAloftResponse.
    """
    fcst = str(forecast).zfill(2)
    params = {"region": "all", "level": level, "fcst": fcst}

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(WINDS_URL, params=params)
        resp.raise_for_status()

    text = resp.text
    valid_time = _find_valid_time(text)
    altitudes = LOW_ALTITUDES if level == "low" else HIGH_ALTITUDES

    station_upper = station.upper().strip()
    station_data = None
    raw_line = None

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        parts = stripped.split()
        if parts and parts[0] == station_upper:
            station_data = _parse_station_line(stripped, altitudes)
            raw_line = stripped
            break

    if not station_data:
        return None

    return {
        "station": station_upper,
        "forecast_hour": forecast,
        "level": level,
        "valid_time": valid_time,
        "winds": station_data["winds"],
        "raw_text": raw_line,
    }


def get_station_for_icao(icao: str) -> Optional[str]:
    """Public helper: resolve ICAO → FB winds station ID, or None."""
    return _icao_to_station(icao)

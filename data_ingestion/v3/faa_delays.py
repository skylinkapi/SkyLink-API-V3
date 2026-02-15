"""
Fetch and parse FAA NAS (National Airspace System) delay information.

Source: https://nasstatus.faa.gov/api/airport-status-information
Free, no authentication required. Returns XML.
"""

import logging
from typing import Any, Dict, List
from xml.etree import ElementTree

import httpx

logger = logging.getLogger(__name__)

FAA_NAS_URL = "https://nasstatus.faa.gov/api/airport-status-information"

# Map common FAA 3-letter IDs to ICAO codes for matching
_FAA_TO_ICAO = {
    "EWR": "KEWR", "JFK": "KJFK", "LGA": "KLGA", "SFO": "KSFO",
    "LAX": "KLAX", "ORD": "KORD", "ATL": "KATL", "DFW": "KDFW",
    "DEN": "KDEN", "IAH": "KIAH", "MIA": "KMIA", "BOS": "KBOS",
    "SEA": "KSEA", "MSP": "KMSP", "DTW": "KDTW", "PHL": "KPHL",
    "CLT": "KCLT", "PHX": "KPHX", "IAD": "KIAD", "DCA": "KDCA",
    "FLL": "KFLL", "MCO": "KMCO", "SLC": "KSLC", "BWI": "KBWI",
    "TPA": "KTPA", "SAN": "KSAN", "HNL": "PHNL", "STL": "KSTL",
    "MDW": "KMDW", "BNA": "KBNA", "OAK": "KOAK", "SJC": "KSJC",
    "AUS": "KAUS", "RDU": "KRDU", "CLE": "KCLE", "MKE": "KMKE",
    "SAT": "KSAT", "PDX": "KPDX", "PIT": "KPIT", "IND": "KIND",
    "CVG": "KCVG", "CMH": "KCMH", "MCI": "KMCI", "JAX": "KJAX",
    "SNA": "KSNA", "ABQ": "KABQ", "BUF": "KBUF", "OMA": "KOMA",
    # US Territories — Virgin Islands (TI), Puerto Rico (TJ)
    "STX": "TISX", "STT": "TIST", "SJU": "TJSJ", "BQN": "TJBQ",
    "PSE": "TJPS", "MAZ": "TJMZ", "VQS": "TJVQ",
    # Alaska (PA)
    "ANC": "PANC", "FAI": "PAFA", "JNU": "PAJN", "SIT": "PASI",
    "KTN": "PAKT", "ADQ": "PADQ", "BET": "PABE", "OME": "PAOM",
    "BRW": "PABR", "CDV": "PACV", "YAK": "PAYA", "DLG": "PADL",
    # Hawaii (PH)
    "HNL": "PHNL", "OGG": "PHOG", "LIH": "PHLI", "KOA": "PHKO",
    "ITO": "PHTO",
    # Pacific (PG/PK)
    "GUM": "PGUM", "SPN": "PGSN",
}

def _normalize_airport(code: str) -> str:
    """Return ICAO code from whatever the FAA feed gives us."""
    code = code.strip().upper()
    if len(code) == 4:
        return code
    if len(code) == 3:
        return _FAA_TO_ICAO.get(code, f"K{code}")
    return code


def _text(el: Any, tag: str) -> str:
    """Safely extract text from a child element."""
    child = el.find(tag)
    return child.text.strip() if child is not None and child.text else ""


def _parse_ground_delays(root: ElementTree.Element) -> List[Dict]:
    delays = []
    for gd_list in root.iter("Ground_Delay_List"):
        for gd in gd_list.findall("Ground_Delay"):
            delays.append({
                "airport": _normalize_airport(_text(gd, "ARPT")),
                "airport_name": None,
                "reason": _text(gd, "Reason"),
                "avg_delay": _text(gd, "Avg") or None,
                "max_delay": _text(gd, "Max") or None,
            })
    return delays


def _parse_ground_stops(root: ElementTree.Element) -> List[Dict]:
    stops = []
    for gs_list in root.iter("Ground_Stop_List"):
        for gs in gs_list.findall("Program"):
            stops.append({
                "airport": _normalize_airport(_text(gs, "ARPT")),
                "airport_name": None,
                "reason": _text(gs, "Reason"),
                "end_time": _text(gs, "End_Time") or None,
            })
    # Also check for direct Ground_Stop elements
    for gs_list in root.iter("Ground_Stop_List"):
        for gs in gs_list.findall("Ground_Stop"):
            stops.append({
                "airport": _normalize_airport(_text(gs, "ARPT")),
                "airport_name": None,
                "reason": _text(gs, "Reason"),
                "end_time": _text(gs, "End_Time") or None,
            })
    return stops


def _parse_closures(root: ElementTree.Element) -> List[Dict]:
    closures = []
    for cl_list in root.iter("Airport_Closure_List"):
        for apt in cl_list.findall("Airport"):
            closures.append({
                "airport": _normalize_airport(_text(apt, "ARPT")),
                "airport_name": None,
                "reason": _text(apt, "Reason"),
                "begin": _text(apt, "Start") or None,
                "reopen": _text(apt, "Reopen") or None,
            })
    return closures


def _parse_airspace_flow_programs(root: ElementTree.Element) -> List[Dict]:
    programs = []
    for af_list in root.iter("Airspace_Flow_List"):
        for af in af_list.findall("Airspace_Flow"):
            programs.append({
                "facility": _text(af, "CTL_Element"),
                "reason": _text(af, "Reason"),
                "fca_start": _text(af, "FCA_StartDateTime") or _text(af, "AFP_StartTime") or None,
                "fca_end": _text(af, "FCA_EndDateTime") or _text(af, "AFP_EndTime") or None,
            })
    return programs


async def fetch_faa_delays() -> Dict:
    """Fetch and parse all FAA NAS delay information.

    Returns a dict ready to be used with FAADelayResponse.
    """
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(FAA_NAS_URL, headers={"Accept": "application/xml"})
        resp.raise_for_status()

    root = ElementTree.fromstring(resp.text)

    ground_delays = _parse_ground_delays(root)
    ground_stops = _parse_ground_stops(root)
    closures = _parse_closures(root)
    airspace_fps = _parse_airspace_flow_programs(root)

    total = len(ground_delays) + len(ground_stops) + len(closures) + len(airspace_fps)

    return {
        "ground_delays": ground_delays,
        "ground_stops": ground_stops,
        "closures": closures,
        "airspace_flow_programs": airspace_fps,
        "total_alerts": total,
        "message": None if total > 0 else "No active FAA delays or advisories at this time",
    }

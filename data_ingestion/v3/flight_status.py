"""
v3 Flight status data ingestion from avionio.com.

Supports both IATA (BA123) and ICAO (BAW123) flight number formats.
ICAO codes are converted to IATA via the flight parser service before
querying avionio.

Optimised: uses async httpx instead of blocking urllib3 (no thread pool
needed), reuses a single httpx client across requests.
"""

import re
import logging
from typing import Optional

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

# Reusable async client with connection pooling and retries
_transport = httpx.AsyncHTTPTransport(retries=3)
_client: Optional[httpx.AsyncClient] = None


async def _get_client() -> httpx.AsyncClient:
    """Return a reusable async client."""
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            transport=_transport,
            timeout=httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=10.0),
            headers=_HEADERS,
            follow_redirects=True,
        )
    return _client


def _format_for_avionio(iata_code: str, flight_num: str) -> str:
    """Build the avionio URL slug: ``iata-number`` (lowercase)."""
    return f"{iata_code.lower()}-{flight_num}"


async def _scrape_flight(flight_code: str) -> dict:
    """
    Scrape flight status from avionio.com (async).

    *flight_code* must already be in avionio format (e.g. ``ba-123``).
    """
    url = f"https://www.avionio.com/en/flight/{flight_code}"

    try:
        client = await _get_client()
        response = await client.get(url)
        if response.status_code != 200:
            return {"error": f"HTTP {response.status_code}: Flight not found or site unavailable."}
        html = response.text
        soup = BeautifulSoup(html, "html.parser")
    except httpx.ConnectError as e:
        return {"error": f"Connection failed: {e}"}
    except httpx.TimeoutException as e:
        return {"error": f"Request timed out: {e}"}
    except Exception as e:
        return {"error": f"Unexpected error: {e}"}

    result = {}
    try:
        flight_div = soup.find("div", id="flight")
        if not flight_div:
            return {"error": "Flight information not found."}

        # Flight number
        flight_num_el = flight_div.find("h2", class_="h3 no-margin")
        result["flight_number"] = flight_num_el.text.strip() if flight_num_el else flight_code

        # Status
        status_p = flight_div.find(
            "p", class_=lambda x: x and "sc" in x and "sbg" in x
        )
        result["status"] = status_p.text.strip() if status_p else "Unknown"

        # Airline
        airline = "Unknown"
        first_card = flight_div.find("div", class_="card card-section")
        if first_card:
            airline_p = first_card.find_all("p")
            if airline_p:
                airline = airline_p[-1].text.strip()
        result["airline"] = airline

        # Departure / Arrival details
        details = flight_div.find_all("div", class_="card details")
        departure, arrival = {}, {}

        if len(details) >= 1:
            departure = _parse_leg(details[0], leg_type="departure")
        if len(details) >= 2:
            arrival = _parse_leg(details[1], leg_type="arrival")

        result["departure"] = departure
        result["arrival"] = arrival

    except Exception as e:
        result = {"error": str(e)}

    return result


def _parse_leg(card, leg_type: str = "departure") -> dict:
    """Parse a departure or arrival card from the flight page."""
    header = card.find("div", class_="card-section card-header")
    airport = header.find("h2", class_="h1").text.strip() if header else ""
    airport_full = header.find_all("p")[-1].text.strip() if header and header.find_all("p") else ""

    body = card.find("div", class_="card-body")
    sections = body.find_all("div", class_="card-section") if body else []
    sched_section = sections[0] if len(sections) > 0 else None
    extra_section = sections[1] if len(sections) > 1 else None

    sched_time = sched_section.find("p", class_="h1 no-margin").text.strip() if sched_section else ""
    sched_date = sched_section.find_all("p")[-1].text.strip() if sched_section else ""
    extra_time = extra_section.find("p", class_="h1 no-margin").text.strip() if extra_section else ""
    extra_date = extra_section.find_all("p")[-1].text.strip() if extra_section else ""

    footer = card.find("div", class_="card-section card-footer")
    footer_divs = footer.find_all("div") if footer else []
    col1 = footer_divs[0].find("p", class_="h1 no-margin").text.strip() if len(footer_divs) > 0 else ""
    col2 = footer_divs[1].find("p", class_="h1 no-margin").text.strip() if len(footer_divs) > 1 else ""
    col3 = footer_divs[2].find("p", class_="h1 no-margin").text.strip() if len(footer_divs) > 2 else ""

    if leg_type == "departure":
        return {
            "airport": airport,
            "airport_full": airport_full,
            "scheduled_time": sched_time,
            "scheduled_date": sched_date,
            "actual_time": extra_time,
            "actual_date": extra_date,
            "terminal": col1,
            "gate": col2,
            "checkin": col3,
        }
    else:
        return {
            "airport": airport,
            "airport_full": airport_full,
            "scheduled_time": sched_time,
            "scheduled_date": sched_date,
            "estimated_time": extra_time,
            "estimated_date": extra_date,
            "terminal": col1,
            "gate": col2,
            "baggage": col3,
        }


def _parse_flight_number(flight_number: str) -> str:
    """Parse a flight number into avionio's ``iata-number`` format."""
    if not flight_number:
        return flight_number
    s = re.sub(r"[^A-Za-z0-9]", "", flight_number).lower()
    if len(s) < 3:
        return s
    iata = s[:2]
    num = s[2:]
    if num.isdigit():
        return f"{iata}-{num}"
    match = re.match(r"([a-zA-Z]+)(\d+)", flight_number)
    if match:
        return f"{match.group(1).lower()}-{match.group(2)}"
    return s


async def get_flight_status_v3(flight_number: str) -> dict:
    """
    Async v3 entry point with ICAO->IATA conversion.

    Tries the parsed IATA format first; if the input was an ICAO code
    (3-letter prefix), it converts via the airline database and tries that
    format as well.
    """
    from services.v3.flight_parser import flight_parser_service

    try:
        parsed = await flight_parser_service.parse(flight_number)
    except ValueError:
        # Fallback to legacy parsing if the parser can't handle it
        flight_code = _parse_flight_number(flight_number)
        return await _scrape_flight(flight_code)

    # Build ordered list of formats to try
    formats_to_try = []

    # If we have an IATA code, try that first (avionio prefers IATA)
    if parsed.iata_code:
        formats_to_try.append(
            _format_for_avionio(parsed.iata_code, parsed.flight_number)
        )

    # Also try the raw airline code if it's different from IATA
    if parsed.airline_code != parsed.iata_code:
        formats_to_try.append(
            _format_for_avionio(parsed.airline_code, parsed.flight_number)
        )

    # Try each format until one works
    result = {"error": "Flight not found"}
    for fmt in formats_to_try:
        result = await _scrape_flight(fmt)
        if isinstance(result, dict) and "error" not in result:
            # Enrich with parsed data
            if parsed.airline_name and result.get("airline") == "Unknown":
                result["airline"] = parsed.airline_name
            return result

    # All formats failed — return last error
    return result

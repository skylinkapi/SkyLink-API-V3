"""
v3 Schedule data ingestion from avionio.com widget.

Uses the avionio widget (style=2) which returns a clean HTML table.
Supports pagination to fetch up to 12 hours of flights and optional
timestamp parameter for historical / future schedules.

Optimised: reuses a single httpx.AsyncClient across requests.
"""

import logging
import re
from typing import Optional
from datetime import datetime

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE_URL = "https://www.avionio.com/widget/en/{iata}/{direction}"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

# Maximum number of pages to fetch (safety limit)
MAX_PAGES = 8
# Target hours of schedule data to fetch
TARGET_HOURS = 12

# Reusable client
_client: Optional[httpx.AsyncClient] = None


async def _get_client() -> httpx.AsyncClient:
    """Return a reusable async client."""
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=30.0,
            headers=_HEADERS,
            follow_redirects=True,
        )
    return _client


def _parse_datetime_from_row(time_str: str, date_str: str) -> Optional[datetime]:
    """Try to parse a datetime from the table's Time and Date columns."""
    try:
        combined = f"{time_str.strip()} {date_str.strip()} {datetime.now().year}"
        return datetime.strptime(combined, "%H:%M %d %b %Y")
    except (ValueError, AttributeError):
        return None


def _extract_next_page_url(soup: BeautifulSoup, direction: str) -> Optional[str]:
    """Extract the 'next flights' pagination URL from the page."""
    for a_tag in soup.find_all("a", href=True):
        href = a_tag.get("href", "")
        text = a_tag.get_text(strip=True).lower()
        classes = a_tag.get("class", [])

        is_next = (
            "next-flights" in classes
            or "next" in text
            or "prossimi" in text
            or "próximos" in text
            or "nächste" in text
        )

        if is_next and direction in href:
            if href.startswith("/"):
                return f"https://www.avionio.com{href}"
            return href

    return None


def _parse_table(soup: BeautifulSoup) -> list[dict]:
    """Parse the schedule table from the HTML."""
    table = soup.find("table")
    if not table:
        return []

    headers = [th.get_text(strip=True) for th in table.find_all("th")]
    if not headers:
        return []

    flights = []
    for row in table.find_all("tr")[1:]:
        cells = []
        for i, td in enumerate(row.find_all("td")):
            # Remove codeshare count spans/links
            for span in td.find_all("span"):
                cls = span.get("class", [])
                title = span.get("title", "")
                if any("count" in c.lower() for c in cls):
                    span.decompose()
                elif "codeshare" in title.lower():
                    span.decompose()
                elif span.text.strip().isdigit():
                    span.decompose()

            for a_tag in td.find_all("a"):
                cls = a_tag.get("class", [])
                title = a_tag.get("title", "")
                if any("count" in c.lower() for c in cls):
                    a_tag.decompose()
                elif "codeshare" in title.lower():
                    a_tag.decompose()
                elif a_tag.text.strip().isdigit():
                    a_tag.decompose()

            cell_text = td.get_text(strip=True)

            # Fix truncated status values like "Estimated 15:" -> need full time
            if i < len(headers) and headers[i].lower() == "status":
                truncated = re.match(
                    r"^(Estimated|Departed|Delayed|Landed)\s+(\d{1,2}):$",
                    cell_text,
                )
                if truncated:
                    title_attr = td.get("title", "")
                    if title_attr:
                        cell_text = title_attr.strip()
                    else:
                        cell_text = f"{truncated.group(1)} {truncated.group(2)}:00"

            # Only strip trailing digits from non-essential columns
            if i < len(headers):
                header = headers[i].lower()
                if not any(kw in header for kw in [
                    "flight", "airline", "aircraft", "time", "gate",
                    "terminal", "status", "date",
                ]):
                    cell_text = re.sub(r"\d+$", "", cell_text).strip()

            cells.append(cell_text)

        if cells and len(cells) == len(headers):
            row_dict = dict(zip(headers, cells))
            time_val = row_dict.get("Time", "")
            if time_val.lower() in ("previous flights", "next flights", ""):
                continue
            flights.append(row_dict)

    return flights


async def fetch_schedule(
    iata: str,
    direction: str = "departures",
    ts: Optional[int] = None,
    hours: int = TARGET_HOURS,
):
    """
    Fetch schedule data with pagination.

    Args:
        iata: 3-letter IATA airport code.
        direction: "departures" or "arrivals".
        ts: Optional Unix timestamp in milliseconds for a specific date/time.
        hours: Target hours of schedule data to fetch (default 12).

    Returns:
        dict with keys: iata, direction, flights, total_flights, pages_fetched.
    """
    iata_lower = iata.strip().lower()

    url = BASE_URL.format(iata=iata_lower, direction=direction)
    params = {"style": "2"}
    if ts:
        params["ts"] = str(ts)

    all_flights = []
    pages_fetched = 0
    first_flight_time = None

    try:
        client = await _get_client()

        for page_num in range(MAX_PAGES):
            logger.debug("Fetching schedule page %d: %s", page_num, url)

            resp = await client.get(url, params=params if page_num == 0 else None)

            if resp.status_code == 404:
                if page_num == 0:
                    return {"error": "Schedule data not available for this airport"}
                break

            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            pages_fetched += 1

            flights = _parse_table(soup)
            if not flights:
                break

            all_flights.extend(flights)

            # Track time range to know when we have enough hours
            if first_flight_time is None and flights:
                first_flight_time = _parse_datetime_from_row(
                    flights[0].get("Time", ""),
                    flights[0].get("Date", ""),
                )

            if first_flight_time and flights:
                last_time = _parse_datetime_from_row(
                    flights[-1].get("Time", ""),
                    flights[-1].get("Date", ""),
                )
                if last_time and first_flight_time:
                    span_hours = (last_time - first_flight_time).total_seconds() / 3600
                    if span_hours >= hours:
                        break

            next_url = _extract_next_page_url(soup, direction)
            if not next_url:
                break

            url = next_url
            params = None

    except httpx.HTTPStatusError as e:
        logger.error("HTTP error fetching schedule for %s: %s", iata, e.response.status_code)
        if not all_flights:
            return {"error": "Schedule data not available for this airport"}
    except httpx.RequestError as e:
        logger.error("Request error fetching schedule for %s: %s", iata, e)
        if not all_flights:
            return {"error": "Unable to fetch schedule data at this time"}
    except Exception as e:
        logger.error("Unexpected error fetching schedule for %s: %s", iata, e)
        if not all_flights:
            return {"error": "Unable to fetch schedule data at this time"}

    logger.info(
        "Fetched %d flights for %s (%s) across %d pages",
        len(all_flights), iata, direction, pages_fetched,
    )

    return {
        "iata": iata.upper(),
        "direction": direction,
        "flights": all_flights,
        "total_flights": len(all_flights),
        "pages_fetched": pages_fetched,
    }

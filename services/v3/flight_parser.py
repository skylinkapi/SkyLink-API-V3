"""
Enhanced Flight Number Parsing service.

Parses flight numbers in IATA (BA123), ICAO (BAW123), and mixed formats,
performs bidirectional IATA <-> ICAO conversion using the OpenFlights
airlines database, and enriches with airline metadata.

Optimised: builds O(1) dict lookups on first load instead of per-request
DataFrame filtering.
"""

import re
import logging
from typing import Optional, Dict, Any

import pandas as pd

from data_ingestion.remote_data import get_airlines
from models.v3.flight_number import ParsedFlightNumber

logger = logging.getLogger(__name__)


def _clean(val) -> Optional[str]:
    """Clean a raw value from the airlines DataFrame."""
    if val is None or pd.isna(val) or str(val).strip() in ("\\N", "", "NULL"):
        return None
    return str(val).strip()


class FlightParserService:
    """Parse and normalise flight numbers between IATA and ICAO formats."""

    def __init__(self):
        self._loaded = False
        self._iata_lookup: Dict[str, Dict[str, Any]] = {}
        self._icao_lookup: Dict[str, Dict[str, Any]] = {}

    async def _ensure_loaded(self):
        """Load airlines data once and build O(1) lookup dicts."""
        if self._loaded:
            return

        df = await get_airlines()
        if list(df.columns) == list(range(len(df.columns))):
            df.columns = [
                "id", "name", "alias", "iata", "icao",
                "callsign", "country", "active",
            ]

        iata_lookup: Dict[str, Dict[str, Any]] = {}
        icao_lookup: Dict[str, Dict[str, Any]] = {}

        for record in df.to_dict("records"):
            name = _clean(record.get("name"))
            iata_code = _clean(record.get("iata"))
            icao_code = _clean(record.get("icao"))
            callsign = _clean(record.get("callsign"))
            country = _clean(record.get("country"))
            is_active = str(record.get("active", "")).strip().upper() == "Y"

            info = {
                "name": name,
                "iata": iata_code,
                "icao": icao_code,
                "callsign": callsign,
                "country": country,
            }

            if iata_code:
                key = iata_code.upper()
                # Active airlines take priority
                if key not in iata_lookup or is_active:
                    iata_lookup[key] = info

            if icao_code:
                key = icao_code.upper()
                if key not in icao_lookup or is_active:
                    icao_lookup[key] = info

        self._iata_lookup = iata_lookup
        self._icao_lookup = icao_lookup
        self._loaded = True

    async def _lookup_by_iata(self, iata: str) -> Optional[Dict[str, Any]]:
        await self._ensure_loaded()
        return self._iata_lookup.get(iata.upper())

    async def _lookup_by_icao(self, icao: str) -> Optional[Dict[str, Any]]:
        await self._ensure_loaded()
        return self._icao_lookup.get(icao.upper())

    # ── parsing ──────────────────────────────────────────────────────

    async def parse(self, flight_number: str) -> ParsedFlightNumber:
        """
        Parse a flight number string and enrich with airline data.

        Supports formats:
        - IATA:  BA123, AA1234
        - ICAO:  BAW123, AAL1234
        - Dirty: ba-123, RYR 5733, BA 123
        """
        original = flight_number
        cleaned = re.sub(r"[^A-Za-z0-9]", "", flight_number).upper()

        if not cleaned:
            raise ValueError(f"Invalid flight number: {flight_number}")

        match = re.match(r"^([A-Z]{2,3})(\d{1,5})$", cleaned)
        if not match:
            raise ValueError(
                f"Cannot parse flight number '{flight_number}'. "
                "Expected format: 2-letter IATA (BA123) or 3-letter ICAO (BAW123)."
            )

        airline_code, num = match.groups()
        airline_info: Optional[Dict[str, Any]] = None
        iata_code: Optional[str] = None
        icao_code: Optional[str] = None

        if len(airline_code) == 2:
            iata_code = airline_code
            airline_info = await self._lookup_by_iata(iata_code)
            if airline_info and airline_info.get("icao"):
                icao_code = airline_info["icao"]
        else:
            icao_code = airline_code
            airline_info = await self._lookup_by_icao(icao_code)
            if airline_info and airline_info.get("iata"):
                iata_code = airline_info["iata"]

        return ParsedFlightNumber(
            original=original,
            airline_code=airline_code,
            flight_number=num,
            iata_code=iata_code,
            icao_code=icao_code,
            iata_format=f"{iata_code}{num}" if iata_code else None,
            icao_format=f"{icao_code}{num}" if icao_code else None,
            airline_name=airline_info["name"] if airline_info else None,
            callsign=airline_info.get("callsign") if airline_info else None,
            country=airline_info.get("country") if airline_info else None,
        )


# Global singleton
flight_parser_service = FlightParserService()

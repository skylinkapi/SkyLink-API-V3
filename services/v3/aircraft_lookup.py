"""
Aircraft Registration Lookup service (v3).

Wraps the existing AircraftDatabaseService to provide async-friendly lookups
by registration number or ICAO24 hex address, and fetches aircraft
thumbnail photos from airport-data.com.

Optimised: reuses a single httpx.AsyncClient for photo fetches instead of
creating one per request.
"""

import re
import logging
from typing import Optional, List

import httpx

from services.aircraft_db_service import get_aircraft_db_service
from models.v3.aircraft import AircraftDetails, AircraftPhoto

logger = logging.getLogger(__name__)

PHOTO_API_URL = "https://airport-data.com/api/ac_thumb.json"
PHOTO_MAX_RESULTS = 5


def _link_to_full_image(link: str) -> str:
    """
    Convert an airport-data.com photo page link to a full-size image URL.

    ``https://airport-data.com/aircraft/photo/001912010.html``
    ->  ``https://image.airport-data.com/aircraft/001912010.jpg``
    """
    photo_id = link.rstrip("/").split("/")[-1].replace(".html", "")
    return f"https://image.airport-data.com/aircraft/{photo_id}.jpg"


class AircraftLookupService:
    """Look up aircraft details by registration or ICAO24 hex code."""

    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Return a reusable httpx client for photo fetches."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=10.0)
        return self._client

    @staticmethod
    def _normalize_registration(reg: str) -> str:
        """Normalise a registration: strip dashes/spaces, uppercase."""
        return re.sub(r"[^A-Z0-9]", "", reg.upper())

    def _build_details(self, raw: dict) -> AircraftDetails:
        """Map raw database record to AircraftDetails model (without photos)."""

        def _clean(val):
            if val is None or (isinstance(val, str) and val.strip().upper() in ("", "NULL")):
                return None
            if isinstance(val, str):
                return val.strip()
            return val

        type_name = _clean(raw.get("model")) or _clean(raw.get("short_type"))
        manufacturer = _clean(raw.get("manufacturer"))
        icao_type = _clean(raw.get("icaotype"))

        return AircraftDetails(
            registration=_clean(raw.get("reg")),
            icao24=_clean(raw.get("icao")),
            icao_type=icao_type,
            type_name=type_name,
            manufacturer=manufacturer,
            owner_operator=_clean(raw.get("ownop")),
            is_military=bool(raw.get("mil")),
            year_built=_clean(str(raw["year"])) if raw.get("year") and raw["year"] != "NULL" else None,
        )

    # ── photo fetching ───────────────────────────────────────────────

    async def _fetch_photos(
        self,
        icao24: Optional[str] = None,
        registration: Optional[str] = None,
    ) -> List[AircraftPhoto]:
        """Fetch aircraft thumbnail photos from airport-data.com."""
        params = {"n": str(PHOTO_MAX_RESULTS)}

        if icao24:
            params["m"] = icao24.upper()
        if registration:
            params["r"] = registration

        if not params.get("m") and not params.get("r"):
            return []

        try:
            client = await self._get_client()
            resp = await client.get(PHOTO_API_URL, params=params)
            if resp.status_code != 200:
                return []
            data = resp.json()
        except Exception as exc:
            logger.debug("airport-data.com photo fetch failed: %s", exc)
            return []

        if data.get("status") != 200 or "data" not in data:
            return []

        photos = []
        for item in data["data"]:
            try:
                link = item["link"]
                photos.append(AircraftPhoto(
                    image=_link_to_full_image(link),
                    link=link,
                    photographer=item.get("photographer", "Unknown"),
                ))
            except (KeyError, TypeError):
                continue

        return photos

    # ── public lookup methods ────────────────────────────────────────

    async def lookup_by_registration(
        self, registration: str, include_photos: bool = True
    ) -> Optional[AircraftDetails]:
        """Look up an aircraft by its registration / tail number."""
        db = get_aircraft_db_service()
        original = registration.upper().strip()
        raw = db.get_aircraft_by_registration(original)
        if not raw:
            normalized = self._normalize_registration(registration)
            raw = db.get_aircraft_by_registration(normalized)
        if not raw:
            return None
        details = self._build_details(raw)
        if include_photos:
            details.photos = await self._fetch_photos(
                icao24=details.icao24,
                registration=details.registration,
            )
        return details

    async def lookup_by_icao24(
        self, icao24: str, include_photos: bool = True
    ) -> Optional[AircraftDetails]:
        """Look up an aircraft by its ICAO 24-bit hex address."""
        db = get_aircraft_db_service()
        raw = db.get_aircraft_by_icao24(icao24.upper().strip())
        if not raw:
            return None
        details = self._build_details(raw)
        if include_photos:
            details.photos = await self._fetch_photos(
                icao24=details.icao24,
                registration=details.registration,
            )
        return details


# Global singleton
aircraft_lookup_service = AircraftLookupService()

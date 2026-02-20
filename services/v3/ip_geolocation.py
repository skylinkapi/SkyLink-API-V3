"""
In-house IP geolocation service (v3).

Uses the DB-IP City Lite database (CC BY 4.0, free for commercial use, no API key).
Database is stored locally and refreshed monthly — zero external API calls at request time.

Database path: data/ip-geolocation.mmdb
Download source: https://download.db-ip.com/free/dbip-city-lite-{YYYY}-{MM}.mmdb.gz
"""

import gzip
import os
import time
import logging
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any

import httpx

logger = logging.getLogger(__name__)

# ── paths ─────────────────────────────────────────────────────────────────────

_PROJECT_ROOT = Path(__file__).parent.parent.parent
_DB_DIR = _PROJECT_ROOT / "data"
_DB_PATH = _DB_DIR / "ip-geolocation.mmdb"

# DB-IP Lite: CC BY 4.0, free for commercial use, no registration required
_DB_URL_TEMPLATE = (
    "https://download.db-ip.com/free/dbip-city-lite-{year}-{month:02d}.mmdb.gz"
)

# Refresh interval — DB-IP publishes monthly updates
_REFRESH_INTERVAL = 30 * 24 * 3600  # 30 days in seconds


class IPGeolocationService:
    """
    Local IP → (lat, lon, city, country …) resolver backed by DB-IP Lite MMDB.

    On first use the database is downloaded automatically (~40 MB compressed).
    Subsequent calls use an in-process Reader with no network I/O.
    """

    def __init__(self):
        self._reader = None          # geoip2.database.Reader, opened lazily
        self._loaded_at: float = 0.0
        self._lock = asyncio.Lock()  # serialise download + open

    # ── private helpers ───────────────────────────────────────────────────────

    def _open_reader(self):
        """Open (or re-open) the MMDB reader."""
        import geoip2.database  # lazy import so startup isn't affected if not installed

        if self._reader is not None:
            try:
                self._reader.close()
            except Exception:
                pass

        self._reader = geoip2.database.Reader(str(_DB_PATH))
        self._loaded_at = time.time()
        logger.info("IP geolocation database loaded from %s", _DB_PATH)

    async def _download_db(self):
        """Download the current DB-IP City Lite MMDB and decompress it."""
        _DB_DIR.mkdir(parents=True, exist_ok=True)

        now = datetime.now(timezone.utc)
        url = _DB_URL_TEMPLATE.format(year=now.year, month=now.month)
        logger.info("Downloading IP geolocation database from %s ...", url)

        tmp_gz = _DB_PATH.with_suffix(".mmdb.gz.tmp")

        async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
            async with client.stream("GET", url) as resp:
                resp.raise_for_status()
                with open(tmp_gz, "wb") as fh:
                    async for chunk in resp.aiter_bytes(65536):
                        fh.write(chunk)

        logger.info("Decompressing IP geolocation database ...")
        with gzip.open(tmp_gz, "rb") as gz_in, open(_DB_PATH, "wb") as out:
            while True:
                chunk = gz_in.read(65536)
                if not chunk:
                    break
                out.write(chunk)

        tmp_gz.unlink(missing_ok=True)
        logger.info("IP geolocation database ready at %s", _DB_PATH)

    async def _ensure_ready(self):
        """Guarantee the reader is open and the database is not stale."""
        async with self._lock:
            now = time.time()

            # Already loaded and fresh enough → nothing to do
            if self._reader is not None and (now - self._loaded_at) < _REFRESH_INTERVAL:
                return

            # Existing file on disk — check its age
            if _DB_PATH.exists():
                age = now - _DB_PATH.stat().st_mtime
                if age < _REFRESH_INTERVAL:
                    # File is fresh; just (re-)open the reader
                    self._open_reader()
                    return

            # Need a fresh download
            try:
                await self._download_db()
                self._open_reader()
            except Exception as exc:
                logger.error("Failed to download IP geolocation database: %s", exc)
                # Fall back to a stale file rather than failing completely
                if _DB_PATH.exists():
                    logger.warning("Using stale IP geolocation database as fallback")
                    self._open_reader()
                else:
                    raise RuntimeError(
                        "IP geolocation database is unavailable. "
                        "Check network connectivity."
                    ) from exc

    # ── public API ────────────────────────────────────────────────────────────

    async def geolocate(self, ip: str) -> Dict[str, Any]:
        """
        Return geolocation data for *ip*.

        Returns a dict with keys matching the legacy ip-api.com shape so
        callers need no changes:
            lat, lon, city, regionName, country, countryCode, zip, timezone
        """
        await self._ensure_ready()

        import geoip2.errors  # lazy import

        try:
            record = self._reader.city(ip)
        except geoip2.errors.AddressNotFoundError:
            raise ValueError(f"IP address {ip!r} not found in geolocation database")

        subdivision = (
            record.subdivisions.most_specific.name
            if record.subdivisions
            else None
        )

        return {
            "lat": record.location.latitude,
            "lon": record.location.longitude,
            "city": record.city.name,
            "regionName": subdivision,
            "country": record.country.name,
            "countryCode": record.country.iso_code,
            "zip": record.postal.code,
            "timezone": record.location.time_zone,
        }

    async def close(self):
        """Release the MMDB file handle."""
        if self._reader is not None:
            try:
                self._reader.close()
            except Exception:
                pass
            self._reader = None


# Global singleton — shared across all requests
ip_geolocation_service = IPGeolocationService()

"""
Airport Search service (v3).

Provides location-based, IP-based, and free-text airport search over the
OurAirports dataset (~74 K airports).  Data is fetched once and cached
in memory for 1 hour to avoid re-downloading on every request.

Text search uses a pre-built lowercase index for fast matching.

IP geolocation uses a local DB-IP Lite MMDB database (no external API calls).
"""

import math
import time
import logging
from typing import Optional, List, Dict, Any, Tuple

import pandas as pd

from services.airport_service import airport_service
from services.v3.ip_geolocation import ip_geolocation_service
from utils.adsb_utils import haversine_distance

logger = logging.getLogger(__name__)

# 1-hour cache TTL (seconds)
_CACHE_TTL = 3600


class AirportSearchService:

    def __init__(self):
        self._df: Optional[pd.DataFrame] = None
        self._cache_ts: float = 0.0
        # Pre-built search index (populated on first load)
        self._index: Optional[List[Dict[str, Any]]] = None

    # ── data loading & caching ────────────────────────────────────────

    async def _get_airports(self) -> pd.DataFrame:
        """Return cached airport DataFrame, refreshing if stale."""
        now = time.time()
        if self._df is not None and (now - self._cache_ts) < _CACHE_TTL:
            return self._df
        logger.info("Loading airports.csv from OurAirports...")
        df = await airport_service.fetch_data("airports.csv")
        self._df = df
        self._cache_ts = now
        self._index = None  # rebuild index on next text search
        return df

    def _build_index(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Build a lightweight search index from the DataFrame.

        Each entry holds the lowercase versions of searchable fields so
        we don't have to call ``.lower()`` on 74 K rows per request.
        Uses to_dict("records") to avoid named-tuple field conflicts.
        """
        index = []
        for record in df.to_dict("records"):
            row_id = record.get("id")
            ident = str(record.get("ident") or "")
            iata = str(record.get("iata_code") or "")
            name = str(record.get("name") or "")
            municipality = str(record.get("municipality") or "")
            iso_country = str(record.get("iso_country") or "")
            keywords = str(record.get("keywords") or "")
            ap_type = str(record.get("type") or "")

            lat = record.get("latitude_deg")
            lon = record.get("longitude_deg")

            # Size bonus for ranking
            if ap_type == "large_airport":
                size_bonus = 10
            elif ap_type == "medium_airport":
                size_bonus = 5
            else:
                size_bonus = 0

            # Clean NaN strings
            iata_clean = iata if iata and iata != "nan" else ""
            municipality_clean = municipality if municipality != "nan" else ""
            iso_country_clean = iso_country if iso_country != "nan" else ""
            keywords_clean = keywords if keywords != "nan" else ""

            index.append({
                # original values
                "id": None if pd.isna(row_id) else int(row_id),
                "ident": ident,
                "iata_code": iata_clean,
                "name": name,
                "municipality": municipality_clean,
                "iso_country": iso_country_clean,
                "keywords": keywords_clean,
                "type": ap_type,
                "lat": None if pd.isna(lat) else float(lat),
                "lon": None if pd.isna(lon) else float(lon),
                "size_bonus": size_bonus,
                # lowercase for matching
                "l_ident": ident.lower(),
                "l_iata": iata_clean.lower(),
                "l_name": name.lower(),
                "l_municipality": municipality_clean.lower(),
                "l_country": iso_country_clean.lower(),
                "l_keywords": keywords_clean.lower(),
            })
        return index

    async def _get_index(self) -> List[Dict[str, Any]]:
        df = await self._get_airports()
        if self._index is None:
            self._index = self._build_index(df)
        return self._index

    @staticmethod
    def _index_entry_to_airport_base(entry: Dict[str, Any]) -> Dict[str, Any]:
        """Build a flat airport dict from an index entry (avoids DataFrame lookup)."""
        return {
            "id": entry["id"],
            "ident": entry["ident"],
            "type": entry["type"],
            "name": entry["name"],
            "latitude_deg": entry["lat"],
            "longitude_deg": entry["lon"],
            "municipality": entry["municipality"] or None,
            "iso_country": entry["iso_country"] or None,
            "iata_code": entry["iata_code"] or None,
        }

    # ── location search ──────────────────────────────────────────────

    async def search_by_location(
        self,
        lat: float,
        lon: float,
        radius_km: float = 50.0,
        airport_type: Optional[str] = None,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """Find airports within *radius_km* of (*lat*, *lon*)."""
        df = await self._get_airports()

        # Bounding-box pre-filter (1 degree lat ~ 111 km)
        deg_offset = radius_km / 111.0
        lat_min, lat_max = lat - deg_offset, lat + deg_offset
        cos_lat = math.cos(math.radians(lat)) or 0.01
        lon_offset = radius_km / (111.0 * cos_lat)
        lon_min, lon_max = lon - lon_offset, lon + lon_offset

        mask = (
            df["latitude_deg"].between(lat_min, lat_max)
            & df["longitude_deg"].between(lon_min, lon_max)
        )
        if airport_type:
            mask = mask & (df["type"] == airport_type)
        candidates = df[mask]

        results = []
        for record in candidates.to_dict("records"):
            r_lat = record.get("latitude_deg")
            r_lon = record.get("longitude_deg")
            if pd.isna(r_lat) or pd.isna(r_lon):
                continue
            dist = haversine_distance(lat, lon, float(r_lat), float(r_lon))
            if dist <= radius_km:
                results.append({
                    "id": None if pd.isna(record.get("id")) else record.get("id"),
                    "ident": record.get("ident"),
                    "type": record.get("type"),
                    "name": record.get("name"),
                    "latitude_deg": r_lat,
                    "longitude_deg": r_lon,
                    "elevation_ft": None if pd.isna(record.get("elevation_ft")) else record.get("elevation_ft"),
                    "municipality": None if pd.isna(record.get("municipality")) else record.get("municipality"),
                    "iso_country": None if pd.isna(record.get("iso_country")) else record.get("iso_country"),
                    "iso_region": None if pd.isna(record.get("iso_region")) else record.get("iso_region"),
                    "iata_code": None if pd.isna(record.get("iata_code")) else record.get("iata_code"),
                    "distance_km": round(dist, 2),
                })

        results.sort(key=lambda r: r["distance_km"])
        results = results[:limit]

        return {
            "search_location": {
                "latitude": lat,
                "longitude": lon,
                "radius_km": radius_km,
                "type_filter": airport_type,
            },
            "airports": results,
            "airports_found": len(results),
        }

    # ── IP-based search ──────────────────────────────────────────────

    async def _geolocate_ip(self, ip: str) -> Dict[str, Any]:
        """Resolve an IP address to coordinates using the local GeoIP database."""
        return await ip_geolocation_service.geolocate(ip)

    async def search_by_ip(
        self,
        ip: str,
        radius_km: float = 100.0,
        airport_type: Optional[str] = None,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """Geolocate *ip* and find nearby airports."""
        try:
            geo = await self._geolocate_ip(ip)
            lat = geo["lat"]
            lon = geo["lon"]
        except Exception as exc:
            return {
                "ip_address": ip,
                "location": None,
                "airports": [],
                "search_radius_km": int(radius_km),
                "airports_found": 0,
                "error": str(exc),
            }

        location_result = await self.search_by_location(
            lat, lon, radius_km, airport_type, limit,
        )

        location_data = {
            "latitude": lat,
            "longitude": lon,
            "city": geo.get("city"),
            "region": geo.get("regionName"),
            "country": geo.get("country"),
            "country_code": geo.get("countryCode"),
            "postal": geo.get("zip"),
            "timezone": geo.get("timezone"),
            "ip": ip,
        }

        return {
            "ip_address": ip,
            "location": location_data,
            "airports": location_result["airports"],
            "search_radius_km": int(radius_km),
            "airports_found": location_result["airports_found"],
            "error": None,
        }

    # ── text search ──────────────────────────────────────────────────

    async def search_by_text(
        self,
        query: str,
        limit: int = 20,
        airport_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Free-text airport search with relevance scoring.

        Scoring:
          exact ICAO  100 | exact IATA  90 | exact name  80 | exact city  70
          partial name 50 | partial city 40 | partial ident 30
          country code 20 | keywords     15
          + size bonus: large +10, medium +5
        """
        index = await self._get_index()
        q = query.strip().lower()
        if not q:
            return {"query": query, "airports": [], "airports_found": 0}

        scored: List[Tuple[int, Dict[str, Any]]] = []

        for entry in index:
            if airport_type and entry["type"] != airport_type:
                continue

            score = 0

            # Exact matches
            if q == entry["l_ident"]:
                score = max(score, 100)
            if entry["l_iata"] and q == entry["l_iata"]:
                score = max(score, 90)
            if q == entry["l_name"]:
                score = max(score, 80)
            if entry["l_municipality"] and q == entry["l_municipality"]:
                score = max(score, 70)

            # Partial matches (only if no exact match yet)
            if score < 50 and q in entry["l_name"]:
                score = max(score, 50)
            if score < 40 and entry["l_municipality"] and q in entry["l_municipality"]:
                score = max(score, 40)
            if score < 30 and q in entry["l_ident"]:
                score = max(score, 30)
            if score < 20 and entry["l_country"] and q == entry["l_country"]:
                score = max(score, 20)
            if score < 15 and entry["l_keywords"] and q in entry["l_keywords"]:
                score = max(score, 15)

            if score == 0:
                continue

            score += entry["size_bonus"]

            airport = self._index_entry_to_airport_base(entry)
            scored.append((score, airport))

        # Sort by score descending, then by name for ties
        scored.sort(key=lambda x: (-x[0], x[1].get("name", "")))
        top = scored[:limit]

        results = []
        for score, airport in top:
            results.append({
                "id": airport["id"],
                "ident": airport["ident"],
                "type": airport["type"],
                "name": airport["name"],
                "latitude_deg": airport["latitude_deg"],
                "longitude_deg": airport["longitude_deg"],
                "municipality": airport["municipality"],
                "iso_country": airport["iso_country"],
                "iata_code": airport["iata_code"],
                "relevance_score": score,
            })

        return {
            "query": query,
            "airports": results,
            "airports_found": len(results),
        }


# Global singleton
airport_search_service = AirportSearchService()

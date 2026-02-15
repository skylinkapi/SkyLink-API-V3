import asyncio
import time
import logging
from io import StringIO
from typing import Optional, Dict, Any, List

import pandas as pd
import httpx

logger = logging.getLogger(__name__)

# Cache TTL: 1 hour for static reference data (airports, runways, etc.)
_CACHE_TTL = 3600


class AirportService:
    """Service for enriching airport data by fetching from ourairports-data."""

    def __init__(self):
        self.base_url = "https://raw.githubusercontent.com/davidmegginson/ourairports-data/main"
        self._client: Optional[httpx.AsyncClient] = None
        # DataFrame cache: filename -> (DataFrame, timestamp)
        self._df_cache: Dict[str, tuple] = {}
        # Fast lookup dicts built from airports.csv
        self._icao_lookup: Optional[Dict[str, Dict[str, Any]]] = None
        self._iata_lookup: Optional[Dict[str, Dict[str, Any]]] = None

    @staticmethod
    def _convert_value(value):
        """Convert pandas/numpy values to JSON serializable Python types."""
        if pd.isna(value):
            return None
        if hasattr(value, 'item'):
            return value.item()
        return value

    async def _get_client(self) -> httpx.AsyncClient:
        """Return a reusable httpx client (lazy init)."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def fetch_data(self, filename: str) -> pd.DataFrame:
        """Fetch CSV data from GitHub with 1-hour cache."""
        now = time.time()
        cached = self._df_cache.get(filename)
        if cached and (now - cached[1]) < _CACHE_TTL:
            return cached[0]

        url = f"{self.base_url}/{filename}"
        client = await self._get_client()
        response = await client.get(url)
        response.raise_for_status()
        df = pd.read_csv(StringIO(response.text))
        self._df_cache[filename] = (df, now)

        # Invalidate lookup dicts when airports.csv refreshes
        if filename == "airports.csv":
            self._icao_lookup = None
            self._iata_lookup = None

        return df

    async def _ensure_lookups(self):
        """Build ICAO/IATA -> airport dict lookups once for O(1) find_airport_by_code."""
        if self._icao_lookup is not None:
            return

        df = await self.fetch_data("airports.csv")
        icao_lookup: Dict[str, Dict[str, Any]] = {}
        iata_lookup: Dict[str, Dict[str, Any]] = {}

        for record in df.to_dict("records"):
            clean = {k: self._convert_value(v) for k, v in record.items()}

            ident = clean.get("ident")
            iata = clean.get("iata_code")

            if ident and isinstance(ident, str):
                icao_lookup[ident.upper()] = clean
            if iata and isinstance(iata, str) and iata.upper() not in ("", "NAN"):
                iata_lookup[iata.upper()] = clean

        self._icao_lookup = icao_lookup
        self._iata_lookup = iata_lookup

    async def find_airport_by_code(self, code: str) -> Optional[Dict[str, Any]]:
        """Find airport by IATA or ICAO code using pre-built O(1) lookups."""
        try:
            await self._ensure_lookups()
            code = code.upper()

            if len(code) == 4 and code in self._icao_lookup:
                return self._icao_lookup[code]
            if len(code) == 3 and code in self._iata_lookup:
                return self._iata_lookup[code]
            # Fallback: try both regardless of length
            if code in self._icao_lookup:
                return self._icao_lookup[code]
            if code in self._iata_lookup:
                return self._iata_lookup[code]

            return None
        except Exception as e:
            logger.error(f"Error finding airport by code {code}: {e}")
            raise

    async def get_runways_for_airport(self, airport_ident: str) -> List[Dict[str, Any]]:
        """Get all runways for an airport by airport_ident (ICAO)."""
        try:
            runways_df = await self.fetch_data("runways.csv")
            airport_runways = runways_df[runways_df['airport_ident'] == airport_ident]

            runways = []
            for record in airport_runways.to_dict("records"):
                runways.append({k: self._convert_value(v) for k, v in record.items()})
            return runways
        except Exception as e:
            logger.error(f"Error getting runways for airport {airport_ident}: {e}")
            raise

    async def get_frequencies_for_airport(self, airport_ident: str) -> List[Dict[str, Any]]:
        """Get all frequencies for an airport by airport_ident (ICAO)."""
        try:
            frequencies_df = await self.fetch_data("airport-frequencies.csv")
            airport_frequencies = frequencies_df[frequencies_df['airport_ident'] == airport_ident]

            frequencies = []
            for record in airport_frequencies.to_dict("records"):
                frequencies.append({
                    'id': self._convert_value(record.get('id')),
                    'type': self._convert_value(record.get('type')),
                    'description': self._convert_value(record.get('description')),
                    'frequency_mhz': self._convert_value(record.get('frequency_mhz')),
                    'airport_ref': self._convert_value(record.get('airport_ref')),
                })
            return frequencies
        except Exception as e:
            logger.error(f"Error getting frequencies for airport {airport_ident}: {e}")
            raise

    async def get_country_info(self, iso_country: str) -> Optional[Dict[str, Any]]:
        """Get country information by iso_country code."""
        try:
            if not iso_country or pd.isna(iso_country):
                return None

            countries_df = await self.fetch_data("countries.csv")
            country_matches = countries_df[countries_df['code'] == iso_country]
            if country_matches.empty:
                return None

            country = country_matches.iloc[0]
            country_dict = {
                'id': country.get('id'),
                'code': country.get('code'),
                'name': country.get('name'),
                'continent': country.get('continent'),
                'wikipedia_link': country.get('wikipedia_link'),
                'keywords': country.get('keywords')
            }
            return {k: self._convert_value(v) for k, v in country_dict.items()}
        except Exception as e:
            logger.error(f"Error getting country info for {iso_country}: {e}")
            raise

    async def get_region_info(self, iso_region: str) -> Optional[Dict[str, Any]]:
        """Get region information by iso_region code."""
        try:
            if not iso_region or pd.isna(iso_region):
                return None

            regions_df = await self.fetch_data("regions.csv")
            region_matches = regions_df[regions_df['code'] == iso_region]
            if region_matches.empty:
                return None

            region = region_matches.iloc[0]
            region_dict = {
                'id': region.get('id'),
                'code': region.get('code'),
                'local_code': region.get('local_code'),
                'name': region.get('name'),
                'continent': region.get('continent'),
                'iso_country': region.get('iso_country'),
                'wikipedia_link': region.get('wikipedia_link'),
                'keywords': region.get('keywords')
            }
            return {k: self._convert_value(v) for k, v in region_dict.items()}
        except Exception as e:
            logger.error(f"Error getting region info for {iso_region}: {e}")
            raise

    async def get_navaids_for_airport(self, airport_icao: str) -> List[Dict[str, Any]]:
        """Get all navaids associated with an airport by ICAO code."""
        try:
            navaids_df = await self.fetch_data("navaids.csv")
            airport_navaids = navaids_df[navaids_df['associated_airport'] == airport_icao]

            navaids = []
            for record in airport_navaids.to_dict("records"):
                navaids.append({k: self._convert_value(v) for k, v in record.items()})
            return navaids
        except Exception as e:
            logger.error(f"Error getting navaids for airport {airport_icao}: {e}")
            raise

    async def get_enriched_airport_data(self, code: str) -> Optional[Dict[str, Any]]:
        """Get enriched airport data by combining all data sources concurrently."""
        try:
            airport = await self.find_airport_by_code(code)
            if not airport:
                return None

            airport_ident = airport.get('ident')
            if not airport_ident:
                logger.warning(f"Airport {code} has no ICAO identifier")
                return airport

            enriched_data = airport.copy()

            # Fetch all supplementary data concurrently
            runways, frequencies, country, region, navaids = await asyncio.gather(
                self.get_runways_for_airport(airport_ident),
                self.get_frequencies_for_airport(airport_ident),
                self.get_country_info(airport.get('iso_country')),
                self.get_region_info(airport.get('iso_region')),
                self.get_navaids_for_airport(airport_ident),
            )

            enriched_data['runways'] = runways
            enriched_data['frequencies'] = frequencies
            enriched_data['country'] = country
            enriched_data['region'] = region
            enriched_data['navaids'] = navaids

            return enriched_data
        except Exception as e:
            logger.error(f"Error enriching airport data for {code}: {e}")
            raise


# Global airport service instance
airport_service = AirportService()

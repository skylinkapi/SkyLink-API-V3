import time
import logging
from io import StringIO
from typing import Optional, Dict, Tuple

import pandas as pd
import httpx

logger = logging.getLogger(__name__)

# URLs for aviation data
AIRPORTS_URL = "https://davidmegginson.github.io/ourairports-data/airports.csv"
FREQUENCIES_URL = "https://davidmegginson.github.io/ourairports-data/airport-frequencies.csv"
NAVAIDS_URL = "https://davidmegginson.github.io/ourairports-data/navaids.csv"
AIRLINES_URL = "https://raw.githubusercontent.com/jpatokal/openflights/master/data/airlines.dat"

# Cache TTL: 1 hour for reference data
_CACHE_TTL = 3600

# Module-level cache and client
_cache: Dict[str, Tuple[pd.DataFrame, float]] = {}
_client: Optional[httpx.AsyncClient] = None


async def _get_client() -> httpx.AsyncClient:
    """Return a reusable httpx client."""
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=30.0)
    return _client


async def fetch_csv(url: str, sep: str = ',', header='infer', dtype=None):
    """Fetch a CSV from a URL with 1-hour cache."""
    now = time.time()
    cached = _cache.get(url)
    if cached and (now - cached[1]) < _CACHE_TTL:
        return cached[0]

    client = await _get_client()
    response = await client.get(url)
    response.raise_for_status()
    df = pd.read_csv(StringIO(response.text), sep=sep, header=header, dtype=dtype)
    _cache[url] = (df, now)
    return df


async def get_airports():
    return await fetch_csv(AIRPORTS_URL)

async def get_frequencies():
    return await fetch_csv(FREQUENCIES_URL)

async def get_navaids():
    return await fetch_csv(NAVAIDS_URL)

async def get_airlines():
    return await fetch_csv(AIRLINES_URL, header=None, dtype=str)

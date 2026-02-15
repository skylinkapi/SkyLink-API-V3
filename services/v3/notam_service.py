"""
NOTAMs service — reads from FAA SWIM FNS real-time feed.

Source: FAA SWIM Flight Notification Service via Solace messaging.
NOTAMs are received continuously in the background and stored in memory.
"""

import logging
from typing import Dict

from data_ingestion.v3.swim_notam_client import get_swim_notam_client

logger = logging.getLogger(__name__)


async def get_notams(icao: str) -> Dict:
    """Get active NOTAMs for an airport from the SWIM feed.

    Returns dict ready for NOTAMResponse model.
    """
    icao = icao.upper().strip()
    client = get_swim_notam_client()
    notams = client.get_notams(icao)

    return {
        "icao": icao,
        "notams": notams,
        "total": len(notams),
    }

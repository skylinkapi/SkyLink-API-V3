"""v3 Airport Search models — AirportType enum only.

Response models (AirportsByLocationResponse, AirportsByIPResponse,
AirportsTextSearchResponse, etc.) live in models/airports.py and are
reused here.
"""

from enum import Enum


class AirportType(str, Enum):
    large_airport = "large_airport"
    medium_airport = "medium_airport"
    small_airport = "small_airport"
    heliport = "heliport"
    seaplane_base = "seaplane_base"
    closed = "closed"
    balloonport = "balloonport"

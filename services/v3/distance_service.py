"""
Distance & Bearing calculation service.

Uses the Haversine formula for great-circle distances and forward-azimuth
bearing calculations.  Supports resolving ICAO/IATA airport codes to
coordinates via the existing AirportService.
"""

import math
from typing import Union

from models.v3.distance import Coordinates, DistanceUnit
from services.airport_service import airport_service


# ── Constants ────────────────────────────────────────────────────────────────

EARTH_RADIUS_KM = 6371.0
KM_TO_NM = 0.539957
KM_TO_MI = 0.621371


# ── Public service class ─────────────────────────────────────────────────────

class DistanceService:
    """Calculate great-circle distances and bearings between aviation waypoints."""

    # ── coordinate resolution ────────────────────────────────────────────

    async def resolve_point(self, point: Union[str, Coordinates]) -> Coordinates:
        """Resolve an ICAO/IATA code **or** a Coordinates object to Coordinates."""
        if isinstance(point, Coordinates):
            return point

        code = point.upper().strip()
        airport = await airport_service.find_airport_by_code(code)
        if not airport:
            raise ValueError(f"Airport not found: {code}")

        return Coordinates(
            latitude=airport["latitude_deg"],
            longitude=airport["longitude_deg"],
            icao_code=airport.get("ident"),
            iata_code=airport.get("iata_code"),
            name=airport.get("name"),
        )

    # ── distance ─────────────────────────────────────────────────────────

    def haversine(
        self,
        lat1: float, lon1: float,
        lat2: float, lon2: float,
    ) -> float:
        """Return great-circle distance in **kilometres**."""
        lat1_r, lon1_r = math.radians(lat1), math.radians(lon1)
        lat2_r, lon2_r = math.radians(lat2), math.radians(lon2)

        dlat = lat2_r - lat1_r
        dlon = lon2_r - lon1_r

        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return EARTH_RADIUS_KM * c

    def convert_distance(self, km: float, unit: DistanceUnit) -> float:
        """Convert kilometres to the requested unit."""
        if unit == DistanceUnit.KILOMETERS:
            return round(km, 2)
        if unit == DistanceUnit.NAUTICAL_MILES:
            return round(km * KM_TO_NM, 2)
        if unit == DistanceUnit.MILES:
            return round(km * KM_TO_MI, 2)
        return round(km, 2)

    # ── bearing ──────────────────────────────────────────────────────────

    def calculate_bearing(
        self,
        lat1: float, lon1: float,
        lat2: float, lon2: float,
    ) -> float:
        """Return initial (forward) bearing in degrees 0-360."""
        lat1_r = math.radians(lat1)
        lat2_r = math.radians(lat2)
        dlon = math.radians(lon2 - lon1)

        x = math.sin(dlon) * math.cos(lat2_r)
        y = (
            math.cos(lat1_r) * math.sin(lat2_r)
            - math.sin(lat1_r) * math.cos(lat2_r) * math.cos(dlon)
        )
        bearing = math.degrees(math.atan2(x, y))
        return round((bearing + 360) % 360, 2)

    @staticmethod
    def degrees_to_cardinal(deg: float) -> str:
        """Convert a bearing in degrees to a 16-point cardinal string."""
        directions = [
            "N", "NNE", "NE", "ENE",
            "E", "ESE", "SE", "SSE",
            "S", "SSW", "SW", "WSW",
            "W", "WNW", "NW", "NNW",
        ]
        idx = round(deg / 22.5) % 16
        return directions[idx]

    # ── midpoint ─────────────────────────────────────────────────────────

    def calculate_midpoint(self, c1: Coordinates, c2: Coordinates) -> Coordinates:
        """Return the geographic midpoint between two coordinates."""
        lat1 = math.radians(c1.latitude)
        lon1 = math.radians(c1.longitude)
        lat2 = math.radians(c2.latitude)
        lon2 = math.radians(c2.longitude)

        bx = math.cos(lat2) * math.cos(lon2 - lon1)
        by = math.cos(lat2) * math.sin(lon2 - lon1)

        mid_lat = math.atan2(
            math.sin(lat1) + math.sin(lat2),
            math.sqrt((math.cos(lat1) + bx) ** 2 + by ** 2),
        )
        mid_lon = lon1 + math.atan2(by, math.cos(lat1) + bx)

        return Coordinates(
            latitude=round(math.degrees(mid_lat), 6),
            longitude=round(math.degrees(mid_lon), 6),
        )

    # ── main entry point ─────────────────────────────────────────────────

    async def calculate(
        self,
        from_point: Union[str, Coordinates],
        to_point: Union[str, Coordinates],
        unit: DistanceUnit = DistanceUnit.NAUTICAL_MILES,
    ):
        """
        Calculate distance, bearing, and midpoint between two points.

        *from_point* / *to_point* can be an ICAO/IATA code string **or** a
        ``Coordinates`` object.

        Returns a dict ready to unpack into ``DistanceResponse``.
        """
        from_coords = await self.resolve_point(from_point)
        to_coords = await self.resolve_point(to_point)

        dist_km = self.haversine(
            from_coords.latitude, from_coords.longitude,
            to_coords.latitude, to_coords.longitude,
        )
        bearing = self.calculate_bearing(
            from_coords.latitude, from_coords.longitude,
            to_coords.latitude, to_coords.longitude,
        )

        return {
            "from_point": from_coords,
            "to_point": to_coords,
            "distance": self.convert_distance(dist_km, unit),
            "unit": unit,
            "bearing": bearing,
            "bearing_cardinal": self.degrees_to_cardinal(bearing),
            "midpoint": self.calculate_midpoint(from_coords, to_coords),
        }


# Global singleton
distance_service = DistanceService()

"""
Utility functions for ADS-B aircraft tracking.
"""

import math
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from data_ingestion.adsb_client import Aircraft

import httpx

logger = logging.getLogger(__name__)

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great circle distance between two points on earth in kilometers.
    
    Args:
        lat1, lon1: Latitude and longitude of first point in decimal degrees
        lat2, lon2: Latitude and longitude of second point in decimal degrees
        
    Returns:
        Distance in kilometers
    """
    # Convert decimal degrees to radians
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)
    
    # Haversine formula
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    
    a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    
    # Earth's radius in kilometers
    earth_radius_km = 6371.0
    
    return earth_radius_km * c

def is_in_bounding_box(lat: float, lon: float, lat1: float, lon1: float, 
                      lat2: float, lon2: float) -> bool:
    """
    Check if a point is within a bounding box.
    
    Args:
        lat, lon: Point coordinates
        lat1, lon1: Southwest corner
        lat2, lon2: Northeast corner
        
    Returns:
        True if point is within bounding box
    """
    return lat1 <= lat <= lat2 and lon1 <= lon <= lon2

def filter_aircraft_by_radius(aircraft_dict: Dict[str, Aircraft], 
                            center_lat: float, center_lon: float, 
                            radius_km: float) -> List[Aircraft]:
    """
    Filter aircraft within a specified radius from a center point.
    
    Args:
        aircraft_dict: Dictionary of aircraft by ICAO24
        center_lat, center_lon: Center point coordinates
        radius_km: Search radius in kilometers
        
    Returns:
        List of aircraft within the radius
    """
    filtered_aircraft = []
    
    for aircraft in aircraft_dict.values():
        if aircraft.latitude is None or aircraft.longitude is None:
            continue
            
        distance = haversine_distance(
            center_lat, center_lon,
            aircraft.latitude, aircraft.longitude
        )
        
        if distance <= radius_km:
            filtered_aircraft.append(aircraft)
    
    return filtered_aircraft

def filter_aircraft_by_bounding_box(aircraft_dict: Dict[str, Aircraft],
                                  lat1: float, lon1: float,
                                  lat2: float, lon2: float) -> List[Aircraft]:
    """
    Filter aircraft within a bounding box.
    
    Args:
        aircraft_dict: Dictionary of aircraft by ICAO24
        lat1, lon1: Southwest corner
        lat2, lon2: Northeast corner
        
    Returns:
        List of aircraft within the bounding box
    """
    filtered_aircraft = []
    
    for aircraft in aircraft_dict.values():
        if aircraft.latitude is None or aircraft.longitude is None:
            continue
            
        if is_in_bounding_box(aircraft.latitude, aircraft.longitude, 
                            lat1, lon1, lat2, lon2):
            filtered_aircraft.append(aircraft)
    
    return filtered_aircraft

def filter_aircraft_by_callsign(aircraft_dict: Dict[str, Aircraft], 
                               callsign: str) -> List[Aircraft]:
    """
    Filter aircraft by callsign (partial match, case-insensitive).
    
    Args:
        aircraft_dict: Dictionary of aircraft by ICAO24
        callsign: Callsign to search for
        
    Returns:
        List of matching aircraft
    """
    callsign_upper = callsign.upper()
    filtered_aircraft = []
    
    for aircraft in aircraft_dict.values():
        if aircraft.callsign and callsign_upper in aircraft.callsign.upper():
            filtered_aircraft.append(aircraft)
    
    return filtered_aircraft

def filter_aircraft_by_altitude(aircraft_dict: Dict[str, Aircraft],
                               min_alt: Optional[float] = None,
                               max_alt: Optional[float] = None) -> List[Aircraft]:
    """
    Filter aircraft by altitude range.
    
    Args:
        aircraft_dict: Dictionary of aircraft by ICAO24
        min_alt: Minimum altitude in feet
        max_alt: Maximum altitude in feet
        
    Returns:
        List of aircraft within altitude range
    """
    filtered_aircraft = []
    
    for aircraft in aircraft_dict.values():
        if aircraft.altitude is None:
            continue
            
        if min_alt is not None and aircraft.altitude < min_alt:
            continue
            
        if max_alt is not None and aircraft.altitude > max_alt:
            continue
            
        filtered_aircraft.append(aircraft)
    
    return filtered_aircraft

def filter_aircraft_by_speed(aircraft_dict: Dict[str, Aircraft],
                           min_speed: Optional[float] = None,
                           max_speed: Optional[float] = None) -> List[Aircraft]:
    """
    Filter aircraft by ground speed range.
    
    Args:
        aircraft_dict: Dictionary of aircraft by ICAO24
        min_speed: Minimum ground speed in knots
        max_speed: Maximum ground speed in knots
        
    Returns:
        List of aircraft within speed range
    """
    filtered_aircraft = []
    
    for aircraft in aircraft_dict.values():
        if aircraft.ground_speed is None:
            continue
            
        if min_speed is not None and aircraft.ground_speed < min_speed:
            continue
            
        if max_speed is not None and aircraft.ground_speed > max_speed:
            continue
            
        filtered_aircraft.append(aircraft)
    
    return filtered_aircraft

# Squawk filtering removed - squawk codes not available in data source

async def fetch_aircraft_photo(icao24: str, registration: Optional[str] = None) -> Optional[str]:
    """Fetch a single full-size aircraft photo URL from airport-data.com."""
    params = {"n": "1"}
    if icao24:
        params["m"] = icao24.upper()
    if registration:
        params["r"] = registration
    if not params.get("m") and not params.get("r"):
        return None
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                "https://airport-data.com/api/ac_thumb.json", params=params
            )
            if resp.status_code != 200:
                return None
            data = resp.json()
            if data.get("status") == 200 and data.get("data"):
                link = data["data"][0].get("link", "")
                if link:
                    photo_id = link.rstrip("/").split("/")[-1].replace(".html", "")
                    return f"https://image.airport-data.com/aircraft/{photo_id}.jpg"
    except Exception:
        return None
    return None


def convert_aircraft_to_response(aircraft: Aircraft) -> dict:
    """
    Convert Aircraft object to API response format.
    
    Args:
        aircraft: Aircraft object
        
    Returns:
        Dictionary formatted for API response
    """
    return {
        "icao24": aircraft.icao24,
        "callsign": aircraft.callsign,
        "latitude": aircraft.latitude,
        "longitude": aircraft.longitude,
        "altitude": aircraft.altitude,
        "ground_speed": aircraft.ground_speed,
        "track": aircraft.track,
        "vertical_rate": aircraft.vertical_rate,
        "is_on_ground": aircraft.is_on_ground,
        "last_seen": aircraft.last_seen,
        "first_seen": aircraft.first_seen,
        # Enriched data from aircraft database
        "registration": aircraft.registration,
        "aircraft_type": aircraft.aircraft_type,
        "airline": aircraft.airline,
        "year": getattr(aircraft, 'year', None),
        "military": getattr(aircraft, 'military', None)
    }

def get_aircraft_statistics(aircraft_dict: Dict[str, Aircraft]) -> dict:
    """
    Get statistics about tracked aircraft.
    
    Args:
        aircraft_dict: Dictionary of aircraft by ICAO24
        
    Returns:
        Statistics dictionary
    """
    total_count = len(aircraft_dict)
    
    # Count aircraft with position data
    positioned_count = sum(
        1 for aircraft in aircraft_dict.values()
        if aircraft.latitude is not None and aircraft.longitude is not None
    )
    
    # Count aircraft on ground vs airborne
    on_ground_count = sum(
        1 for aircraft in aircraft_dict.values()
        if aircraft.is_on_ground is True
    )
    
    airborne_count = sum(
        1 for aircraft in aircraft_dict.values()
        if aircraft.is_on_ground is False
    )
    
    # Get altitude statistics for airborne aircraft
    airborne_altitudes = [
        aircraft.altitude for aircraft in aircraft_dict.values()
        if aircraft.altitude is not None and aircraft.is_on_ground is False
    ]
    
    altitude_stats = {}
    if airborne_altitudes:
        altitude_stats = {
            "min_altitude": min(airborne_altitudes),
            "max_altitude": max(airborne_altitudes),
            "avg_altitude": sum(airborne_altitudes) / len(airborne_altitudes)
        }
    
    return {
        "total_aircraft": total_count,
        "positioned_aircraft": positioned_count,
        "on_ground": on_ground_count,
        "airborne": airborne_count,
        "altitude_stats": altitude_stats,
        "timestamp": datetime.now()
    }
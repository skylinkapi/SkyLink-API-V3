

from fastapi import APIRouter, HTTPException, status, Path, Query
from typing import Dict, Any, Optional
import avwx
from avwx.exceptions import BadStation
from services.airport_service import airport_service
import logging
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/weather", tags=["Weather"])

async def get_metar_async(icao: str) -> dict:
    """Get METAR weather data asynchronously"""
    try:
        icao = icao.upper().strip()
        logger.info(f"Fetching METAR for {icao}")
        
        metar = avwx.Metar(icao)
        
        # Use async update method
        success = await metar.async_update()
        
        if success and metar.raw:
            logger.info(f"Successfully fetched METAR for {icao}")
            return {
                "raw": metar.raw,
                "station": metar.station.icao if hasattr(metar.station, 'icao') else icao,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "_data": metar.data
            }
        else:
            logger.warning(f"No METAR data available for {icao}")
            return {"error": "No METAR found"}
            
    except BadStation as e:
        logger.warning(f"Bad station for METAR {icao}: {e}")
        return {"error": "Invalid ICAO code"}
    except Exception as e:
        logger.error(f"Error fetching METAR for {icao}: {e}")
        return {"error": str(e)}

async def get_taf_async(icao: str) -> dict:
    """Get TAF forecast data asynchronously"""
    try:
        icao = icao.upper().strip()
        logger.info(f"Fetching TAF for {icao}")
        
        taf = avwx.Taf(icao)
        
        # Use async update method
        success = await taf.async_update()
        
        if success and taf.raw:
            logger.info(f"Successfully fetched TAF for {icao}")
            return {
                "raw": taf.raw,
                "station": taf.station.icao if hasattr(taf.station, 'icao') else icao,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "_data": taf.data
            }
        else:
            logger.warning(f"No TAF data available for {icao}")
            return {"error": "No TAF found"}
            
    except BadStation as e:
        logger.warning(f"Bad station for TAF {icao}: {e}")
        return {"error": "Invalid ICAO code"}
    except Exception as e:
        logger.error(f"Error fetching TAF for {icao}: {e}")
        return {"error": str(e)}

def _num_val(obj) -> Optional[float]:
    """Extract numeric value from avwx Number-like objects."""
    if obj is None:
        return None
    if hasattr(obj, 'value'):
        return obj.value
    return obj

def _timestamp(obj) -> Optional[str]:
    """Extract ISO timestamp from avwx Timestamp-like objects."""
    if obj is None:
        return None
    if hasattr(obj, 'dt') and obj.dt:
        return obj.dt.isoformat() + "Z" if obj.dt.tzinfo is None else obj.dt.isoformat()
    if hasattr(obj, 'repr'):
        return obj.repr
    return str(obj)

def _serialize_cloud(cloud) -> dict:
    """Serialize a single cloud layer."""
    return {
        "type": getattr(cloud, 'type', None),
        "base": getattr(cloud, 'base', None),
        "repr": cloud.repr if hasattr(cloud, 'repr') else str(cloud),
    }

def _serialize_wx_code(wx) -> dict:
    """Serialize a weather code."""
    return {
        "repr": wx.repr if hasattr(wx, 'repr') else str(wx),
        "value": getattr(wx, 'value', None),
    }

def _serialize_metar(data) -> Optional[dict]:
    """Convert avwx MetarData to a JSON-safe dict."""
    if data is None:
        return None
    try:
        vis = None
        if data.visibility is not None:
            vis = {
                "value": _num_val(data.visibility),
                "repr": data.visibility.repr if hasattr(data.visibility, 'repr') else str(data.visibility),
            }

        return {
            "wind": {
                "direction": _num_val(data.wind_direction),
                "speed": _num_val(data.wind_speed),
                "gust": _num_val(data.wind_gust),
                "variable": _num_val(getattr(data, 'wind_variable_direction', None)),
            },
            "visibility": vis,
            "clouds": [_serialize_cloud(c) for c in (data.clouds or [])],
            "temperature": _num_val(data.temperature),
            "dewpoint": _num_val(data.dewpoint),
            "altimeter": _num_val(data.altimeter),
            "flight_rules": getattr(data, 'flight_rules', None),
            "wx_codes": [_serialize_wx_code(wx) for wx in (data.wx_codes or [])],
            "remarks": getattr(data, 'remarks', None),
            "time": _timestamp(data.time),
            "density_altitude": getattr(data, 'density_altitude', None),
            "pressure_altitude": getattr(data, 'pressure_altitude', None),
            "relative_humidity": getattr(data, 'relative_humidity', None),
        }
    except Exception as e:
        logger.error(f"Error serializing METAR data: {e}")
        return None

def _serialize_taf_period(period) -> dict:
    """Serialize a single TAF forecast period."""
    vis = None
    if period.visibility is not None:
        vis = {
            "value": _num_val(period.visibility),
            "repr": period.visibility.repr if hasattr(period.visibility, 'repr') else str(period.visibility),
        }
    return {
        "type": getattr(period, 'type', None),
        "start_time": _timestamp(period.start_time),
        "end_time": _timestamp(period.end_time),
        "wind": {
            "direction": _num_val(period.wind_direction),
            "speed": _num_val(period.wind_speed),
            "gust": _num_val(period.wind_gust),
            "variable": _num_val(getattr(period, 'wind_variable_direction', None)),
        },
        "visibility": vis,
        "clouds": [_serialize_cloud(c) for c in (period.clouds or [])],
        "wx_codes": [_serialize_wx_code(wx) for wx in (period.wx_codes or [])],
        "flight_rules": getattr(period, 'flight_rules', None),
        "probability": getattr(period, 'probability', None),
        "turbulence": [str(t) for t in (getattr(period, 'turbulence', None) or [])],
        "icing": [str(i) for i in (getattr(period, 'icing', None) or [])],
    }

def _serialize_taf(data) -> Optional[dict]:
    """Convert avwx TafData to a JSON-safe dict."""
    if data is None:
        return None
    try:
        return {
            "start_time": _timestamp(data.start_time),
            "end_time": _timestamp(data.end_time),
            "forecast": [_serialize_taf_period(p) for p in (data.forecast or [])],
        }
    except Exception as e:
        logger.error(f"Error serializing TAF data: {e}")
        return None

@router.get(
    "/metar/{icao}",
    responses={
        200: {
            "description": "Current METAR weather data",
            "content": {
                "application/json": {
                    "example": {
                        "raw": "METAR KJFK 271851Z 16013KT 10SM FEW024 15/09 A3020 RMK AO2 SLP216 T01500089",
                        "icao": "KJFK",
                        "airport_name": "John F Kennedy International Airport",
                        "timestamp": "2025-09-27T12:00:00Z"
                    }
                }
            }
        }
    }
)
async def get_metar_data(
    icao: str = Path(..., description="4-letter ICAO airport code", min_length=4, max_length=4),
    parsed: bool = Query(False, description="Include parsed/decoded METAR fields alongside raw text")
) -> Dict[str, Any]:
    """
    Get current METAR weather data for an airport by ICAO code.

    - **icao**: 4-letter ICAO airport code (e.g., KJFK, EGLL)
    - **parsed**: If true, includes structured decoded fields (wind, visibility, clouds, etc.)
    """
    try:
        icao = icao.upper().strip()
        if len(icao) != 4:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="ICAO code must be exactly 4 characters"
            )
        
        # Verify airport exists first
        airport = await airport_service.find_airport_by_code(icao)
        if not airport:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Airport not found for ICAO code: {icao}"
            )
        
        # Fetch METAR data
        result = await get_metar_async(icao)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to fetch weather data at this time"
            )
        
        if "error" in result:
            error_msg = result.get("error", "Unknown error")
            logger.warning(f"METAR error for {icao}: {error_msg}")
            
            # Provide more specific error messages
            if "Invalid ICAO code" in error_msg:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Weather station not found for {icao}. This airport may not have a weather reporting station."
                )
            elif "No METAR found" in error_msg:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"No current METAR data available for {icao}. Weather station may be temporarily offline."
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f"Weather service temporarily unavailable for {icao}"
                )
        
        # Add airport information to response
        try:
            response_data = {
                "raw": result.get("raw"),
                "icao": icao,
                "airport_name": airport.get("name"),
                "timestamp": result.get("timestamp")
            }
            if parsed:
                response_data["parsed"] = _serialize_metar(result.get("_data"))
            return response_data
        except Exception as serialize_error:
            logger.error(f"Error serializing METAR response for {icao}: {serialize_error}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to format weather data response"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching METAR for {icao}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to fetch weather data at this time"
        )

@router.get(
    "/taf/{icao}",
    responses={
        200: {
            "description": "Terminal Aerodrome Forecast (TAF) data",
            "content": {
                "application/json": {
                    "example": {
                        "raw": "TAF KJFK 271720Z 2718/2824 16012KT P6SM FEW025 SCT250 FM272100 18010KT P6SM SCT025 BKN250",
                        "icao": "KJFK",
                        "airport_name": "John F Kennedy International Airport",
                        "timestamp": "2025-09-27T12:00:00Z"
                    }
                }
            }
        }
    }
)
async def get_taf_data(
    icao: str = Path(..., description="4-letter ICAO airport code", min_length=4, max_length=4),
    parsed: bool = Query(False, description="Include parsed/decoded TAF fields alongside raw text")
) -> Dict[str, Any]:
    """
    Get Terminal Aerodrome Forecast (TAF) data for an airport by ICAO code.

    - **icao**: 4-letter ICAO airport code (e.g., KJFK, EGLL)
    - **parsed**: If true, includes structured decoded fields (forecast periods, wind, visibility, etc.)
    """
    try:
        icao = icao.upper().strip()
        if len(icao) != 4:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="ICAO code must be exactly 4 characters"
            )
        
        # Verify airport exists first
        airport = await airport_service.find_airport_by_code(icao)
        if not airport:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Airport not found for ICAO code: {icao}"
            )
        
        # Fetch TAF data
        result = await get_taf_async(icao)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to fetch weather data at this time"
            )
        
        if "error" in result:
            error_msg = result.get("error", "Unknown error")
            logger.warning(f"TAF error for {icao}: {error_msg}")
            
            # Provide more specific error messages
            if "Invalid ICAO code" in error_msg:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Weather station not found for {icao}. This airport may not have a weather reporting station."
                )
            elif "No TAF found" in error_msg:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"No current TAF forecast available for {icao}. Weather station may not issue TAF reports or may be temporarily offline."
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f"Weather service temporarily unavailable for {icao}"
                )
        
        # Add airport information to response
        try:
            response_data = {
                "raw": result.get("raw"),
                "icao": icao,
                "airport_name": airport.get("name"),
                "timestamp": result.get("timestamp")
            }
            if parsed:
                response_data["parsed"] = _serialize_taf(result.get("_data"))
            return response_data
        except Exception as serialize_error:
            logger.error(f"Error serializing TAF response for {icao}: {serialize_error}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to format weather data response"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching TAF for {icao}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to fetch weather data at this time"
        )

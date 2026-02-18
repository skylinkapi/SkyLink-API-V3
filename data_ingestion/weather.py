

import avwx
from avwx.exceptions import BadStation
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

def get_metar(icao: str) -> dict:
    """Get METAR weather data for an airport"""
    try:
        icao = icao.upper().strip()
        logger.info(f"Fetching METAR for {icao}")
        
        metar = avwx.Metar(icao)
        
        # Use sync update method to avoid event loop issues
        success = metar.update()
        
        if success and metar.raw:
            logger.info(f"Successfully fetched METAR for {icao}")
            return {
                "raw": metar.raw,
                "station": metar.station,
                "timestamp": datetime.utcnow().isoformat() + "Z"
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

def get_taf(icao: str) -> dict:
    """Get TAF forecast data for an airport"""
    try:
        icao = icao.upper().strip()
        logger.info(f"Fetching TAF for {icao}")
        
        taf = avwx.Taf(icao)
        
        # Use sync update method to avoid event loop issues
        success = taf.update()
        
        if success and taf.raw:
            logger.info(f"Successfully fetched TAF for {icao}")
            return {
                "raw": taf.raw,
                "station": taf.station,
                "timestamp": datetime.utcnow().isoformat() + "Z"
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

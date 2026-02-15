"""
ADS-B Data Client for connecting to ADS-B Hub and parsing SBS CSV data.
Clean version with proper SBS parsing.
"""

import socket
import threading
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from dataclasses import dataclass

# Get logger (configuration is done in main.py)
logger = logging.getLogger(__name__)

# Import aircraft database service
try:
    from services.aircraft_db_service import get_aircraft_db_service
    AIRCRAFT_DB_AVAILABLE = True
except ImportError:
    AIRCRAFT_DB_AVAILABLE = False
    logger.warning("Aircraft database service not available")

@dataclass
class SBSMessage:
    """SBS message data structure."""
    icao24: str = ""
    callsign: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    altitude: Optional[float] = None
    ground_speed: Optional[float] = None
    track: Optional[float] = None
    vertical_rate: Optional[float] = None
    is_on_ground: Optional[bool] = None

@dataclass
class Aircraft:
    """Aircraft data model for tracking active aircraft."""
    icao24: str
    callsign: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    altitude: Optional[float] = None
    ground_speed: Optional[float] = None
    track: Optional[float] = None
    vertical_rate: Optional[float] = None
    is_on_ground: Optional[bool] = None
    last_seen: datetime = None
    first_seen: datetime = None
    
    # Enriched fields from aircraft database
    registration: Optional[str] = None
    aircraft_type: Optional[str] = None
    airline: Optional[str] = None
    year: Optional[int] = None
    military: Optional[bool] = None
    
    def __post_init__(self):
        if self.last_seen is None:
            self.last_seen = datetime.now()
        if self.first_seen is None:
            self.first_seen = datetime.now()
    
    def update_from_sbs(self, sbs: SBSMessage) -> None:
        """Update aircraft data from SBS message."""
        if sbs.callsign:
            self.callsign = sbs.callsign.strip()
        if sbs.latitude is not None:
            self.latitude = sbs.latitude
        if sbs.longitude is not None:
            self.longitude = sbs.longitude
        if sbs.altitude is not None:
            self.altitude = sbs.altitude
        if sbs.ground_speed is not None:
            self.ground_speed = sbs.ground_speed
        if sbs.track is not None:
            self.track = sbs.track
        if sbs.vertical_rate is not None:
            self.vertical_rate = sbs.vertical_rate
        if sbs.squawk:
            self.squawk = sbs.squawk
        if sbs.is_on_ground is not None:
            self.is_on_ground = sbs.is_on_ground
        
        self.last_seen = datetime.now()

class ADSBClient:
    """ADS-B client for connecting to data.adsbhub.org and managing aircraft data."""
    
    def __init__(self, host: str = "data.adsbhub.org", port: int = 5002, aircraft_timeout: int = 120):
        self.host = host
        self.port = port
        self.aircraft_timeout = aircraft_timeout
        self.aircraft: Dict[str, Aircraft] = {}
        self.running = False
        self.socket = None
        self.thread = None
        self.lock = threading.Lock()
        self.cleanup_thread = None
        
    def start(self) -> None:
        """Start the ADS-B client connection."""
        if self.running:
            return
            
        self.running = True
        self.thread = threading.Thread(target=self._run_client, daemon=True)
        self.thread.start()
        
        # Start automatic cleanup thread
        self.cleanup_thread = threading.Thread(target=self._run_cleanup, daemon=True)
        self.cleanup_thread.start()
        
        logger.info("🚀 ADS-B client started")
        
    def stop(self) -> None:
        """Stop the ADS-B client connection."""
        self.running = False
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
        if self.thread:
            self.thread.join(timeout=5)
        if self.cleanup_thread:
            self.cleanup_thread.join(timeout=5)
        logger.info("🛑 ADS-B client stopped")
        
    def _run_cleanup(self) -> None:
        """Background thread to periodically clean old aircraft data."""
        logger.info("🧹 Automatic cleanup thread started")
        while self.running:
            try:
                # Clean old aircraft every 30 seconds to ensure data freshness
                time.sleep(30)
                if self.running:
                    self._clean_old_aircraft()
            except Exception as e:
                logger.debug(f"Cleanup error: {e}")
    
    def _run_client(self) -> None:
        """Main client loop for receiving and processing ADS-B data."""
        retry_count = 0
        max_retries = 1000  # Unlimited retries for production environment
        
        while self.running and retry_count < max_retries:
            try:
                self._connect_and_receive()
                retry_count = 0  # Reset retry count on successful connection
            except Exception as e:
                retry_count += 1
                # Reduce log spam - only log every 10th retry
                if retry_count % 10 == 0:
                    logger.warning(f"⚠️ ADS-B Hub connection lost")
                if retry_count < max_retries:
                    # Faster reconnection for cloud environment
                    wait_time = min(1 + (retry_count * 0.1), 5)  # 1-5 second exponential backoff
                    time.sleep(wait_time)
                else:
                    logger.error("ADS-B client connection failed after max retries")
                    break
                
    def _connect_and_receive(self) -> None:
        """Connect to ADS-B Hub and receive data."""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        
        # Optimized settings for Fly.io environment
        self.socket.settimeout(30)  # Shorter timeout for faster reconnection
        
        # Enable TCP keepalive to maintain connection
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        
        # Platform-specific keepalive settings
        import platform
        if platform.system() == "Linux":
            # Fly.io uses Linux - optimize for cloud environment
            self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 60)   # Start keepalive after 60s idle
            self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 10)  # Keepalive interval 10s
            self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 3)     # 3 failed keepalives = drop
        
        try:
            logger.info(f"📡 Connecting to {self.host}:{self.port}...")
            self.socket.connect((self.host, self.port))
            logger.info("📡 Connected to ADS-B Hub")
            
            buffer = ""
            message_count = 0
            consecutive_empty_reads = 0
            
            while self.running:
                try:
                    # Non-blocking receive with timeout handling
                    data = self.socket.recv(8192)
                    if not data:
                        consecutive_empty_reads += 1
                        if consecutive_empty_reads > 30:  # Reduced threshold for faster reconnection
                            raise ConnectionError("Connection lost - empty reads exceeded threshold")
                        # Shorter delay for cloud environment
                        time.sleep(0.05)
                        continue
                    else:
                        consecutive_empty_reads = 0
                        
                    # Decode and process
                    text_data = data.decode('utf-8', errors='ignore')
                    buffer += text_data
                    
                    # Process complete lines
                    lines = buffer.split('\n')
                    
                    # Process all lines except the last (potentially incomplete)
                    for line in lines[:-1]:
                        line = line.strip()
                        if line and line.startswith('MSG,'):
                            try:
                                # Debug removed - squawk analysis complete
                                aircraft_data = self._parse_sbs_line(line)
                                if aircraft_data:
                                    self._add_aircraft(aircraft_data)
                                    message_count += 1
                                    
                                    # Progress logging disabled to reduce console spam
                                    # if message_count % 50000 == 0:
                                    #     with self.lock:
                                    #         count = len(self.aircraft)
                                    #     logger.info(f"📊 Processed {message_count} messages, tracking {count} aircraft")
                            except Exception as e:
                                logger.debug(f"Parse error: {e}")
                    
                    # Keep the last incomplete line
                    buffer = lines[-1]
                    
                    # Prevent buffer from growing too large
                    if len(buffer) > 10000:
                        buffer = ""
                        
                except socket.error as e:
                    logger.warning(f"Socket error: {e}")
                    break
                    
        except socket.timeout:
            logger.debug("Socket timeout, reconnecting...")
        except Exception as e:
            logger.debug(f"Connection error: {e}")
        finally:
            if self.socket:
                self.socket.close()
                
    def _parse_sbs_line(self, line: str) -> Optional[Dict]:
        """Parse a single SBS CSV line into aircraft data."""
        try:
            fields = line.split(',')
            
            # SBS format validation
            if len(fields) < 20 or fields[0] != 'MSG':
                return None
                
            # Extract ICAO24 (field 4)
            icao24 = fields[4].strip()
            if not icao24 or len(icao24) < 1:
                return None
                
            # Pad ICAO24 to 6 characters
            icao24 = icao24.upper().zfill(6)
            
            aircraft_data = {'icao24': icao24}
            
            # Extract other fields safely
            try:
                # Callsign (field 10)
                if len(fields) > 10 and fields[10].strip():
                    aircraft_data['callsign'] = fields[10].strip()
                    
                # Altitude (field 11)
                if len(fields) > 11 and fields[11].strip():
                    aircraft_data['altitude'] = float(fields[11])
                    
                # Ground speed (field 12)
                if len(fields) > 12 and fields[12].strip():
                    aircraft_data['ground_speed'] = float(fields[12])
                    
                # Track (field 13)
                if len(fields) > 13 and fields[13].strip():
                    aircraft_data['track'] = float(fields[13])
                    
                # Latitude (field 14)
                if len(fields) > 14 and fields[14].strip():
                    lat = float(fields[14])
                    if -90 <= lat <= 90:
                        aircraft_data['latitude'] = lat
                        
                # Longitude (field 15)
                if len(fields) > 15 and fields[15].strip():
                    lon = float(fields[15])
                    if -180 <= lon <= 180:
                        aircraft_data['longitude'] = lon
                        
                # Vertical rate (field 16)
                if len(fields) > 16 and fields[16].strip():
                    aircraft_data['vertical_rate'] = float(fields[16])
                    
                # Note: Squawk codes not available in this data source
                
                # Alert flag (field 18) - indicates emergency/alert
                if len(fields) > 18 and fields[18].strip():
                    aircraft_data['alert'] = fields[18].strip() == '1'
                    
                # Emergency flag (field 19) - indicates emergency squawk
                if len(fields) > 19 and fields[19].strip():
                    aircraft_data['emergency'] = fields[19].strip() == '1'
                    
                # SPI flag (field 20) - Special Position Identification 
                if len(fields) > 20 and fields[20].strip():
                    aircraft_data['spi'] = fields[20].strip() == '1'
                    
                # On ground (field 21) - check if exists
                if len(fields) > 21 and fields[21].strip():
                    aircraft_data['is_on_ground'] = fields[21].strip() == '1'
                    
            except (ValueError, IndexError):
                pass  # Skip invalid numeric values
                
            return aircraft_data
            
        except Exception:
            return None
            
    def _add_aircraft(self, aircraft_data: Dict) -> None:
        """Add or update aircraft from parsed data."""
        icao24 = aircraft_data.get('icao24')
        if not icao24:
            return
            
        # Enrich aircraft data with database information
        if AIRCRAFT_DB_AVAILABLE:
            try:
                db_service = get_aircraft_db_service()
                aircraft_data = db_service.enrich_aircraft_data(aircraft_data)
                
                # Also enrich with airline info from callsign if not already set
                if not aircraft_data.get('airline') and aircraft_data.get('callsign'):
                    try:
                        from utils.airline_codes import get_airline_from_callsign
                        airline = get_airline_from_callsign(aircraft_data['callsign'])
                        if airline:
                            aircraft_data['airline'] = airline
                    except ImportError:
                        pass
                
                # Determine ground status from altitude if not provided
                if aircraft_data.get('is_on_ground') is None and aircraft_data.get('altitude') is not None:
                    # Consider aircraft on ground if altitude is 0 or very low (< 100 feet)
                    # This accounts for airport elevation and minor altitude reporting variations
                    aircraft_data['is_on_ground'] = aircraft_data['altitude'] < 100
                        
            except Exception as e:
                logger.debug(f"Aircraft enrichment failed for {icao24}: {e}")
            
        with self.lock:
            if icao24 in self.aircraft:
                # Update existing aircraft
                aircraft = self.aircraft[icao24]
                for key, value in aircraft_data.items():
                    if key != 'icao24' and value is not None:
                        setattr(aircraft, key, value)
                aircraft.last_seen = datetime.now()
            else:
                # Create new aircraft
                aircraft = Aircraft(icao24=icao24)
                for key, value in aircraft_data.items():
                    if key != 'icao24' and value is not None:
                        setattr(aircraft, key, value)
                self.aircraft[icao24] = aircraft
                
                # Aircraft addition logging disabled to reduce console spam  
                # if len(self.aircraft) <= 5:
                #     logger.info(f"✈️ Added aircraft: {icao24} (Total: {len(self.aircraft)})")
                
    def get_aircraft(self, clean_old: bool = True) -> Dict[str, Aircraft]:
        """Get all active aircraft."""
        if clean_old:
            self._clean_old_aircraft()
            
        with self.lock:
            return self.aircraft.copy()
            
    def get_aircraft_by_icao24(self, icao24: str) -> Optional[Aircraft]:
        """Get specific aircraft by ICAO24."""
        with self.lock:
            return self.aircraft.get(icao24.upper())
            
    def get_aircraft_by_registration(self, registration: str) -> Optional[Aircraft]:
        """Get specific aircraft by registration/tail number."""
        if not AIRCRAFT_DB_AVAILABLE:
            return None
            
        try:
            # First, look up ICAO24 by registration
            db_service = get_aircraft_db_service()
            icao24 = db_service.search_by_registration(registration)
            
            if icao24:
                return self.get_aircraft_by_icao24(icao24)
                
            # If not found in database, search through active aircraft
            with self.lock:
                for aircraft in self.aircraft.values():
                    if (aircraft.registration and 
                        aircraft.registration.upper() == registration.upper()):
                        return aircraft
                        
        except Exception as e:
            logger.debug(f"Registration search failed for {registration}: {e}")
            
        return None
            
    def is_connected(self) -> bool:
        """Check if connected."""
        return self.running and self.socket is not None
        
    def get_connection_status(self) -> dict:
        """Get connection status."""
        with self.lock:
            aircraft_count = len(self.aircraft)
            recent_count = 0
            
            if aircraft_count > 0:
                cutoff = datetime.now() - timedelta(seconds=60)
                recent_count = sum(1 for a in self.aircraft.values() if a.last_seen > cutoff)
                
        return {
            "running": self.running,
            "connected": self.is_connected(),
            "total_aircraft": aircraft_count,
            "recent_aircraft": recent_count,
            "host": self.host,
            "port": self.port
        }
            
    def _clean_old_aircraft(self) -> None:
        """Remove old aircraft that haven't been seen recently."""
        cutoff_time = datetime.now() - timedelta(seconds=self.aircraft_timeout)
        
        with self.lock:
            old_aircraft = [
                icao24 for icao24, aircraft in self.aircraft.items()
                if aircraft.last_seen < cutoff_time
            ]
            
            for icao24 in old_aircraft:
                del self.aircraft[icao24]
                
            if old_aircraft:
                if len(old_aircraft) < 20:
                    logger.info(f"🧹 Cleaned {len(old_aircraft)} stale aircraft (timeout: {self.aircraft_timeout}s)")
                else:
                    logger.info(f"🧹 Cleaned {len(old_aircraft)} stale aircraft")

# Global instance
adsb_client = ADSBClient()

def get_adsb_client() -> ADSBClient:
    """Get the global ADS-B client instance."""
    return adsb_client
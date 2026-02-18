"""
Aircraft Database Service for enriching ADS-B data with registration and owner information.
Uses basic-ac-db.json for aircraft lookups.
"""

import json
import logging
from typing import Dict, Optional, Any
from functools import lru_cache
import os

logger = logging.getLogger(__name__)

class AircraftDatabaseService:
    """Service for looking up aircraft information by ICAO24 or registration."""
    
    def __init__(self, db_file_path: str = "basic-ac-db.json"):
        self.db_file_path = db_file_path
        self._icao_lookup: Dict[str, Dict[str, Any]] = {}
        self._registration_lookup: Dict[str, Dict[str, Any]] = {}
        self._loaded = False
        
    def load_database(self) -> bool:
        """Load the aircraft database from JSON file."""
        if self._loaded:
            return True
            
        try:
            if not os.path.exists(self.db_file_path):
                logger.warning(f"Aircraft database file not found: {self.db_file_path}")
                return False
                
            logger.info(f"Loading aircraft database from {self.db_file_path}")
            
            with open(self.db_file_path, 'r', encoding='utf-8') as f:
                count = 0
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                        
                    try:
                        aircraft_data = json.loads(line)
                        icao = aircraft_data.get('icao')
                        reg = aircraft_data.get('reg')
                        
                        # Handle icao field safely - store in uppercase for consistent lookup
                        if icao and icao != 'NULL' and isinstance(icao, str):
                            icao_normalized = icao.upper().strip()
                            if icao_normalized:
                                self._icao_lookup[icao_normalized] = aircraft_data
                        
                        # Handle registration field safely  
                        if reg and reg != 'NULL' and isinstance(reg, str):
                            reg = reg.upper().strip()
                            if reg:
                                self._registration_lookup[reg] = aircraft_data
                            
                        count += 1
                        
                    except json.JSONDecodeError as e:
                        logger.debug(f"Skipping invalid JSON line: {e}")
                        continue
                        
            self._loaded = True
            logger.info(f"Loaded {count} aircraft records into database")
            logger.info(f"ICAO lookup entries: {len(self._icao_lookup)}")
            logger.info(f"Registration lookup entries: {len(self._registration_lookup)}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load aircraft database: {e}")
            return False
    
    def get_aircraft_by_icao24(self, icao24: str) -> Optional[Dict[str, Any]]:
        """Get aircraft information by ICAO24 code."""
        if not self._loaded:
            self.load_database()
            
        icao24 = icao24.upper().strip()
        return self._icao_lookup.get(icao24)
    
    def get_aircraft_by_registration(self, registration: str) -> Optional[Dict[str, Any]]:
        """Get aircraft information by registration/tail number."""
        if not self._loaded:
            self.load_database()
            
        registration = registration.upper().strip()
        return self._registration_lookup.get(registration)
    
    def enrich_aircraft_data(self, aircraft_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enrich aircraft data with database information.
        
        Args:
            aircraft_data: Basic aircraft data from ADS-B
            
        Returns:
            Enriched aircraft data with registration, owner, etc.
        """
        enriched = aircraft_data.copy()
        
        icao24 = aircraft_data.get('icao24', '').upper()
        if not icao24:
            return enriched
            
        db_info = self.get_aircraft_by_icao24(icao24)
        if db_info:
            # Add registration
            if db_info.get('reg') and db_info['reg'] != 'NULL' and isinstance(db_info['reg'], str):
                enriched['registration'] = db_info['reg']
            
            # Add owner/operator
            if db_info.get('ownop') and db_info['ownop'] != 'NULL' and isinstance(db_info['ownop'], str):
                enriched['airline'] = db_info['ownop']
            
            # Add aircraft type if available
            if db_info.get('icaotype') and db_info['icaotype'] != 'NULL' and isinstance(db_info['icaotype'], str) and db_info['icaotype'].strip():
                enriched['aircraft_type'] = db_info['icaotype']
            elif db_info.get('model') and db_info['model'] != 'NULL' and isinstance(db_info['model'], str) and db_info['model'].strip():
                enriched['aircraft_type'] = db_info['model']
            elif db_info.get('short_type') and db_info['short_type'] != 'NULL' and isinstance(db_info['short_type'], str) and db_info['short_type'].strip():
                enriched['aircraft_type'] = db_info['short_type']
            
            # Add manufacturer if available
            if db_info.get('manufacturer') and db_info['manufacturer'] != 'NULL':
                if enriched.get('aircraft_type'):
                    enriched['aircraft_type'] = f"{db_info['manufacturer']} {enriched['aircraft_type']}"
                else:
                    enriched['aircraft_type'] = db_info['manufacturer']
            
            # Add year if available
            if db_info.get('year') and db_info['year'] != 'NULL':
                enriched['year'] = db_info['year']
            
            # Add military flag
            if db_info.get('mil') is True:
                enriched['military'] = True
        
        return enriched
    
    def search_by_registration(self, registration: str) -> Optional[str]:
        """
        Search for ICAO24 by registration.
        
        Returns:
            ICAO24 code if found, None otherwise
        """
        db_info = self.get_aircraft_by_registration(registration)
        return db_info.get('icao') if db_info else None
    
    def get_database_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        if not self._loaded:
            self.load_database()
            
        return {
            "loaded": self._loaded,
            "total_icao_entries": len(self._icao_lookup),
            "total_registration_entries": len(self._registration_lookup),
            "database_file": self.db_file_path
        }

# Global database service instance
_aircraft_db_service: Optional[AircraftDatabaseService] = None

def get_aircraft_db_service() -> AircraftDatabaseService:
    """Get the global aircraft database service instance."""
    global _aircraft_db_service
    if _aircraft_db_service is None:
        _aircraft_db_service = AircraftDatabaseService()
        _aircraft_db_service.load_database()
    return _aircraft_db_service
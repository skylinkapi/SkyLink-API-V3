"""
Colombia Aerocivil Scraper
Fetches aerodrome charts from Colombia's eAIP directory structure.
"""

import requests
from bs4 import BeautifulSoup
from typing import List, Dict
import urllib3

# Disable SSL warnings for the Colombia site
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class ColombiaScraper:
    """Scraper for Colombia Aerocivil aerodrome charts."""
    
    BASE_URL = "https://eaip-colombia.atnaerocivil.gov.co/eaip/A%2069-25_2025_10_02/documents/Root_WePub/Colombia/CHARTS/AD/{icao_code}/NEW/"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def get_charts(self, icao_code: str) -> List[Dict[str, str]]:
        """
        Fetch aerodrome charts for a Colombian airport.
        
        Args:
            icao_code: ICAO code of the airport (e.g., 'SKBO', 'SKCL')
            
        Returns:
            List of chart dictionaries with 'name', 'url', and 'type' keys
        """
        icao_code = icao_code.upper()
        url = self.BASE_URL.format(icao_code=icao_code)
        
        try:
            response = self.session.get(url, timeout=30, verify=False)
            response.raise_for_status()
        except requests.RequestException as e:
            print(f"Error fetching data for {icao_code}: {e}")
            return []
        
        soup = BeautifulSoup(response.content, 'html.parser')
        charts = []
        
        # Find all links in the directory listing
        links = soup.find_all('a')
        
        for link in links:
            href = link.get('href', '')
            filename = link.get_text(strip=True)
            
            # Skip parent directory and non-PDF files
            if not href or href == '../' or 'Parent Directory' in filename:
                continue
            
            # Only process PDF files
            if not href.lower().endswith('.pdf'):
                continue
            
            # Build full URL
            chart_url = url + href
            
            # Categorize based on filename prefix
            chart_type = self._categorize_chart(filename)
            
            charts.append({
                'name': filename.replace('.pdf', ''),
                'url': chart_url,
                'type': chart_type
            })
        
        return charts
    
    def _categorize_chart(self, filename: str) -> str:
        """Categorize chart based on filename prefix."""
        filename_lower = filename.lower()
        
        # Check for explicit type prefixes in filename
        if filename_lower.startswith('sid '):
            return 'sid'
        
        if filename_lower.startswith('star '):
            return 'star'
        
        if filename_lower.startswith('iac '):
            return 'approach'
        
        if filename_lower.startswith('vac '):
            return 'approach'
        
        # Ground movement and airport diagrams
        if any(keyword in filename_lower for keyword in [
            'aerodrome ground mov', 'ground mov',
            'aerodrome heliport', 'heliport chart',
            'aircraft parking', 'parking',
            'aerodrome taxying', 'taxying',
            'aerodrome chart', 'airport chart'
        ]):
            return 'airport_diagram'
        
        # Obstacle and precision approach terrain charts
        if any(keyword in filename_lower for keyword in [
            'aerodrome obstacle', 'obstacle chart',
            'aerodrome precision', 'precision approach terrain',
            'aerodrome critical', 'critical area',
            'aerodrome sensitive', 'sensitive area'
        ]):
            return 'airport_diagram'
        
        # Minimum altitude and vectoring charts (informational)
        if any(keyword in filename_lower for keyword in [
            'minimum area altitude', 'minimum vectoring',
            'control zone', 'visibility chart',
            'wpt coordinates'
        ]):
            return 'airport_diagram'
        
        # Default to airport_diagram for unclear cases
        return 'airport_diagram'

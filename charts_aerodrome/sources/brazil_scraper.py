"""
Brazil DECEA (Departamento de Controle do Espaço Aéreo) Scraper
Fetches aerodrome charts from Brazil's official aeronautical information system.
"""

import requests
from bs4 import BeautifulSoup
import re
from typing import List, Dict


class BrazilScraper:
    """Scraper for Brazil DECEA aerodrome charts."""
    
    BASE_URL = "https://aisweb.decea.mil.br"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def get_charts(self, icao_code: str) -> List[Dict[str, str]]:
        """
        Fetch aerodrome charts for a Brazilian airport.
        
        Args:
            icao_code: ICAO code of the airport (e.g., 'SBGR', 'SBSP')
            
        Returns:
            List of chart dictionaries with 'name', 'url', and 'type' keys
        """
        icao_code = icao_code.upper()
        url = f"{self.BASE_URL}/?i=aerodromos&codigo={icao_code}"
        
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
        except requests.RequestException as e:
            print(f"Error fetching data for {icao_code}: {e}")
            return []
        
        soup = BeautifulSoup(response.content, 'html.parser')
        charts = []
        
        # Chart section mapping
        sections = {
            'ADC': 'airport_diagram',      # Aerodrome Chart
            'AGMC': 'airport_diagram',     # Ground Movement Chart  
            'AOC': 'airport_diagram',      # Obstacle Chart
            'IAC': 'approach',             # Instrument Approach Chart
            'PDC': 'airport_diagram',      # Procedures
            'SID': 'sid',                  # Standard Instrument Departure
            'STAR': 'star',                # Standard Terminal Arrival
            'VAC': 'approach'              # Visual Approach Chart
        }
        
        # Find all chart sections
        for section_name, chart_type in sections.items():
            # Find the section header
            section_header = soup.find('h4', string=section_name)
            if not section_header:
                continue
            
            # Get the parent container that holds the links
            section_container = section_header.find_next_sibling()
            if not section_container:
                continue
            
            # Find all chart links in this section
            chart_links = section_container.find_all('a', href=True)
            
            for link in chart_links:
                chart_name = link.get_text(strip=True)
                chart_url = link['href']
                
                # Skip empty names or non-chart links
                if not chart_name or 'download' not in chart_url:
                    continue
                
                # Make URL absolute if needed
                if not chart_url.startswith('http'):
                    chart_url = self.BASE_URL + chart_url
                
                charts.append({
                    'name': f"{section_name} - {chart_name}",
                    'url': chart_url,
                    'type': chart_type
                })
        
        return charts

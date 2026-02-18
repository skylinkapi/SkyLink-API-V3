"""
Kazakhstan ANS Scraper
Fetches aerodrome charts from Kazakhstan's ANS eAIP system.
Based on https://www.ans.kz/AIP/eAIP/
"""

import requests
import re
from typing import List, Dict
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote


class KazakhstanScraper:
    """Scraper for Kazakhstan ANS aerodrome charts."""
    
    BASE_URL = "https://www.ans.kz"
    # URL pattern with AIRAC cycle date
    AIP_URL_PATTERN = "/AIP/eAIP/2025-11-27-AIRAC/html/eAIP/UA-AD-2.{icao}-en-GB.html"
    GRAPHICS_BASE = "/AIP/eAIP/2025-11-27-AIRAC/graphics/eAIP/"
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def get_charts(self, icao_code: str) -> List[Dict[str, str]]:
        """
        Fetch aerodrome charts for a Kazakhstan airport.
        
        Args:
            icao_code: ICAO code of the airport (e.g., 'UAAA', 'UAKK')
            
        Returns:
            List of chart dictionaries with 'name', 'url', and 'type' keys
        """
        icao_code = icao_code.upper()
        
        try:
            if self.verbose:
                print(f"Fetching Kazakhstan eAIP for {icao_code}...")
            
            # Build the URL
            url = f"{self.BASE_URL}{self.AIP_URL_PATTERN.format(icao=icao_code)}"
            
            if self.verbose:
                print(f"URL: {url}")
            
            # Get the page
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            # Parse HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find the charts table (last table with PDF links)
            tables = soup.find_all('table')
            chart_table = None
            
            # Find the table with the most PDF links (the charts table)
            max_pdfs = 0
            for table in tables:
                pdf_count = len(table.find_all('a', href=lambda x: x and '.pdf' in x.lower()))
                if pdf_count > max_pdfs:
                    max_pdfs = pdf_count
                    chart_table = table
            
            if not chart_table:
                if self.verbose:
                    print("No chart table found")
                return []
            
            if self.verbose:
                print(f"Found chart table with {max_pdfs} PDFs")
            
            # Parse the table to extract chart names and PDF links
            charts = []
            rows = chart_table.find_all('tr')
            
            # Track the current chart name (for rowspan handling)
            current_chart_name = None
            
            for row in rows[1:]:  # Skip header row
                cells = row.find_all('td')
                if not cells:
                    continue
                
                # Check if this row has a chart name (first cell with rowspan)
                first_cell = cells[0]
                
                # Look for PDF link in this row
                pdf_link = row.find('a', href=lambda x: x and '.pdf' in x.lower())
                
                # If first cell has text and no PDF link, it's a chart name row
                cell_text = first_cell.get_text(strip=True)
                
                if cell_text and not pdf_link:
                    # This is a name row
                    current_chart_name = cell_text
                elif pdf_link and current_chart_name:
                    # This is a PDF row, use the current chart name
                    href = pdf_link.get('href')
                    
                    # Build full URL with proper encoding
                    if href.startswith('../'):
                        # Remove one level of ../
                        href = href.replace('../', '', 1)
                        filename = href.split('/')[-1]
                        # Encode the filename to handle spaces
                        encoded_filename = quote(filename)
                        full_url = f"{self.BASE_URL}{self.GRAPHICS_BASE}{encoded_filename}"
                    elif href.startswith('../../'):
                        # Remove two levels
                        filename = href.split('/')[-1]
                        encoded_filename = quote(filename)
                        full_url = f"{self.BASE_URL}{self.GRAPHICS_BASE}{encoded_filename}"
                    else:
                        full_url = urljoin(url, href)
                    
                    # Categorize the chart using the actual chart name
                    chart_type = self._categorize_chart(current_chart_name, href)
                    
                    charts.append({
                        'name': current_chart_name,
                        'url': full_url,
                        'type': chart_type
                    })
            
            return charts
            
        except requests.exceptions.RequestException as e:
            if self.verbose:
                print(f"Error fetching data for {icao_code}: {e}")
            return []
    
    
    def _categorize_chart(self, name: str, filename: str) -> str:
        """
        Categorize a chart based on its name and filename.
        
        Args:
            name: Chart name
            filename: Chart filename
            
        Returns:
            Chart type: 'general', 'airport_diagram', 'sid', 'star', or 'approach'
        """
        name_lower = name.lower()
        filename_lower = filename.lower()
        combined = f"{name_lower} {filename_lower}"
        
        # SID (Standard Instrument Departure)
        if any(keyword in combined for keyword in [
            'sid', 'departure', 'dep', 'standard departure', 'instrument departure'
        ]):
            return 'sid'
        
        # STAR (Standard Terminal Arrival Route)
        if any(keyword in combined for keyword in [
            'star', 'arrival', 'arr', 'standard arrival', 'instrument arrival'
        ]):
            return 'star'
        
        # Approach charts
        if any(keyword in combined for keyword in [
            'approach', 'app', 'iac', 'ils', 'vor', 'ndb', 'rnav', 'rnp', 
            'landing', 'final', 'precision', 'non-precision'
        ]):
            return 'approach'
        
        # Airport/Ground charts
        if any(keyword in combined for keyword in [
            'aerodrome', 'airport', 'ground', 'parking', 'taxi', 'stand',
            'apron', 'movement', 'agc', 'adc'
        ]):
            return 'airport_diagram'
        
        # Default to general
        return 'general'


if __name__ == '__main__':
    # Test the scraper
    import sys
    
    icao = sys.argv[1] if len(sys.argv) > 1 else 'UAAA'  # Almaty
    
    scraper = KazakhstanScraper(verbose=True)
    charts = scraper.get_charts(icao)
    
    print(f"\nFound {len(charts)} charts:")
    for chart in charts:
        print(f"  {chart['type']}: {chart['name']}")
        print(f"    {chart['url']}")

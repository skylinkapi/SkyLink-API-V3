"""
Russia CAIGA Scraper
Fetches aerodrome charts from Russia's CAIGA AIP system.
Based on http://www.caiga.ru/common/AirInter/validaip/html/menueng.htm
"""

import requests
import re
from typing import List, Dict
from bs4 import BeautifulSoup


class RussiaScraper:
    """Scraper for Russia CAIGA aerodrome charts."""
    
    BASE_URL = "http://www.caiga.ru"
    MENU_URL_RUS = "/common/AirInter/validaip/html/menurus.htm"
    MENU_URL_ENG = "/common/AirInter/validaip/html/menueng.htm"
    
    def __init__(self, verbose: bool = False, use_english: bool = True):
        self.verbose = verbose
        self.use_english = use_english
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def get_charts(self, icao_code: str) -> List[Dict[str, str]]:
        """
        Fetch aerodrome charts for a Russian airport.
        
        Args:
            icao_code: ICAO code of the airport (e.g., 'UUEE', 'UWWW')
            
        Returns:
            List of chart dictionaries with 'name', 'url', and 'type' keys
        """
        icao_code = icao_code.upper()
        
        try:
            return self._get_charts_from_web(icao_code)
        except Exception as e:
            if self.verbose:
                print(f"Error fetching data for {icao_code}: {e}")
            return []
    
    def _get_charts_from_web(self, icao_code: str) -> List[Dict[str, str]]:
        """Fetch charts from the CAIGA website."""
        if self.verbose:
            print(f"Fetching CAIGA menu...")
        
        # Choose menu based on language preference
        menu_url = self.MENU_URL_ENG if self.use_english else self.MENU_URL_RUS
        
        # Get the menu content
        response = self.session.get(f"{self.BASE_URL}{menu_url}", timeout=30)
        response.raise_for_status()
        
        # Parse the menu HTML
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find the script tag containing the menu
        script_content = None
        for script in soup.find_all('script'):
            if script.string and 'ItemBegin' in script.string:
                script_content = script.string
                break
        
        if not script_content:
            if self.verbose:
                print("Could not find menu script")
            return []
        
        # Parse the script content
        airports = self._parse_menu(script_content)
        
        if self.verbose:
            print(f"Parsed {len(airports)} airports")
        
        # Find the requested airport
        if icao_code not in airports:
            if self.verbose:
                print(f"Airport {icao_code} not found in menu")
            return []
        
        airport_data = airports[icao_code]
        
        if self.verbose:
            print(f"Found airport with {len(airport_data['charts'])} charts")
        
        # Convert to our chart format
        charts = []
        for title, (url, _filename) in airport_data['charts'].items():
            # The menu is at /common/AirInter/validaip/html/menurus.htm
            # Relative URLs like ../aip/... mean /common/AirInter/validaip/aip/...
            full_url = f"{self.BASE_URL}/common/AirInter/validaip/{url.replace('../', '')}"
            chart_type = self._categorize_chart(title, url)
            
            charts.append({
                'name': title,
                'url': full_url,
                'type': chart_type
            })
        
        return charts
    
    def _parse_menu(self, script_content: str) -> Dict[str, Dict]:
        """
        Parse the JavaScript menu structure to extract airport data.
        
        Args:
            script_content: JavaScript content with ItemBegin/ItemEnd/ItemLink calls
            
        Returns:
            Dictionary mapping ICAO codes to airport data
        """
        airports = {}
        
        in_ad2_section = False
        current_code = None
        current_name = None
        current_charts = {}
        
        for line in script_content.split('\n'):
            line = line.strip()
            
            # Check for AD 2. Аэродромы / AD 2. Aerodromes section
            if 'ItemBegin' in line and 'AD 2' in line and ('Аэродром' in line or 'Aerodrome' in line):
                in_ad2_section = True
                if self.verbose:
                    print("Found AD 2 Aerodromes section")
                continue
            
            # Stop at AD 3 or AD 4
            if in_ad2_section and 'ItemBegin' in line and ('AD 3' in line or 'AD 4' in line):
                in_ad2_section = False
                if self.verbose:
                    print("Left AD 2 section")
                continue
            
            if not in_ad2_section:
                continue
            
            # Parse ItemBegin for airport
            if 'ItemBegin' in line:
                # Extract: ItemBegin("5159", "","UUEE. МОСКВА (ШЕРЕМЕТЬЕВО)");
                match = re.search(r'ItemBegin\("(\d+)",\s*"[^"]*",\s*"([^"]+)"\);', line)
                if match:
                    title = match.group(2)
                    # Check if this is an airport entry (format: "XXXX. NAME")
                    if len(title) > 4 and title[4] == '.':
                        current_code = title[:4]
                        current_name = title[6:].strip()
                        current_charts = {}
                        # Don't print Cyrillic characters that may cause encoding issues
                continue
            
            # Parse ItemLink
            if 'ItemLink' in line and current_code:
                # Extract: ItemLink("../aip/ad/ad2/uuee/1-ad2-rus-uuee-txt.pdf","DATA, TEXTS, TABLES");
                match = re.search(r'ItemLink\("([^"]+)",\s*"([^"]+)"\);', line)
                if match:
                    href = match.group(1)
                    title = match.group(2)
                    
                    # Include DATA, TEXTS, TABLES entries
                    
                    # Clean up title - remove number prefix like "(31)"
                    title = re.sub(r'^\(\d+\)\s*', '', title)
                    
                    filename = f"{current_code} - {title.replace('.', '')}.pdf"
                    current_charts[title] = (href, filename)
                continue
            
            # Parse ItemEnd
            if 'ItemEnd' in line and current_code:
                # Save the airport data
                airports[current_code] = {
                    'name': current_name,
                    'charts': current_charts
                }
                current_code = None
                current_name = None
                current_charts = {}
                continue
        
        return airports
    
    def _categorize_chart(self, name: str, url: str) -> str:
        """
        Categorize a chart based on its name and URL.
        
        Args:
            name: Chart name
            url: Chart URL
            
        Returns:
            Chart type: 'general', 'airport_diagram', 'sid', 'star', or 'approach'
        """
        name_lower = name.lower()
        url_lower = url.lower()
        combined = f"{name_lower} {url_lower}"
        
        # Keywords for chart types (Russian and English)
        # SID (Standard Instrument Departure)
        if any(keyword in combined for keyword in [
            'sid', 'сид', 'вылет', 'departure', 'стандартного вылета',
            'standard departure'
        ]):
            return 'sid'
        
        # STAR (Standard Terminal Arrival Route)
        if any(keyword in combined for keyword in [
            'star', 'стар', 'прилёт', 'прилет', 'arrival', 'стандартного прибытия',
            'standard arrival'
        ]):
            return 'star'
        
        # Approach charts
        if any(keyword in combined for keyword in [
            'approach', 'захода на посадку', 'заход', 'iac', 'ils', 'vor', 'ndb', 
            'rnav', 'rnp', 'gls', 'instrument approach', 'visual approach',
            'визуального захода', 'precision approach'
        ]):
            return 'approach'
        
        # Airport/Ground charts
        if any(keyword in combined for keyword in [
            'карта аэродрома', 'аэродромного наземного движения', 'ground', 'parking', 
            'стоянк', 'стыковки воздушных судов', 'движение', 'aerodrome chart',
            'ground movement', 'aircraft parking', 'docking', 'safedock', 'stands'
        ]):
            return 'airport_diagram'
        
        # Default to general
        return 'general'


if __name__ == '__main__':
    # Test the scraper
    import sys
    
    icao = sys.argv[1] if len(sys.argv) > 1 else 'UUEE'  # Moscow Sheremetyevo
    
    scraper = RussiaScraper(verbose=True)
    charts = scraper.get_charts(icao)
    
    print(f"\nFound {len(charts)} items:")
    for chart in charts:
        print(f"  {chart['type']}: {chart['name']}")
        print(f"    {chart['url']}")
        if 'note' in chart:
            print(f"    Note: {chart['note']}")


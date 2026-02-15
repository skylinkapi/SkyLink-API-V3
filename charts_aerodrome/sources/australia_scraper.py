"""
Australian Airport Charts Scraper
Scrapes aerodrome charts from Airservices Australia AIP
"""

import requests
from bs4 import BeautifulSoup
import re
from typing import List, Dict


class AustraliaScraper:
    """Scraper for Australian aerodrome charts from Airservices Australia"""
    
    BASE_URL = "https://www.airservicesaustralia.com"
    AIP_URL = f"{BASE_URL}/aip/aip.asp"
    
    def __init__(self, verbose=False):
        self.verbose = verbose
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self._agreed = False
        self._latest_date = None
    
    def _log(self, message):
        """Print message if verbose mode is enabled"""
        if self.verbose:
            print(f"[DEBUG] {message}")
    
    def _accept_terms(self):
        """Accept the terms and conditions to access the AIP"""
        if self._agreed:
            return True
        
        self._log("Accepting AIP terms and conditions...")
        
        try:
            # Post to accept terms
            response = self.session.post(
                self.AIP_URL,
                data={'Submit': 'I Agree', 'check': '1'},
                params={'pg': '10'},
                timeout=30
            )
            response.raise_for_status()
            self._agreed = True
            self._log("Terms accepted successfully")
            return True
        except requests.RequestException as e:
            print(f"Error accepting terms: {e}")
            return False
    
    def _get_latest_aip_date(self):
        """Get the latest AIP date from page 10 (ERSA links contain vdate parameter)"""
        if self._latest_date:
            return self._latest_date
        
        if not self._accept_terms():
            return None
        
        self._log("Fetching latest AIP date from page 10...")
        
        try:
            # Get page 10 which contains links with vdate parameter
            response = self.session.get(f"{self.AIP_URL}?pg=10", timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'lxml')
            
            # Look for links with vdate parameter like "aip.asp?pg=40&vdate=27NOV2025&ver=1"
            # These indicate the current AIP effective date
            vdate_pattern = re.compile(r'vdate=(\d{1,2}[A-Z]{3}\d{4})', re.IGNORECASE)
            
            dates_found = []
            for link in soup.find_all('a', href=True):
                href = link['href']
                match = vdate_pattern.search(href)
                if match:
                    date_str = match.group(1).upper()
                    # Ensure day is 2 digits
                    if len(date_str) == 8:  # e.g., "1NOV2025" -> "01NOV2025"
                        date_str = '0' + date_str
                    dates_found.append(date_str)
            
            if dates_found:
                # Use the first (current) date found
                self._latest_date = dates_found[0]
                self._log(f"Found latest AIP date: {self._latest_date}")
                return self._latest_date
            
            self._log("Could not find vdate in any links on page 10")
            return None
            
        except requests.RequestException as e:
            print(f"Error getting AIP date: {e}")
            return None
    
    def _get_dap_page(self):
        """Get the Departure and Approach Procedures (DAP) page"""
        aip_date = self._get_latest_aip_date()
        if not aip_date:
            self._log("Could not determine AIP date, cannot fetch DAP page")
            return None
        
        self._log("Navigating to DAP page...")
        
        try:
            # Construct DAP URL with dynamic date: /aip/pending/dap/dap_{DDMMMYYYY}.htm
            dap_url = f"{self.BASE_URL}/aip/pending/dap/dap_{aip_date}.htm"
            self._log(f"Using DAP URL: {dap_url}")
            response = self.session.get(dap_url, timeout=30)
            response.raise_for_status()
            return response
            
        except requests.RequestException as e:
            print(f"Error getting DAP page: {e}")
            return None
    
    def _find_airport_in_dap(self, icao_code: str):
        """Find the airport in the DAP listing"""
        dap_response = self._get_dap_page()
        if not dap_response:
            return []
        
        soup = BeautifulSoup(dap_response.content, 'lxml')
        icao_upper = icao_code.upper()
        
        self._log(f"Searching for {icao_upper} in DAP...")
        
        # Australian airports are listed with h3 headings like:
        # "SYDNEY/KINGSFORD SMITH (YSSY)"
        # Find the h3 that contains our ICAO code
        target_h3 = None
        for h3 in soup.find_all('h3'):
            h3_text = h3.get_text().strip()
            if f'({icao_upper})' in h3_text:
                target_h3 = h3
                self._log(f"Found airport heading: {h3_text}")
                break
        
        if not target_h3:
            self._log(f"No heading found for {icao_upper}")
            return []
        
        # Get the table immediately following this h3
        charts_table = target_h3.find_next('table')
        if not charts_table:
            self._log("No charts table found after airport heading")
            return []
        
        charts = []
        # Find all chart links in the table
        for link in charts_table.find_all('a', href=True):
            href = link['href']
            chart_name = link.get_text(strip=True)
            
            if not chart_name or '.pdf' not in href.lower():
                continue
            
            # Make URL absolute
            # PDFs are in /aip/pending/dap/ folder
            if not href.startswith('http'):
                base_url = f"{self.BASE_URL}/aip/pending/dap/"
                chart_url = base_url + href
            else:
                chart_url = href
            
            charts.append({
                'name': chart_name,
                'url': chart_url,
                'type': self._categorize_chart(chart_name)
            })
        
        return charts
    
    def _categorize_chart(self, chart_name: str) -> str:
        """Categorize chart based on its name"""
        name_lower = chart_name.lower()
        
        # SID - Standard Instrument Departure
        if 'sid' in name_lower or 'departure' in name_lower:
            return 'sid'
        
        # STAR - Standard Terminal Arrival
        if 'star' in name_lower or 'arrival' in name_lower:
            return 'star'
        
        # Approach charts
        if any(keyword in name_lower for keyword in ['approach', 'ils', 'rnav', 'vor', 'ndb', 'gnss', 'visual']):
            return 'approach'
        
        # Ground/Airport diagrams
        if any(keyword in name_lower for keyword in ['parking', 'taxi', 'aerodrome chart', 'airport diagram']):
            return 'airport_diagram'
        
        # Default to airport_diagram for unclassified
        return 'airport_diagram'
    
    def get_charts(self, icao_code: str) -> List[Dict[str, str]]:
        """
        Fetch aerodrome charts for an Australian airport.
        
        Args:
            icao_code: ICAO code of the airport (e.g., 'YSSY', 'YMML')
            
        Returns:
            List of chart dictionaries with 'name', 'url', and 'type' keys
        """
        icao_code = icao_code.upper()
        
        # Validate Australian ICAO code (starts with Y)
        if not icao_code.startswith('Y'):
            self._log(f"{icao_code} doesn't appear to be an Australian airport code")
            return []
        
        self._log(f"Fetching charts for {icao_code}...")
        
        try:
            charts = self._find_airport_in_dap(icao_code)
            self._log(f"Found {len(charts)} charts for {icao_code}")
            return charts
        except Exception as e:
            print(f"Error fetching charts for {icao_code}: {e}")
            return []

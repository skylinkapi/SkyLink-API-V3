"""
Canadian Airport Charts Scraper (FltPlan.com)
Scrapes aerodrome charts from FltPlan.com for Canadian airports

Uses FltPlan.com authentication to access current chart listings.
"""

import requests
from bs4 import BeautifulSoup
import re
from typing import List, Dict, Optional
from urllib.parse import parse_qs, urlparse


# FltPlan.com credentials
FLTPLAN_USERNAME = "skylinka"
FLTPLAN_PASSWORD = "Lavender1-Confetti2-Skimmed7-Imprison6-Poison4"


class CanadaScraper:
    """Scraper for Canadian aerodrome charts from FltPlan.com"""
    
    BASE_URL = "https://www.fltplan.com"
    IMAGE_SERVER = "https://imageserver.fltplan.com"
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self._crn10 = None
        self._username = None
        self._merge_folder = None
        self._logged_in = False
    
    def _log(self, message: str):
        """Print message if verbose mode is enabled"""
        if self.verbose:
            print(f"[DEBUG] {message}")
    
    def _login(self) -> bool:
        """Login to FltPlan.com and get session tokens"""
        if self._logged_in:
            return True
        
        self._log("Logging in to FltPlan.com...")
        
        login_data = {
            'username': FLTPLAN_USERNAME,
            'password': FLTPLAN_PASSWORD
        }
        
        login_url = f"{self.BASE_URL}/AwRegUserCk.exe?a=1"
        
        try:
            r = self.session.post(login_url, data=login_data, timeout=30)
            
            if r.status_code != 200:
                self._log(f"Login failed with status {r.status_code}")
                return False
            
            # Extract CRN10 and CARRYUNAME from response
            soup = BeautifulSoup(r.text, 'html.parser')
            
            for inp in soup.find_all('input'):
                name = inp.get('name', '').upper()
                value = inp.get('value', '')
                if name == 'CRN10' and value:
                    self._crn10 = value
                elif name == 'CARRYUNAME' and value:
                    self._username = value
            
            if self._crn10 and self._username:
                self._logged_in = True
                self._log(f"Logged in as {self._username}")
                return True
            else:
                self._log("Failed to get authentication tokens")
                return False
                
        except Exception as e:
            self._log(f"Login error: {e}")
            return False
    
    def _get_merge_folder(self, icao_code: str) -> Optional[str]:
        """Get the current merge folder name by fetching a chart display page"""
        if self._merge_folder:
            return self._merge_folder
        
        self._log("Detecting current merge folder...")
        
        # Get chart list for the airport
        list_url = f"{self.BASE_URL}/AwListAppPlates.exe?a=1"
        list_data = {
            'CRN10': self._crn10,
            'CARRYUNAME': self._username,
            'MODE': 'SEARCH',
            'AIRPORTSEL': icao_code
        }
        
        try:
            r = self.session.post(list_url, data=list_data, timeout=30)
            soup = BeautifulSoup(r.text, 'html.parser')
            
            # Find first chart link
            for link in soup.find_all('a', href=True):
                href = link['href']
                if 'AwDisplayAppChart.exe' in href and 'TYPECHART' in href:
                    # Follow this link to get the image URL
                    chart_url = href if href.startswith('http') else f"{self.BASE_URL}/{href}"
                    r2 = self.session.get(chart_url, timeout=30)
                    
                    # Extract merge folder from image URL
                    match = re.search(r'imageserver\.fltplan\.com/merge/Canada/(merge\d+)/', r2.text)
                    if match:
                        self._merge_folder = match.group(1)
                        self._log(f"Found merge folder: {self._merge_folder}")
                        return self._merge_folder
            
            self._log("Could not find merge folder")
            return None
            
        except Exception as e:
            self._log(f"Error getting merge folder: {e}")
            return None
    
    def _categorize_chart(self, chart_name: str) -> str:
        """Categorize chart based on name"""
        name_upper = chart_name.upper()
        
        # STAR charts (arrivals)
        if 'ARR' in name_upper or 'STAR' in name_upper:
            return 'STAR'
        
        # SID charts (departures)
        if 'DEP' in name_upper or 'SID' in name_upper:
            return 'SID'
        
        # Approach charts
        if any(kw in name_upper for kw in ['ILS', 'RNAV', 'VOR', 'NDB', 'LOC', 'RNP', 'APCH', 'APP']):
            return 'Approach'
        
        # Ground charts
        if any(kw in name_upper for kw in ['TAXI', 'GROUND', 'PARKING', 'APRON', 'ADC', 'AERODROME']):
            return 'Airport Diagram'
        
        # General
        return 'General'
    
    def get_charts(self, icao_code: str, extract_pdfs: bool = True) -> List[Dict[str, str]]:
        """
        Fetch aerodrome charts for a given ICAO code.
        
        Args:
            icao_code: 4-letter ICAO code (e.g., 'CYYZ')
            extract_pdfs: Ignored (kept for API compatibility with old scraper)
            
        Returns:
            List of dictionaries with 'name', 'url', and 'type' keys
        """
        icao_code = icao_code.upper().strip()
        charts = []
        
        # Login first
        if not self._login():
            print(f"Failed to login to FltPlan.com")
            return []
        
        # Get the current merge folder
        merge_folder = self._get_merge_folder(icao_code)
        if not merge_folder:
            print(f"Failed to get merge folder for {icao_code}")
            return []
        
        self._log(f"Fetching chart list for {icao_code}...")
        
        # Get chart list
        list_url = f"{self.BASE_URL}/AwListAppPlates.exe?a=1"
        list_data = {
            'CRN10': self._crn10,
            'CARRYUNAME': self._username,
            'MODE': 'SEARCH',
            'AIRPORTSEL': icao_code
        }
        
        try:
            r = self.session.post(list_url, data=list_data, timeout=30)
            soup = BeautifulSoup(r.text, 'html.parser')
            
            # Find all chart links
            seen_charts = set()
            
            for link in soup.find_all('a', href=True):
                href = link['href']
                
                if 'AwDisplayAppChart.exe' in href and 'TYPECHART' in href:
                    # Extract chart filename from TYPECHART parameter
                    parsed = urlparse(href)
                    params = parse_qs(parsed.query)
                    
                    if 'TYPECHART' in params:
                        chart_filename = params['TYPECHART'][0]
                        
                        # Skip duplicates
                        if chart_filename in seen_charts:
                            continue
                        seen_charts.add(chart_filename)
                        
                        # Get chart name from link text
                        chart_name = link.get_text(strip=True) or chart_filename.replace('.pdf', '').replace('_', ' ')
                        
                        # Construct PDF URL
                        pdf_url = f"{self.IMAGE_SERVER}/merge/Canada/{merge_folder}/Single/{chart_filename}"
                        
                        charts.append({
                            'name': chart_name,
                            'url': pdf_url,
                            'type': self._categorize_chart(chart_name)
                        })
            
            self._log(f"Found {len(charts)} charts for {icao_code}")
            return charts
            
        except Exception as e:
            print(f"Error fetching charts for {icao_code}: {e}")
            return []


def get_aerodrome_charts(icao_code: str, verbose: bool = False) -> List[Dict[str, str]]:
    """
    Convenience function to get charts for a Canadian airport.
    
    Args:
        icao_code: 4-letter ICAO code (e.g., 'CYYZ')
        verbose: Enable verbose output
        
    Returns:
        List of chart dictionaries with 'name', 'url', and 'type' keys
    """
    scraper = CanadaScraper(verbose=verbose)
    return scraper.get_charts(icao_code)


# For testing
if __name__ == "__main__":
    import sys
    
    icao = sys.argv[1] if len(sys.argv) > 1 else "CYYZ"
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    
    print(f"Fetching charts for {icao}...")
    
    charts = get_aerodrome_charts(icao, verbose=verbose)
    
    if charts:
        print(f"\nFound {len(charts)} chart(s):")
        for chart in charts[:30]:  # Show first 30
            print(f"  [{chart.get('type', 'N/A')}] {chart['name']}")
            print(f"    URL: {chart['url']}")
        
        if len(charts) > 30:
            print(f"\n  ... and {len(charts) - 30} more charts")
    else:
        print("No charts found.")

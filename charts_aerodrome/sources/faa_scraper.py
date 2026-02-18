"""
FAA Chart Scraper
Scrapes aerodrome chart information from the FAA website
"""

import requests
from bs4 import BeautifulSoup
from typing import List, Dict


class FAAScraper:
    """Scraper for FAA aerodrome charts"""
    
    BASE_URL = "https://nfdc.faa.gov/nfdcApps/services/ajv5/airportDisplay.jsp"
    
    def __init__(self, verbose=False):
        self.verbose = verbose
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def _log(self, message):
        """Print message if verbose mode is enabled"""
        if self.verbose:
            print(f"[DEBUG] {message}")
    
    def get_charts(self, airport_code: str) -> List[Dict[str, str]]:
        """
        Fetch all charts for a given airport code
        
        Args:
            airport_code: ICAO airport code (e.g., KJFK)
            
        Returns:
            List of dictionaries containing chart name and URL
        """
        # Remove 'K' prefix if present (FAA uses 3-letter codes)
        if airport_code.startswith('K') and len(airport_code) == 4:
            search_code = airport_code[1:]
        else:
            search_code = airport_code
        
        self._log(f"Searching for airport: {search_code}")
        
        # Build URL
        url = f"{self.BASE_URL}?airportId={search_code}"
        self._log(f"Fetching: {url}")
        
        try:
            # Fetch page
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            # Parse HTML
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Check if airport was found
            error_elem = soup.find('strong', string=lambda s: s and 'Airport Not Found' in s)
            if error_elem:
                raise ValueError(f"Airport {airport_code} not found in FAA database")
            
            charts = []
            
            # Find the charts section
            charts_section = soup.find('div', id='charts')
            if not charts_section:
                self._log("No charts section found")
                return charts
            
            # Extract airport diagram (look for it in the main charts section)
            # It's usually in a div with class="chartLink" or directly as a link
            diagram_link = charts_section.find('a', class_='chartLink')
            if diagram_link and diagram_link.get('href'):
                charts.append({
                    'name': f"{airport_code} - Airport Diagram",
                    'url': diagram_link['href'],
                    'type': 'airport_diagram'
                })
                self._log(f"Found airport diagram: {diagram_link['href']}")
            
            # Also try to find it in the General section
            general_section = charts_section.find('h3', string=lambda s: s and 'General' in s)
            if general_section:
                gen_parent = general_section.parent
                gen_links = gen_parent.find_all('a')
                for link in gen_links:
                    if link.get('href') and link.text.strip():
                        link_text = link.text.strip()
                        # Check if it's an airport diagram
                        if 'airport diagram' in link_text.lower() or 'APD' in link_text:
                            charts.append({
                                'name': link_text,
                                'url': link['href'],
                                'type': 'airport_diagram'
                            })
                            self._log(f"Found airport diagram in General: {link_text}")
                        else:
                            charts.append({
                                'name': link_text,
                                'url': link['href'],
                                'type': 'general'
                            })
                            self._log(f"Found General chart: {link_text}")
            
            # Extract STAR charts
            star_section = charts_section.find('h3', string=lambda s: s and 'Standard Terminal Arrival (STAR)' in s)
            if star_section:
                star_parent = star_section.parent
                star_links = star_parent.find_all('a')
                for link in star_links:
                    if link.get('href') and link.text.strip():
                        charts.append({
                            'name': link.text.strip(),
                            'url': link['href'],
                            'type': 'star'
                        })
                        self._log(f"Found STAR: {link.text.strip()}")
            
            # Extract Departure Procedure (DP/SID) charts
            dp_section = charts_section.find('h3', string=lambda s: s and 'Departure Procedure (DP)' in s)
            if dp_section:
                dp_parent = dp_section.parent
                dp_links = dp_parent.find_all('a')
                for link in dp_links:
                    if link.get('href') and link.text.strip():
                        charts.append({
                            'name': link.text.strip(),
                            'url': link['href'],
                            'type': 'departure'
                        })
                        self._log(f"Found Departure: {link.text.strip()}")
            
            # Extract Instrument Approach Procedure (IAP) charts
            iap_section = charts_section.find('h3', string=lambda s: s and 'Instrument Approach Procedure (IAP)' in s)
            if iap_section:
                iap_parent = iap_section.parent
                iap_links = iap_parent.find_all('a')
                for link in iap_links:
                    if link.get('href') and link.text.strip():
                        charts.append({
                            'name': link.text.strip(),
                            'url': link['href'],
                            'type': 'approach'
                        })
                        self._log(f"Found Approach: {link.text.strip()}")
            
            # Extract other charts (Hot Spots, LAHSOs, etc.)
            other_section = charts_section.find('h3', string=lambda s: s and 'Other' in s)
            if other_section:
                other_parent = other_section.parent
                other_links = other_parent.find_all('a')
                for link in other_links:
                    if link.get('href') and link.text.strip():
                        charts.append({
                            'name': link.text.strip(),
                            'url': link['href'],
                            'type': 'other'
                        })
                        self._log(f"Found Other: {link.text.strip()}")
            
            # Extract minimums
            minimums_section = charts_section.find('h3', string=lambda s: s and 'Minimums' in s)
            if minimums_section:
                min_parent = minimums_section.parent
                min_links = min_parent.find_all('a')
                for link in min_links:
                    if link.get('href') and link.text.strip():
                        charts.append({
                            'name': link.text.strip(),
                            'url': link['href'],
                            'type': 'minimums'
                        })
                        self._log(f"Found Minimums: {link.text.strip()}")
            
            return charts
            
        except requests.RequestException as e:
            raise Exception(f"Failed to fetch data from FAA: {e}")
        except Exception as e:
            raise Exception(f"Error parsing FAA data: {e}")

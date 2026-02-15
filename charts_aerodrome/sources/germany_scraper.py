#!/usr/bin/env python3
"""
Germany DFS AIP Scraper
Scrapes aerodrome charts from Germany's AIP with PDF downloads

Base URL: https://aip.dfs.de/basicIFR/
Print endpoint: /basicIFR/print/{myURL} - returns actual PDFs!

The URL structure uses dynamic hash-based page IDs that change each AIRAC cycle.
This scraper navigates the menu structure to find airport pages and builds
print URLs for PDF downloads.

ICAO prefix: ED*, ET* (military)
Example: EDDB (Berlin Brandenburg), EDDM (Munich), EDDF (Frankfurt)
"""

import requests
import re
from urllib.parse import quote


# ICAO code database for German airports
# Maps ICAO codes to airport names as they appear in the AIP
GERMANY_AIRPORTS = {
    'EDFQ': 'Allendorf/Eder',
    'EDMA': 'Augsburg',
    'EDQA': 'Bamberg-Breitenau',
    'EDBH': 'Barth',
    'EDAB': 'Bautzen',
    'EDQD': 'Bayreuth',
    'EDDB': 'Berlin Brandenburg',
    'EDLI': 'Bielefeld',
    'EDVE': 'Braunschweig-Wolfsburg',
    'EDDW': 'Bremen',
    'EDWB': 'Bremerhaven',
    'EDBC': 'Cochstedt',
    'EDCD': 'Cottbus-Drewitz',
    'EDAC': 'Dessau',
    'EDDC': 'Dresden',
    'EDDL': 'Düsseldorf',
    'EDFE': 'Egelsbach',
    'EDDE': 'Erfurt-Weimar',
    'EDLE': 'Essen/Mülheim',
    'EDDF': 'Frankfurt Main',
    'EDNY': 'Friedrichshafen',
    'EDDH': 'Hamburg',
    'EDDV': 'Hannover',
    'EDAH': 'Heringsdorf',
    'EDQM': 'Hof-Plauen',
    'EDSB': 'Karlsruhe/Baden-Baden',
    'EDVK': 'Kassel-Calden',
    'EDHK': 'Kiel-Holtenau',
    'EDDK': 'Köln Bonn',
    'EDTL': 'Lahr',
    'EDDP': 'Leipzig/Halle',
    'EDHL': 'Lübeck',
    'EDBM': 'Magdeburg/City',
    'EDFM': 'Mannheim City',
    'EDJA': 'Memmingen',
    'EDLN': 'Mönchengladbach',
    'EDDM': 'München',
    'EDDG': 'Münster/Osnabrück',
    'EDBN': 'Neubrandenburg',
    'EDLV': 'Niederrhein',
    'EDWY': 'Norderney',
    'EDDN': 'Nürnberg',
    'EDMO': 'Oberpfaffenhofen',
    'EDLP': 'Paderborn/Lippstadt',
    'ETNL': 'Rostock-Laage',
    'EDDR': 'Saarbrücken',
    'EDAZ': 'Schönhagen',
    'EDOP': 'Schwerin-Parchim',
    'EDGS': 'Siegerland',
    'EDMS': 'Straubing',
    'EDDS': 'Stuttgart',
    'EDXW': 'Sylt',
    'EDWG': 'Wangerooge',
    'EDCY': 'Welzow',
    'ETOU': 'Wiesbaden',
}


class GermanyScraper:
    """Scraper for Germany DFS AIP aerodrome charts with PDF downloads."""
    
    BASE_URL = "https://aip.dfs.de/basicIFR/"
    PRINT_URL = "https://aip.dfs.de/basicIFR/print/"
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.session = self._setup_session()
        self.airac_base = None
        self.ad2_hash = None
    
    def _setup_session(self):
        """Setup requests session with proper headers."""
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        })
        return session
    
    def _get_airac_base(self):
        """Get the base URL for the current AIRAC cycle."""
        if self.airac_base:
            return self.airac_base
        
        if self.verbose:
            print("[DEBUG] Getting AIRAC base URL...")
        
        r = self.session.get(self.BASE_URL, timeout=30, allow_redirects=True)
        
        # URL is like: https://aip.dfs.de/BasicIFR/2026JAN27/chapter/hash.html
        if '/chapter/' in r.url:
            parts = r.url.split('/chapter/')
            self.airac_base = parts[0] + '/'
            
            # Also extract the AD2 hash from breadcrumb if available
            ad2_match = re.search(r'href="([a-f0-9]{32})\.html"><span[^>]*>AD 2', r.text)
            if ad2_match:
                self.ad2_hash = ad2_match.group(1)
                if self.verbose:
                    print(f"[DEBUG] Found AD 2 hash from breadcrumb: {self.ad2_hash}")
        else:
            match = re.search(r'(https://aip\.dfs\.de/BasicIFR/\d{4}[A-Z]{3}\d{2}/)', r.url)
            if match:
                self.airac_base = match.group(1)
            else:
                raise Exception(f"Could not determine AIRAC base URL from: {r.url}")
        
        if self.verbose:
            print(f"[DEBUG] AIRAC base: {self.airac_base}")
        
        return self.airac_base
    
    def _find_ad2_hash(self):
        """Find the AD 2 section hash from navigation."""
        if self.ad2_hash:
            return self.ad2_hash
        
        base = self._get_airac_base()
        
        if self.verbose:
            print("[DEBUG] Finding AD 2 hash...")
        
        # Get the main AIP page
        r = self.session.get(self.BASE_URL, timeout=30, allow_redirects=True)
        
        # Method 1: Look for AD 2 in breadcrumb (when on an airport page)
        ad2_match = re.search(r'href="([a-f0-9]{32})\.html"[^>]*><span[^>]*>AD 2', r.text)
        if ad2_match:
            self.ad2_hash = ad2_match.group(1)
            if self.verbose:
                print(f"[DEBUG] AD 2 hash from breadcrumb: {self.ad2_hash}")
            return self.ad2_hash
        
        # Method 2: Navigate through AD folder
        # First get the AD section hash from main page
        ad_match = re.search(r'href="([a-f0-9]{32})\.html"[^>]*>\s*<span[^>]*>AD\s*<', r.text)
        if ad_match:
            ad_hash = ad_match.group(1)
            if self.verbose:
                print(f"[DEBUG] AD section hash: {ad_hash}")
            
            # Get AD page content
            r2 = self.session.get(f"{base}chapter/{ad_hash}.html", timeout=30)
            
            # Find AD 2 Flugplätze link - use more specific pattern
            # Pattern: href="HASH.html"...><span...>AD 2 Flugpl
            links = re.findall(r'href="([a-f0-9]{32})\.html"[^>]*>\s*<span[^>]*>([^<]+)</span>', r2.text)
            for hash_val, name in links:
                if name.strip().startswith('AD 2') and 'Flugpl' in name:
                    self.ad2_hash = hash_val
                    if self.verbose:
                        print(f"[DEBUG] AD 2 hash: {self.ad2_hash}")
                    return self.ad2_hash
        
        # Method 3: Direct search in any page that has AD 2 Aerodromes/Flugplätze
        if not self.ad2_hash:
            hashes = re.findall(r'href="([a-f0-9]{32})\.html"', r.text)
            for h in hashes[:10]:
                try:
                    test_r = self.session.get(f"{base}chapter/{h}.html", timeout=10)
                    # Look for the specific pattern
                    links = re.findall(r'href="([a-f0-9]{32})\.html"[^>]*>\s*<span[^>]*>([^<]+)</span>', test_r.text)
                    for hash_val, name in links:
                        if 'AD 2' in name and ('Flugpl' in name or 'Aerodrome' in name):
                            self.ad2_hash = hash_val
                            if self.verbose:
                                print(f"[DEBUG] AD 2 hash found by search: {self.ad2_hash}")
                            return self.ad2_hash
                except:
                    continue
        
        if self.verbose:
            print("[DEBUG] Could not find AD 2 hash automatically")
        
        return self.ad2_hash
    
    def _get_airport_hash(self, airport_name: str):
        """Get the hash for a specific airport's page by name."""
        base = self._get_airac_base()
        
        if not self.ad2_hash:
            self._find_ad2_hash()
        
        if not self.ad2_hash:
            if self.verbose:
                print("[DEBUG] Could not find AD 2 section")
            return None
        
        # Get AD 2 page with airport list
        r = self.session.get(f"{base}chapter/{self.ad2_hash}.html", timeout=30)
        
        # Find the airport by name - pattern: href="HASH.html">...<span...>Airport Name</span>
        # Use non-greedy matching within a single folder-item
        pattern = rf'<li class="folder-item"><a class="folder-link" href="([a-f0-9]{{32}})\.html">[^<]*<span[^>]*>{re.escape(airport_name)}'
        match = re.search(pattern, r.text, re.IGNORECASE)
        
        if match:
            return match.group(1)
        
        # Try partial match
        pattern = rf'href="([a-f0-9]{{32}})\.html">[^<]*<span[^>]*>[^<]*{re.escape(airport_name[:10])}'
        match = re.search(pattern, r.text, re.IGNORECASE)
        
        if match:
            return match.group(1)
        
        if self.verbose:
            print(f"[DEBUG] Could not find airport {airport_name} in AD 2 list")
        
        return None
    
    def get_charts(self, icao_code: str):
        """
        Get aerodrome charts for a German airport.
        
        Args:
            icao_code: 4-letter ICAO code (e.g., 'EDDB')
        
        Returns:
            List of dictionaries with 'name', 'url', and 'type' keys
            URLs point to PDF downloads via the print endpoint
        """
        icao_code = icao_code.upper()
        charts = []
        
        # Get airport name
        airport_name = GERMANY_AIRPORTS.get(icao_code)
        if not airport_name:
            if self.verbose:
                print(f"[DEBUG] ICAO code {icao_code} not in database")
            return charts
        
        if self.verbose:
            print(f"[DEBUG] Looking for {icao_code} ({airport_name})")
        
        # Get airport page hash
        airport_hash = self._get_airport_hash(airport_name)
        if not airport_hash:
            return charts
        
        base = self._get_airac_base()
        airport_url = f"{base}chapter/{airport_hash}.html"
        
        if self.verbose:
            print(f"[DEBUG] Fetching airport page...")
        
        r = self.session.get(airport_url, timeout=30)
        
        # Extract document-link hrefs - uppercase hashes!
        # Pattern: <a...class="document-link"...href="../pages/HASH.html"
        doc_links = re.findall(r'href="\.\./pages/([A-F0-9]{32})\.html"', r.text)
        page_hashes = list(dict.fromkeys(doc_links))  # Remove duplicates, keep order
        
        if self.verbose:
            print(f"[DEBUG] Found {len(page_hashes)} chart pages")
        
        # Fetch each chart page to get myURL and chart name
        for page_hash in page_hashes:
            page_url = f"{base}pages/{page_hash}.html"
            
            try:
                page_r = self.session.get(page_url, timeout=15)
                
                # Extract myURL for PDF
                myurl_match = re.search(r'myURL\s*=\s*["\']([^"\']+)["\']', page_r.text)
                
                if myurl_match:
                    my_url = myurl_match.group(1)
                    
                    # URL encode the myURL (handle spaces -> %20)
                    # Split by / and encode only the last part (chart name)
                    url_parts = my_url.rsplit('/', 1)
                    if len(url_parts) == 2:
                        encoded_url = url_parts[0] + '/' + quote(url_parts[1], safe='')
                    else:
                        encoded_url = quote(my_url, safe='/')
                    
                    pdf_url = self.PRINT_URL + encoded_url
                    
                    # Extract chart name from page content or title
                    # Look for document-name span or extract from myURL
                    name_match = re.search(r'<span[^>]*lang="en"[^>]*class="document-name"[^>]*>([^<]+)</span>', page_r.text)
                    if name_match:
                        chart_name = name_match.group(1).strip()
                    else:
                        # Extract from myURL: "AD/HASH/AD 2 EDDB 1-1" -> "AD 2 EDDB 1-1"
                        chart_name = my_url.split('/')[-1] if '/' in my_url else my_url
                    
                    chart_type = self._categorize_chart(chart_name)
                    
                    charts.append({
                        'name': chart_name,
                        'url': pdf_url,
                        'type': chart_type
                    })
                    
                    if self.verbose:
                        print(f"[DEBUG] Found: {chart_name}")
                        
            except Exception as e:
                if self.verbose:
                    print(f"[DEBUG] Error fetching page {page_hash}: {e}")
                continue
        
        if self.verbose:
            print(f"[DEBUG] Total: {len(charts)} charts with PDF URLs")
        
        return charts
    
    def _categorize_chart(self, chart_name: str) -> str:
        """
        Categorize chart based on its name and German AIP numbering.
        
        German AIP chart numbering system (AD 2 ICAO X-Y-Z):
        - 1-*: General airport text information
        - 2-*: Airport diagrams, ground charts, parking
        - 3-*: SID (Standard Instrument Departures)
        - 4-*: STAR (Standard Terminal Arrivals) - sections 4-2, 4-6, 4-7
        - 5-*: Approach procedures (ILS, RNAV, etc.) - sections 5-7
        - 6-*: Additional procedures/radar vectoring
        """
        name_upper = chart_name.upper()
        
        # First check keywords (higher confidence than number-based)
        # SID charts
        if 'SID' in name_upper or 'STANDARD INSTRUMENT DEPARTURE' in name_upper or 'DEPARTURE' in name_upper:
            return 'SID'
        
        # STAR charts
        if 'STAR' in name_upper or 'STANDARD INSTRUMENT ARRIVAL' in name_upper or 'ARRIVAL' in name_upper:
            return 'STAR'
        
        # Approach charts
        if any(kw in name_upper for kw in ['APPROACH', 'ILS', 'LOC', 'VOR', 'NDB', 'RNP', 'RNAV', 'GLS']):
            return 'Approach'
        
        # Airport diagrams
        if any(kw in name_upper for kw in ['AERODROME CHART', 'AIRPORT CHART', 'GROUND MOVEMENT', 
                                            'PARKING', 'DOCKING', 'AIRCRAFT PARKING', 'APRON']):
            return 'Airport Diagram'
        
        # Visual approach
        if 'VISUAL' in name_upper:
            return 'Approach'
        
        # German AIP number-based categorization
        # Pattern: AD 2 ICAO X-Y or AD 2 ICAO X-Y-Z where X is the main category
        number_match = re.search(r'AD\s*2\s+[A-Z]{4}\s+(\d+)-(\d+)', chart_name, re.IGNORECASE)
        if number_match:
            main_section = int(number_match.group(1))
            sub_section = int(number_match.group(2))
            
            # Section 1: General textual information
            if main_section == 1:
                return 'General'
            
            # Section 2: Airport diagrams, ground charts
            elif main_section == 2:
                return 'Airport Diagram'
            
            # Section 3: SID (Departures)
            elif main_section == 3:
                return 'SID'
            
            # Section 4: STAR (Arrivals) - 4-2 (text), 4-6 (initial), 4-7 (terminal)
            elif main_section == 4:
                if sub_section in [2, 6, 7]:
                    return 'STAR'
                return 'General'
            
            # Section 5: Approach procedures - 5-7 are approach charts
            elif main_section == 5:
                if sub_section == 7:
                    return 'Approach'
                return 'General'
            
            # Section 6: Additional procedures (radar, etc.)
            elif main_section == 6:
                return 'Approach'
        
        return 'General'


def get_aerodrome_charts(icao_code: str, verbose: bool = False):
    """
    Convenience function to get aerodrome charts.
    
    Args:
        icao_code: 4-letter ICAO code (e.g., 'EDDB')
        verbose: Enable debug output
    
    Returns:
        List of chart dictionaries with PDF URLs
    """
    scraper = GermanyScraper(verbose=verbose)
    return scraper.get_charts(icao_code)


# CLI interface
if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python germany_scraper.py <ICAO_CODE> [--verbose]")
        print("Example: python germany_scraper.py EDDB")
        print("\nSupported airports:")
        for icao, name in sorted(GERMANY_AIRPORTS.items()):
            print(f"  {icao} - {name}")
        sys.exit(1)
    
    icao = sys.argv[1].upper()
    verbose = '--verbose' in sys.argv or '-v' in sys.argv
    
    print(f"Fetching charts for {icao}...")
    
    charts = get_aerodrome_charts(icao, verbose=verbose)
    
    if charts:
        print(f"\nFound {len(charts)} charts:")
        for chart in charts:
            print(f"  [{chart['type']}] {chart['name']}")
            print(f"     {chart['url']}")
    else:
        print(f"No charts found for {icao}")

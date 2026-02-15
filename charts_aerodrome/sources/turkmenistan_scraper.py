"""
Turkmenistan CAICA Scraper
Fetches aerodrome charts from Turkmenistan's AIP via CAICA system.
URL: https://www.caica.ru/aiptkm/validaip/html/menueng.htm

Airports: UTAA (Ashgabat), UTAN (Balkanabat), UTAT (Dashoguz), UTAE (Kerki),
          UTAM (Mary), UTAV (Turkmenabat), UTAK (Turkmenbashi)
"""

import requests
import re
from typing import List, Dict
from urllib.parse import urljoin


def categorize_chart(name: str) -> str:
    """Categorize chart based on name."""
    name_lower = name.lower()
    
    # SID charts
    if any(kw in name_lower for kw in ['departure', 'sid']):
        return 'SID'
    
    # STAR charts
    if any(kw in name_lower for kw in ['arrival', 'star']):
        return 'STAR'
    
    # Approach charts
    if any(kw in name_lower for kw in ['approach', 'iac', 'ils', 'vor', 'ndb', 'rnav', 'rnp', 'gls']):
        return 'Approach'
    
    # Ground/Airport diagrams
    if any(kw in name_lower for kw in ['aerodrome chart', 'ground movement', 'parking', 'obstacle']):
        return 'Airport Diagram'
    
    # Area charts
    if 'area chart' in name_lower:
        return 'Area'
    
    return 'General'


def get_aerodrome_charts(icao_code: str, verbose: bool = False) -> List[Dict[str, str]]:
    """
    Fetch aerodrome charts for a Turkmenistan airport.
    
    Args:
        icao_code: ICAO code (UTAA, UTAN, UTAT, UTAE, UTAM, UTAV, UTAK)
        verbose: Print debug information
        
    Returns:
        List of chart dictionaries with 'name', 'url', and 'type' keys
    """
    icao_code = icao_code.upper()
    
    base_url = "https://www.caica.ru"
    menu_url = f"{base_url}/aiptkm/validaip/html/menueng.htm"
    
    if verbose:
        print(f"Fetching menu from {menu_url}")
    
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    })
    
    try:
        response = session.get(menu_url, verify=False, timeout=30)
        response.raise_for_status()
    except requests.RequestException as e:
        if verbose:
            print(f"Error fetching menu: {e}")
        return []
    
    content = response.text
    
    # Parse the JavaScript menu to find the airport
    charts = []
    in_airport = False
    
    for line in content.split('\n'):
        line = line.strip()
        
        # Check if we're entering the requested airport section
        if 'ItemBegin' in line:
            # Match: ItemBegin("5217", "","UTAA. ASHGABAT");
            match = re.search(r'ItemBegin\("[^"]+",\s*"[^"]*",\s*"([A-Z]{4})\.\s*([^"]+)"\)', line)
            if match:
                airport_icao = match.group(1)
                if airport_icao == icao_code:
                    in_airport = True
                    if verbose:
                        print(f"Found airport: {airport_icao} - {match.group(2)}")
                elif in_airport:
                    # We've moved to a different airport, stop
                    break
            continue
        
        # Check for ItemEnd (end of airport section)
        if 'ItemEnd' in line and in_airport:
            break
        
        # Parse ItemLink for charts
        if 'ItemLink' in line and in_airport:
            # Match: ItemLink("../aiptkm/ad/ad2/utaa/ad2-utaa-031-031-1.pdf","(31) AERODROME CHART - ICAO");
            match = re.search(r'ItemLink\("([^"]+)",\s*"([^"]+)"\)', line)
            if match:
                href = match.group(1)
                title = match.group(2)
                
                # Include DATA, TEXTS, TABLES entries
                
                # Clean up title - remove number prefix like "(31)"
                clean_title = re.sub(r'^\(\d+\)\s*', '', title)
                
                # Resolve the relative URL
                full_url = urljoin(menu_url, href)
                
                chart_type = categorize_chart(clean_title)
                
                charts.append({
                    'name': clean_title,
                    'url': full_url,
                    'type': chart_type
                })
                
                if verbose:
                    print(f"  Added: [{chart_type}] {clean_title}")
    
    if not in_airport:
        if verbose:
            print(f"Airport {icao_code} not found")
    
    return charts


# Alias for CLI compatibility
def get_charts(icao_code: str, verbose: bool = False) -> List[Dict[str, str]]:
    """Alias for get_aerodrome_charts."""
    return get_aerodrome_charts(icao_code, verbose)


if __name__ == '__main__':
    import sys
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    if len(sys.argv) > 1:
        icao = sys.argv[1].upper()
        verbose = '--verbose' in sys.argv or '-v' in sys.argv
        
        print(f"Fetching charts for {icao}...")
        charts = get_aerodrome_charts(icao, verbose=verbose)
        
        if charts:
            print(f"\nFound {len(charts)} charts:\n")
            for chart in charts:
                print(f"  [{chart['type']}] {chart['name']}")
                print(f"    {chart['url']}\n")
        else:
            print(f"No charts found for {icao}")
    else:
        print("Turkmenistan AIP Scraper")
        print("Airports: UTAA (Ashgabat), UTAN (Balkanabat), UTAT (Dashoguz),")
        print("          UTAE (Kerki), UTAM (Mary), UTAV (Turkmenabat), UTAK (Turkmenbashi)")
        print("\nUsage: python turkmenistan_scraper.py <ICAO> [--verbose]")
        print("Example: python turkmenistan_scraper.py UTAA")

"""
Malaysia CAAM eAIP Scraper

Scrapes aerodrome charts from Malaysia's Civil Aviation Authority eAIP.
Eurocontrol-style eAIP structure.

Main airports: WMKK (Kuala Lumpur), WMKP (Penang), WMSA (Sultan Abdul Aziz Shah)

Source: https://aip.caam.gov.my/aip/eAIP/history-en-MS.html
"""

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re


BASE_URL = "https://aip.caam.gov.my/aip/eAIP/"
HISTORY_URL = "https://aip.caam.gov.my/aip/eAIP/history-en-MS.html"


def categorize_chart(name: str) -> str:
    """Categorize chart based on name."""
    name_upper = name.upper()
    
    # Ground/Aerodrome patterns - check first (PARKING/DOCKING before APPROACH)
    if any(x in name_upper for x in ['PARKING', 'DOCKING', 'GROUND MOVEMENT', 
                                      'STAND', 'APRON', 'LIGHTING', 'AERODROME CHART',
                                      'HELIPORT CHART']):
        return 'GND'
    
    # Taxi routes - check for TAXI but need context
    if 'TAXI' in name_upper:
        # Taxi routes with ARRIVAL go to STAR category  
        if 'ARRIVAL' in name_upper:
            return 'STAR'
        # Taxi routes with DEPARTURE go to SID category
        if 'DEPARTURE' in name_upper:
            return 'SID'
        # Plain taxi charts are GND
        return 'GND'
    
    # SID patterns
    if 'SID' in name_upper or ('DEPARTURE' in name_upper and 'ARRIVAL' not in name_upper):
        return 'SID'
    
    # STAR patterns
    if 'STAR' in name_upper or ('ARRIVAL' in name_upper and 'DEPARTURE' not in name_upper):
        return 'STAR'
    
    # Approach patterns
    if any(x in name_upper for x in ['APPROACH', 'ILS', 'RNP', 'VOR', 'NDB', 'LOC', 'GLS', 'PAR']):
        return 'APP'
    
    # General patterns
    if any(x in name_upper for x in ['OBSTACLE', 'TERRAIN', 'AREA CHART', 'MSA', 'RADAR', 'PRECISION']):
        return 'GEN'
    
    return 'GEN'


def get_current_airac(verbose: bool = False) -> str:
    """
    Get the currently effective AIRAC date from the history page.
    
    Returns:
        Date string like '2025-12-02'
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    try:
        response = requests.get(HISTORY_URL, headers=headers, timeout=30)
        response.raise_for_status()
    except requests.RequestException as e:
        if verbose:
            print(f"Error fetching history page: {e}")
        return None
    
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Find "Currently Effective Issue" section
    # Look for link in the first table after "Currently Effective Issue"
    for h2 in soup.find_all('h2'):
        if 'Currently Effective' in h2.get_text():
            # Find next table
            table = h2.find_next('table')
            if table:
                # Find first link with date pattern
                for link in table.find_all('a', href=True):
                    href = link.get('href', '')
                    # Pattern: 2025-12-02/html/index-en-MS.html
                    match = re.search(r'(\d{4}-\d{2}-\d{2})', href)
                    if match:
                        return match.group(1)
    
    if verbose:
        print("Could not find current AIRAC date")
    return None


def get_aerodrome_charts(icao_code: str, verbose: bool = False) -> list:
    """
    Get aerodrome charts for a Malaysia airport.
    
    Args:
        icao_code: ICAO code (e.g., 'WMKK')
        verbose: Enable verbose output
        
    Returns:
        List of chart dictionaries with 'name', 'url', and 'type' keys
    """
    icao_code = icao_code.upper()
    
    # Get current AIRAC date
    if verbose:
        print("Getting current AIRAC date...")
    
    airac_date = get_current_airac(verbose)
    if not airac_date:
        if verbose:
            print("Failed to get AIRAC date")
        return []
    
    if verbose:
        print(f"Current AIRAC: {airac_date}")
    
    # Construct airport page URL
    airport_url = f"{BASE_URL}{airac_date}/html/eAIP/WM-AD-2.{icao_code}-en-MS.html"
    
    if verbose:
        print(f"Fetching airport page: {airport_url}")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    try:
        response = requests.get(airport_url, headers=headers, timeout=30)
        response.raise_for_status()
    except requests.RequestException as e:
        if verbose:
            print(f"Error fetching airport page: {e}")
        return []
    
    soup = BeautifulSoup(response.text, 'html.parser')
    charts = []
    
    # Find AD 2.24 section (charts)
    ad24_section = soup.find(id=f'{icao_code}-AD-2.24')
    
    if not ad24_section:
        if verbose:
            print(f"AD 2.24 section not found for {icao_code}")
        # Try to find charts in whole page
        ad24_section = soup
    
    # Base URL for PDFs (relative path ../../graphics/ -> {airac}/graphics/)
    pdf_base_url = f"{BASE_URL}{airac_date}/graphics/"
    
    # Find all PDF links
    for link in ad24_section.find_all('a', href=True):
        href = link.get('href', '')
        
        if not href.endswith('.pdf'):
            continue
        
        # Get chart code (e.g., "AD 2-WMKK-2-1")
        chart_code = link.get_text(strip=True)
        
        # Skip if not related to this airport
        if icao_code not in chart_code and icao_code not in href:
            continue
        
        # Find title from parent row
        title = chart_code
        parent_row = link.find_parent('tr')
        if parent_row:
            # Get full text from row and extract title
            row_text = parent_row.get_text(' ', strip=True)
            # Title is usually after the chart code
            if chart_code in row_text:
                # Try to extract title (format: "TITLE chart_code TACLO...")
                title_match = re.match(r'^([^A-Z]*AD\s*2[^A-Z]*)?(.+?)\s+' + re.escape(chart_code), row_text)
                if title_match:
                    title = title_match.group(2).strip()
                else:
                    # Just use everything before TACLO
                    parts = row_text.split('TACLO')
                    if parts:
                        title = parts[0].strip()
                        # Remove chart code from end if present
                        if title.endswith(chart_code):
                            title = title[:-len(chart_code)].strip()
        
        # Clean up title
        title = re.sub(r'\s+', ' ', title).strip()
        if not title or title == chart_code:
            title = chart_code
        
        # Construct full PDF URL
        # href is like "../../graphics/290219.pdf"
        if href.startswith('../../graphics/'):
            pdf_filename = href.split('/')[-1]
            pdf_url = pdf_base_url + pdf_filename
        else:
            pdf_url = urljoin(airport_url, href)
        
        chart_type = categorize_chart(title)
        
        charts.append({
            'name': title,
            'url': pdf_url,
            'type': chart_type
        })
        
        if verbose:
            print(f"  Found: {title[:60]}... [{chart_type}]")
    
    if verbose:
        print(f"Total charts found for {icao_code}: {len(charts)}")
    
    # Sort charts by type then name
    type_order = {'GEN': 0, 'GND': 1, 'SID': 2, 'STAR': 3, 'APP': 4}
    charts.sort(key=lambda x: (type_order.get(x['type'], 99), x['name']))
    
    return charts


# For CLI compatibility
class MalaysiaScraper:
    """Class wrapper for CLI compatibility."""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
    
    def get_charts(self, icao_code: str) -> list:
        return get_aerodrome_charts(icao_code, self.verbose)


if __name__ == "__main__":
    import sys
    icao = sys.argv[1] if len(sys.argv) > 1 else "WMKK"
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    
    print(f"Fetching charts for {icao}...")
    charts = get_aerodrome_charts(icao, verbose=verbose)
    
    if charts:
        print(f"\nFound {len(charts)} charts:")
        for chart in charts:
            print(f"  [{chart['type']}] {chart['name'][:60]}")
            print(f"       {chart['url']}")
    else:
        print("No charts found.")

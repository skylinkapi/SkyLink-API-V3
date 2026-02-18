#!/usr/bin/env python3
"""
Estonia eAIP Scraper
Scrapes aerodrome charts from Estonia AIP (EANS)

Base URL: https://eaip.eans.ee/
ICAO prefix: EE* (EETN - Tallinn, EEEI - Tartu, EEKA - Kärdla, EEPU - Pärnu)

Structure:
1. Main URL redirects to current AIRAC: https://eaip.eans.ee/2026-01-22/
2. Airport pages: html/eAIP/EE-AD-2.{ICAO}-en-GB.html
3. Charts in AD 2.24 section with table id="chartTable"
4. Eurocontrol standard structure
"""

import re
import requests
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
from urllib.parse import urljoin
import sys
import warnings

# Suppress XML parsed as HTML warning
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

BASE_URL = "https://eaip.eans.ee/"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
}


def get_current_airac_date():
    """
    Get the current AIRAC date folder by following redirect from base URL.
    
    Returns:
        str: Date folder like '2026-01-22'
    """
    try:
        # Follow redirects to get actual URL
        response = requests.get(BASE_URL, headers=HEADERS, timeout=30, allow_redirects=True)
        response.raise_for_status()
        
        # Extract date from final URL: https://eaip.eans.ee/2026-01-22/
        match = re.search(r'/(\d{4}-\d{2}-\d{2})/', response.url)
        if match:
            return match.group(1)
        
        # Fallback: search in page content for date folder links
        match = re.search(r'href="[^"]*?(\d{4}-\d{2}-\d{2})[^"]*"', response.text)
        if match:
            return match.group(1)
        
        return None
        
    except Exception as e:
        print(f"Error getting AIRAC date: {e}")
        return None


def get_airport_page_url(icao_code, airac_date):
    """Construct URL for airport page."""
    # Pattern: EE-AD-2.{ICAO}-en-GB.html
    return f"{BASE_URL}{airac_date}/html/eAIP/EE-AD-2.{icao_code}-en-GB.html"


def categorize_chart(chart_name):
    """Categorize chart based on its name."""
    name_upper = chart_name.upper()
    
    if any(kw in name_upper for kw in ['SID', 'DEPARTURE CHART', 'STANDARD DEPARTURE']):
        return 'SID'
    if any(kw in name_upper for kw in ['STAR', 'ARRIVAL CHART', 'STANDARD ARRIVAL']):
        return 'STAR'
    if any(kw in name_upper for kw in ['INSTRUMENT APPROACH', 'ILS', 'VOR', 'RNP', 'RNAV', 'LOC', 'NDB', 'DME', 'IAC', 'GLS', 'FASDB']):
        return 'Approach'
    if any(kw in name_upper for kw in ['VISUAL APPROACH', 'VAC']):
        return 'Approach'
    if any(kw in name_upper for kw in ['AERODROME CHART', 'PARKING', 'DOCKING', 'GROUND MOVEMENT', 'TAXI', 'ADC', 'APDC']):
        return 'Airport Diagram'
    if any(kw in name_upper for kw in ['AOC', 'OBSTACLE', 'PATC', 'TERRAIN']):
        return 'General'
    if any(kw in name_upper for kw in ['LDG', 'LANDING', 'BIRD']):
        return 'General'
    
    return 'General'


def parse_chart_name_from_filename(filename):
    """
    Parse human-readable chart name from Estonia PDF filename.
    
    Examples:
    - AD_2_EETN_ADC_en.pdf -> Aerodrome Chart (ADC)
    - AD_2_EETN_RNAV_SID_08_en.pdf -> RNAV SID RWY 08
    - AD_2_EETN_IAC_08_1_en.pdf -> Instrument Approach Chart RWY 08-1
    """
    # Remove path and extension
    name = filename.split('/')[-1].replace('.pdf', '').replace('_en', '')
    
    # Remove prefix like AD_2_EETN_ or AD-2-EETN-
    name = re.sub(r'^AD[-_]2[-_][A-Z]{4}[-_]', '', name)
    
    # Chart type mappings
    chart_types = {
        'ADC': 'Aerodrome Chart',
        'APDC': 'Aircraft Parking/Docking Chart',
        'AOC_A': 'Aerodrome Obstacle Chart Type A',
        'AOC_B': 'Aerodrome Obstacle Chart Type B',
        'PATC': 'Precision Approach Terrain Chart',
        'RNAV_SID': 'RNAV SID',
        'RNP_SID': 'RNP SID',
        'SID': 'Standard Instrument Departure',
        'RNAV_STAR': 'RNAV STAR',
        'RNP_STAR': 'RNP STAR',
        'STAR': 'Standard Arrival',
        'IAC': 'Instrument Approach Chart',
        'VAC': 'Visual Approach Chart',
        'FASDB': 'Final Approach Segment Data Block',
        'LDG': 'Landing Chart',
        'BIRD': 'Bird Concentration Chart',
    }
    
    # Try to match chart type
    for code, full_name in chart_types.items():
        if name.startswith(code):
            remainder = name[len(code):].strip('_-')
            # Parse runway info
            rwy_match = re.search(r'(\d{2})', remainder)
            suffix_match = re.search(r'_(\d+)$', remainder)
            
            parts = [full_name]
            if rwy_match:
                parts.append(f"RWY {rwy_match.group(1)}")
            if suffix_match:
                parts.append(f"({suffix_match.group(1)})")
            
            return ' '.join(parts)
    
    # Fallback: clean up the filename
    return name.replace('_', ' ').replace('-', ' ').title()


def get_aerodrome_charts(icao_code):
    """
    Fetch aerodrome charts for a given ICAO code from Estonia eAIP.
    
    Args:
        icao_code: 4-letter ICAO code (e.g., 'EETN')
        
    Returns:
        list: List of dicts with 'name', 'url', and 'type' keys
    """
    charts = []
    icao_code = icao_code.upper()
    
    try:
        # Get current AIRAC date
        airac_date = get_current_airac_date()
        
        if not airac_date:
            print("Could not determine current AIRAC date")
            return charts
        
        print(f"Using AIRAC date: {airac_date}")
        
        # Fetch airport page
        airport_url = get_airport_page_url(icao_code, airac_date)
        print(f"Fetching: {airport_url}")
        
        response = requests.get(airport_url, headers=HEADERS, timeout=30)
        
        if response.status_code == 404:
            print(f"Airport {icao_code} not found in Estonia eAIP")
            return charts
        
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'lxml')
        
        seen_urls = set()
        
        # Find all PDF links on the page
        for link in soup.find_all('a', href=lambda h: h and '.pdf' in h.lower()):
            href = link.get('href', '')
            
            # Build full URL
            if href.startswith('http'):
                chart_url = href
            else:
                chart_url = urljoin(airport_url, href)
            
            if chart_url in seen_urls:
                continue
            seen_urls.add(chart_url)
            
            # Parse chart name from filename
            chart_name = parse_chart_name_from_filename(href)
            
            charts.append({
                'name': chart_name,
                'url': chart_url,
                'type': categorize_chart(chart_name)
            })
        
        return charts
        
    except Exception as e:
        print(f"Error scraping {icao_code}: {e}")
        import traceback
        traceback.print_exc()
        return charts


def main():
    if len(sys.argv) < 2:
        print("Usage: python estonia_scraper.py <ICAO>")
        print("Example: python estonia_scraper.py EETN")
        sys.exit(1)
    
    icao = sys.argv[1].upper()
    print(f"Fetching charts for {icao}...")
    
    charts = get_aerodrome_charts(icao)
    
    if charts:
        print(f"\nFound {len(charts)} charts:")
        for c in charts:
            print(f"  [{c['type']}] {c['name']}")
            print(f"    {c['url']}")
    else:
        print("No charts found")


if __name__ == "__main__":
    main()

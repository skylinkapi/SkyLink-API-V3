#!/usr/bin/env python3
"""
France SIA eAIP Scraper
Scrapes aerodrome charts from French SIA eAIP following Eurocontrol structure

Supports multiple regions:
- FRANCE: Mainland France (LF*)
- CAR SAM NAM: Caribbean, Saint Pierre and Miquelon (TFF*, LF* for SPM)
- PAC-N: Pacific North - New Caledonia, Wallis and Futuna (NW*, NL*)
- PAC-P: Pacific South - French Polynesia (NT*)
- RUN: Reunion, Mayotte, scattered islands (FM*)

Note: Individual airport charts are not publicly accessible via scraping.
The SIA France eAIP appears to use an access control system where:
- htmlshow URLs serve as authenticated wrappers
- Actual eAIP content may be loaded in iframes for authorized users
- The /media/ path contains the raw eAIP files but is access-controlled
- Public access is limited to the eAIP home page links
"""

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote
import re
import sys


BASE_URL = "https://www.sia.aviation-civile.gouv.fr"


def get_current_eaip_urls():
    """Get the current effective eAIP URLs for all French regions"""
    try:
        response = requests.get(f"{BASE_URL}/plandesite", timeout=30)
        soup = BeautifulSoup(response.text, 'lxml')
        
        eaip_urls = {}
        
        # Look for eAIP links
        for link in soup.find_all('a', href=True):
            text = link.get_text().strip()
            href = link['href']
            
            if 'eAIP FRANCE' in text:
                eaip_urls['FRANCE'] = href
            elif 'eAIP CAR SAM NAM' in text:
                eaip_urls['CAR-SAM-NAM'] = href
            elif 'eAIP PAC-N' in text:
                eaip_urls['PAC-N'] = href
            elif 'eAIP PAC-P' in text:
                eaip_urls['PAC-P'] = href
            elif 'eAIP RUN' in text:
                eaip_urls['RUN'] = href
        
        return eaip_urls
        
    except Exception as e:
        print(f"Error getting eAIP URLs: {e}")
        return {}


def get_region_for_icao(icao_code):
    """Determine which region an ICAO code belongs to"""
    icao_upper = icao_code.upper()
    
    # France mainland
    if icao_upper.startswith('LF'):
        return 'FRANCE'
    
    # French Antilles
    elif icao_upper.startswith('TFF'):
        return 'CAR-SAM-NAM'
    
    # French Guiana
    elif icao_upper.startswith('SO'):
        return 'CAR-SAM-NAM'
    
    # New Caledonia
    elif icao_upper.startswith('NW'):
        return 'PAC-N'
    
    # Wallis and Futuna
    elif icao_upper.startswith('NL'):
        return 'PAC-N'
    
    # French Polynesia
    elif icao_upper.startswith('NT'):
        return 'PAC-P'
    
    # Reunion, Mayotte
    elif icao_upper.startswith('FM'):
        return 'RUN'
    
    return None


def get_eaip_base_url(region):
    """Get the base URL for a region's eAIP"""
    eaip_urls = get_current_eaip_urls()
    
    if region not in eaip_urls:
        return None
    
    # The actual eAIP content is in the AIRAC subdirectory
    # Format: /media/dvd/eAIP_22_JAN_2026/{REGION}/AIRAC-2026-01-22/html/eAIP/
    base_url = f"https://www.sia.aviation-civile.gouv.fr/media/dvd/eAIP_22_JAN_2026/{region}/AIRAC-2026-01-22/html/eAIP/"
    return base_url


def get_airport_page_url(icao_code):
    """Get the URL for a specific airport's AD 2 page"""
    region = get_region_for_icao(icao_code)
    if not region:
        return None
    
    base_url = get_eaip_base_url(region)
    if not base_url:
        return None
    
    # SIA France eAIP pattern: FR-AD-2.{ICAO}-fr-FR.html
    airport_page = f"FR-AD-2.{icao_code}-fr-FR.html"
    
    # Construct URL manually since urljoin doesn't handle query parameters well
    return base_url + airport_page


def categorize_chart(chart_name):
    """Categorize chart based on its name"""
    chart_name_upper = chart_name.upper()
    
    if 'SID' in chart_name_upper or 'STANDARD DEPARTURE' in chart_name_upper:
        return 'SID'
    elif 'STAR' in chart_name_upper or 'STANDARD ARRIVAL' in chart_name_upper:
        return 'STAR'
    elif 'APPROACH' in chart_name_upper or 'ILS' in chart_name_upper or 'LOC' in chart_name_upper \
            or 'NDB' in chart_name_upper or 'RNP' in chart_name_upper or 'GLS' in chart_name_upper \
            or 'VOR' in chart_name_upper or 'RNAV' in chart_name_upper:
        return 'APP'
    elif 'AERODROME CHART' in chart_name_upper or 'GROUND MOVEMENT' in chart_name_upper \
            or 'PARKING' in chart_name_upper or 'VISUAL APPROACH' in chart_name_upper \
            or 'APRON' in chart_name_upper or 'STAND' in chart_name_upper:
        return 'GND'
    else:
        return 'GEN'


def get_aerodrome_charts(icao_code):
    """
    Get all aerodrome charts for a given ICAO code from French SIA eAIP
    
    Args:
        icao_code: 4-letter ICAO code (e.g., 'LFPG', 'TFFF', 'NTAA')
        
    Returns:
        List of dictionaries with 'name', 'url', and 'type' keys
    """
    charts = []
    
    try:
        # Get airport page URL
        airport_url = get_airport_page_url(icao_code)
        if not airport_url:
            print(f"Could not determine airport page URL for {icao_code}")
            return charts
        
        print(f"Fetching {airport_url}")
        
        # Get the airport page
        response = requests.get(airport_url, timeout=30)
        if response.status_code != 200:
            print(f"Error: Got status code {response.status_code}")
            return charts
        
        soup = BeautifulSoup(response.text, 'lxml')
        
        # Find AD 2.24 section (charts section)
        # Look for the AD 2.24 header
        ad24_header = None
        for header in soup.find_all(['h2', 'h3', 'h4']):
            if 'AD 2.24' in header.get_text():
                ad24_header = header
                break
        
        if not ad24_header:
            print("AD 2.24 section not found")
            return charts
        
        # Find the parent container that holds the charts
        # Look for tables containing PDF links
        parent = ad24_header.parent
        if not parent:
            print("No parent container found for AD 2.24 header")
            return charts
        
        # Find all tables in the parent that contain PDF links
        chart_tables = []
        for table in parent.find_all('table'):
            pdf_links = table.find_all('a', href=lambda x: x and '.pdf' in x.lower())
            if pdf_links:
                chart_tables.append(table)
        
        if not chart_tables:
            print("No tables with PDF links found")
            return charts
        
        print(f"Found {len(chart_tables)} table(s) with PDF links")
        
        # Extract PDF links from all chart tables
        for table in chart_tables:
            for link in table.find_all('a', href=True):
                href = link['href']
                
                # Only process PDF links
                if '.pdf' not in href.lower():
                    continue
                
                # Get the chart name - try different approaches
                chart_name = ""
                
                # First, try to get name from link text
                link_text = link.get_text(strip=True)
                if link_text:
                    chart_name = link_text
                else:
                    # Try to get name from parent elements
                    parent_td = link.find_parent('td')
                    if parent_td:
                        # Look for text in the same row
                        row = parent_td.find_parent('tr')
                        if row:
                            cells = row.find_all('td')
                            if len(cells) > 1:
                                # Assume first cell has name, second has link
                                name_cell = cells[0]
                                chart_name = name_cell.get_text(strip=True)
                
                if not chart_name:
                    # Fallback: use filename from URL
                    chart_name = href.split('/')[-1].replace('.pdf', '').replace('_', ' ')
                
                # Build full URL
                full_url = urljoin(airport_url, href)
                
                # URL encode the PDF filename (spaces and special characters)
                url_parts = full_url.rsplit('/', 1)
                if len(url_parts) == 2:
                    base_url, filename = url_parts
                    encoded_filename = quote(filename, safe='')
                    full_url = f"{base_url}/{encoded_filename}"
                
                # Categorize the chart
                chart_type = categorize_chart(chart_name)
                
                charts.append({
                    'name': chart_name,
                    'url': full_url,
                    'type': chart_type
                })
        
        return charts
        
    except Exception as e:
        print(f"Error scraping {icao_code}: {e}")
        import traceback
        traceback.print_exc()
        return charts


def categorize_chart(chart_name):
    """
    Categorize chart based on its name
    
    Categories:
    - GEN: General information (procedures, requirements, operations, minimums)
    - GND: Ground charts (airport diagrams, taxi diagrams, parking, facilities)
    - SID: Standard Instrument Departure
    - STAR: Standard Terminal Arrival Route
    - APP: Approach procedures (IAP)
    """
    chart_lower = chart_name.lower()
    
    # GND - Ground/Airport diagrams
    if any(keyword in chart_lower for keyword in ['airport diagram', 'taxi', 'hot spot', 'lahso', 'parking', 'apron', 'ground movement', 'docking', 'adc', 'apdc', 'gmc']):
        return 'GND'
    
    # GEN - Minimums and general info
    if any(keyword in chart_lower for keyword in ['minimum', 'alternate', 'takeoff minimum', 'legend', 'procedure', 'requirement', 'operation']):
        # Exclude approach charts that might contain "minimum"
        if not any(keyword in chart_lower for keyword in ['ils', 'rnav', 'vor', 'approach', 'loc']):
            return 'GEN'
    
    # STAR - Standard Terminal Arrival
    if any(keyword in chart_lower for keyword in [' arrival', 'star']):
        # But not if it says departure or ground movement
        if 'departure' not in chart_lower and ' dp' not in chart_lower and 'ground' not in chart_lower:
            return 'STAR'
    
    # SID - Standard Instrument Departure  
    if any(keyword in chart_lower for keyword in ['departure', ' dp ', 'sid']):
        # But not ground movement charts
        if 'ground' not in chart_lower:
            return 'SID'
    
    # APP - Approach procedures and RNAV routes
    if any(keyword in chart_lower for keyword in ['approach', 'iap', 'ils', 'rnav', 'rnp', 'vor', 'ndb', 'gps', 'loc', 'tacan', 'visual', 'aoc', 'patc']):
        return 'APP'
    
    # Default to GEN for unknown types
    return 'GEN'


def main():
    if len(sys.argv) < 2:
        print("Usage: python france_scraper.py <ICAO_CODE>")
        print("Example: python france_scraper.py LFPG")
        sys.exit(1)
    
    icao_code = sys.argv[1].upper()
    
    print(f"Fetching charts for {icao_code}...")
    charts = get_aerodrome_charts(icao_code)
    
    if charts:
        print(f"\nFound {len(charts)} charts:")
        for chart in charts:
            print(f"  [{chart['type']}] {chart['name']}")
            print(f"    {chart['url']}")
    else:
        print("No charts found")


if __name__ == "__main__":
    main()
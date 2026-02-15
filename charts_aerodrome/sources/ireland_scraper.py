#!/usr/bin/env python3
"""
Ireland AIP Scraper
Scrapes aerodrome charts from Irish Aviation Authority (IAA)
https://www.airnav.ie/

ICAO prefix: EI* (EICK, EIDW, EINN, EIDL, EIKN, EIKY, EISG, EIWF, EIWT)
"""

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import sys


BASE_URL = "https://www.airnav.ie"

# ICAO to URL slug mapping
ICAO_TO_SLUG = {
    'EICK': 'cork-chart-information',
    'EIDW': 'dublin-chart-information',
    'EINN': 'shannon-chart-information',
    'EIDL': 'donegal-chart-information',
    'EIKN': 'ireland-west-chart-information',
    'EIKY': 'kerry-chart-information',
    'EISG': 'sligo-chart-information',
    'EIWF': 'waterford-chart-information',
    'EIWT': 'weston-chart-information',
}

# Airport names for display
ICAO_TO_NAME = {
    'EICK': 'Cork',
    'EIDW': 'Dublin',
    'EINN': 'Shannon',
    'EIDL': 'Donegal',
    'EIKN': 'Ireland West (Knock)',
    'EIKY': 'Kerry',
    'EISG': 'Sligo',
    'EIWF': 'Waterford',
    'EIWT': 'Weston',
}


def get_airport_page_url(icao_code):
    """Get the chart information page URL for an airport."""
    slug = ICAO_TO_SLUG.get(icao_code.upper())
    if not slug:
        return None
    return f"{BASE_URL}/air-traffic-management/aeronautical-information-management/aip-package/{slug}"


def categorize_chart(chart_name):
    """Categorize chart based on its name."""
    name_upper = chart_name.upper()
    
    # Ground/Airport diagrams
    if any(keyword in name_upper for keyword in ['AERODROME CHART', 'PARKING', 'DOCKING', 
                                                   'GROUND MOVEMENT', 'AIRCRAFT STAND']):
        return 'airport_diagram'
    
    # SID charts
    if any(keyword in name_upper for keyword in ['DEPARTURE CHART', 'SID', 'STANDARD DEPARTURE']):
        return 'sid'
    
    # STAR charts
    if any(keyword in name_upper for keyword in ['ARRIVAL CHART', 'STAR', 'STANDARD ARRIVAL']):
        return 'star'
    
    # Approach charts
    if any(keyword in name_upper for keyword in ['INSTRUMENT APPROACH', 'ILS', 'LOC', 'VOR', 
                                                   'NDB', 'RNP', 'RNAV', 'VISUAL APPROACH']):
        return 'approach'
    
    # Obstacle/Terrain charts - general info
    if any(keyword in name_upper for keyword in ['OBSTACLE', 'TERRAIN', 'PRECISION APPROACH TERRAIN',
                                                   'ATC SURVEILLANCE']):
        return 'airport_diagram'
    
    # Default
    return 'airport_diagram'


def get_aerodrome_charts(icao_code):
    """
    Get all aerodrome charts for a given ICAO code from Ireland AIP.
    
    Args:
        icao_code: 4-letter ICAO code (e.g., 'EICK', 'EIDW')
        
    Returns:
        List of dictionaries with 'name', 'url', and 'type' keys
    """
    charts = []
    icao_code = icao_code.upper()
    
    # Check if airport is supported
    if icao_code not in ICAO_TO_SLUG:
        print(f"Airport {icao_code} not found in Ireland AIP")
        print(f"Supported airports: {', '.join(sorted(ICAO_TO_SLUG.keys()))}")
        return charts
    
    try:
        # Get airport chart page
        airport_url = get_airport_page_url(icao_code)
        print(f"Fetching: {airport_url}")
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(airport_url, headers=headers, timeout=30)
        
        if response.status_code == 404:
            print(f"Airport page not found for {icao_code}")
            return charts
        
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'lxml')
        
        # Find all tables - charts are in tables with class "Table"
        seen_urls = set()
        
        for table in soup.find_all('table', class_='Table'):
            rows = table.find_all('tr')
            
            for row in rows:
                tds = row.find_all('td')
                if len(tds) < 2:
                    continue
                
                # First column: chart name (in <p> or direct text)
                name_td = tds[0]
                chart_name = name_td.get_text(strip=True)
                
                # Skip header rows or empty names
                if not chart_name or 'CHARTS RELATED' in chart_name.upper():
                    continue
                
                # Second column: PDF link
                link_td = tds[1]
                link = link_td.find('a', href=True)
                
                if not link:
                    continue
                
                href = link.get('href', '')
                if not href or '/getattachment/' not in href:
                    continue
                
                # Build full URL
                chart_url = urljoin(BASE_URL, href)
                
                # Skip duplicates
                if chart_url in seen_urls:
                    continue
                seen_urls.add(chart_url)
                
                # Categorize
                chart_type = categorize_chart(chart_name)
                
                charts.append({
                    'name': chart_name,
                    'url': chart_url,
                    'type': chart_type
                })
        
        return charts
        
    except requests.exceptions.HTTPError as e:
        print(f"HTTP error fetching charts for {icao_code}: {e}")
        return charts
    except Exception as e:
        print(f"Error scraping {icao_code}: {e}")
        import traceback
        traceback.print_exc()
        return charts


def main():
    if len(sys.argv) < 2:
        print("Usage: python ireland_scraper.py <ICAO_CODE>")
        print("Example: python ireland_scraper.py EICK")
        print(f"\nSupported airports:")
        for icao, name in sorted(ICAO_TO_NAME.items()):
            print(f"  {icao} - {name}")
        sys.exit(1)
    
    icao_code = sys.argv[1].upper()
    
    print(f"Fetching charts for {icao_code}...")
    charts = get_aerodrome_charts(icao_code)
    
    if charts:
        print(f"\nFound {len(charts)} charts:")
        
        # Group by type
        by_type = {}
        for chart in charts:
            t = chart['type']
            if t not in by_type:
                by_type[t] = []
            by_type[t].append(chart)
        
        for chart_type in ['airport_diagram', 'sid', 'star', 'approach']:
            if chart_type in by_type:
                print(f"\n  {chart_type}:")
                for chart in by_type[chart_type]:
                    print(f"    - {chart['name']}")
                    print(f"      {chart['url']}")
    else:
        print("No charts found")


if __name__ == "__main__":
    main()

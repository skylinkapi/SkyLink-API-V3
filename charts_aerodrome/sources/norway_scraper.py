#!/usr/bin/env python3
"""
Norway eAIP Scraper
Scrapes aerodrome charts from Norwegian AIP (Avinor)
https://aim-prod.avinor.no/

ICAO prefix: EN* (ENGM, ENBR, ENZV, ENSO, etc.)
"""

import requests
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
from urllib.parse import urljoin, quote
import re
import sys
import warnings

# Suppress XML parsing warning (content is valid HTML despite XML declaration)
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)


BASE_URL = "https://aim-prod.avinor.no/no/AIP/View/Index/148/"


def get_current_airac_folder():
    """
    Get the current effective AIRAC folder from the history page.
    Looks for "Gjeldende utgave" (Current edition) section.
    """
    try:
        url = f"{BASE_URL}history-no-NO.html"
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'lxml')
        
        # Look for links with AIRAC date pattern
        # Format: 2026-01-22-AIRAC
        for link in soup.find_all('a', href=True):
            href = link['href']
            match = re.search(r'(\d{4}-\d{2}-\d{2}-AIRAC)', href)
            if match:
                return match.group(1)
        
        # Alternative: find from page content
        text = response.text
        match = re.search(r'(\d{4}-\d{2}-\d{2}-AIRAC)', text)
        if match:
            return match.group(1)
        
        return None
        
    except Exception as e:
        print(f"Error getting AIRAC folder: {e}")
        return None


def get_airport_page_url(icao_code, airac_folder):
    """
    Construct the URL for an airport's eAIP page.
    Format: EN-AD-2.{ICAO}-no-NO.html
    """
    return f"{BASE_URL}{airac_folder}/html/eAIP/EN-AD-2.{icao_code}-no-NO.html"


def categorize_chart(chart_name):
    """Categorize chart based on its name."""
    name_upper = chart_name.upper()
    
    # General/Info charts - check first for exceptions
    if any(keyword in name_upper for keyword in ['RECOMMENDED CODING', 'TMA CHART', 'AREA CHART', 
                                                   'HELICOPTER ROUTE', 'INTERSECTION TAKE-OFF']):
        return 'airport_diagram'  # Will map to GEN via CLI
    
    # Ground movement / Airport diagrams
    if any(keyword in name_upper for keyword in ['AERODROME CHART', 'AD CHART', 'GROUND MOVEMENT', 
                                                   'PARKING', 'DOCKING', 'AIRCRAFT STAND', 'DE-ICE']):
        return 'airport_diagram'
    
    # SID charts
    if any(keyword in name_upper for keyword in ['SID', 'DEPARTURE CHART', 'DEPARTURE ROUTE', 'OMNI-DIRECTIONAL DEPARTURE']):
        return 'sid'
    
    # STAR charts
    if any(keyword in name_upper for keyword in ['STAR', 'ARRIVAL CHART', 'ARRIVAL ROUTE']):
        return 'star'
    
    # Approach charts
    if any(keyword in name_upper for keyword in ['RNP', 'ILS', 'LOC', 'VOR', 'NDB', 'APPROACH', 'IAC', 'PATC', 'TERRAIN CHART']):
        return 'approach'
    
    # Visual approach
    if 'VISUAL' in name_upper:
        return 'approach'
    
    # Default to airport_diagram (maps to GND via CLI)
    return 'airport_diagram'


def get_aerodrome_charts(icao_code):
    """
    Get all aerodrome charts for a given ICAO code from Norway eAIP.
    
    Args:
        icao_code: 4-letter ICAO code (e.g., 'ENGM', 'ENBR')
        
    Returns:
        List of dictionaries with 'name', 'url', and 'type' keys
    """
    charts = []
    icao_code = icao_code.upper()
    
    try:
        # Get current AIRAC folder
        airac_folder = get_current_airac_folder()
        if not airac_folder:
            print("Could not determine current AIRAC folder")
            return charts
        
        print(f"Using AIRAC: {airac_folder}")
        
        # Get airport page
        airport_url = get_airport_page_url(icao_code, airac_folder)
        print(f"Fetching: {airport_url}")
        
        response = requests.get(airport_url, timeout=30)
        
        if response.status_code == 404:
            print(f"Airport {icao_code} not found in Norway eAIP")
            return charts
        
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'lxml')
        
        # Find all tables - charts are in a table with headers "Chart Name" and "Side/Page"
        seen_urls = set()
        
        for table in soup.find_all('table'):
            # Check if this looks like a charts table
            headers = table.find_all('th')
            header_text = ' '.join([th.get_text(strip=True).lower() for th in headers])
            
            # Charts table has "chart name" or similar header
            if 'chart' not in header_text and 'kart' not in header_text:
                continue
            
            # Process rows
            rows = table.find_all('tr')
            
            for row in rows:
                tds = row.find_all('td')
                if len(tds) < 2:
                    continue
                
                # First column: chart name (usually in a <p> tag)
                name_td = tds[0]
                p_tag = name_td.find('p')
                if p_tag:
                    chart_name = p_tag.get_text(strip=True)
                else:
                    chart_name = name_td.get_text(strip=True)
                
                if not chart_name:
                    continue
                
                # Second column: PDF link
                link_td = tds[1]
                link = link_td.find('a', href=True)
                
                if not link:
                    continue
                
                href = link.get('href', '')
                if not href or '.pdf' not in href.lower():
                    continue
                
                # Skip if already seen
                if href in seen_urls:
                    continue
                seen_urls.add(href)
                
                # Resolve relative URL to absolute
                # URLs are like "../../graphics/571596.pdf" relative to airport page
                chart_url = urljoin(airport_url, href)
                
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
        print("Usage: python norway_scraper.py <ICAO_CODE>")
        print("Example: python norway_scraper.py ENGM")
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
        
        for chart_type in ['Airport Diagram', 'General', 'SID', 'STAR', 'Approach']:
            if chart_type in by_type:
                print(f"\n  {chart_type}:")
                for chart in by_type[chart_type]:
                    print(f"    - {chart['name']}")
                    print(f"      {chart['url']}")
    else:
        print("No charts found")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Dominican Republic AIP Scraper
Scrapes aerodrome charts from IDAC (Instituto Dominicano de Aviación Civil)
URL: https://aip.sna.gob.do/Map/{ICAO}

ICAO prefix: MD*
Examples: MDSD (Las Américas), MDPC (Punta Cana), MDST (Santiago), MDLR (La Romana)

The website organizes charts into sections:
- Aerodrome Data (AD 2.1-2.24)
- Aerodrome Charts (ground movement, parking, obstacles)
- SID (Standard Instrument Departure)
- STAR (Standard Instrument Arrival)
- IAC (Instrument Approach Charts)
- Area Charts (departure/arrival routes)
- Visual Approach Charts
"""

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote
import re
import sys
import urllib3

# Disable SSL warnings for sites with certificate issues
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


BASE_URL = "https://aip.sna.gob.do"


def categorize_chart(chart_name, section_type=None):
    """
    Categorize chart based on its name and the section it came from.
    
    Args:
        chart_name: Name of the chart
        section_type: Section identifier (sid, star, iac, map, etc.)
        
    Returns:
        Category string matching CLI expected types:
        - SID, STAR, Approach, airport_diagram, General
    """
    name_upper = chart_name.upper()
    
    # Use section_type if provided
    if section_type:
        if section_type == 'sid':
            return 'SID'
        elif section_type == 'star':
            return 'STAR'
        elif section_type == 'iac':
            return 'Approach'
        elif section_type == 'map':
            return 'airport_diagram'
        elif section_type == 'visual':
            return 'Approach'
        elif section_type == 'area':
            return 'General'
        elif section_type == 'radar':
            return 'General'
    
    # Fallback to name-based categorization
    if any(kw in name_upper for kw in ['SID', 'DEPARTURE', 'SALIDA']):
        return 'SID'
    elif any(kw in name_upper for kw in ['STAR', 'ARRIVAL', 'LLEGADA']):
        return 'STAR'
    elif any(kw in name_upper for kw in ['IAC', 'APPROACH', 'ILS', 'VOR', 'RNAV', 'LOC', 'DME', 'GNSS', 'APROXIMACIÓN', 'APROXIMACION', 'VISUAL']):
        return 'Approach'
    elif any(kw in name_upper for kw in ['AERODROME', 'PARKING', 'GROUND', 'OBSTACLE', 'TERRAIN', 'HELIPUERTO', 'ESTACIONAMIENTO', 'MOVIMIENTO', 'ATRAQUE']):
        return 'airport_diagram'
    else:
        return 'General'


def get_aerodrome_charts(icao_code):
    """
    Get all aerodrome charts for a given ICAO code from Dominican Republic AIP.
    
    Args:
        icao_code: 4-letter ICAO code (e.g., 'MDSD')
        
    Returns:
        List of dictionaries with 'name', 'url', and 'type' keys
    """
    icao_code = icao_code.upper()
    charts = []
    seen_urls = set()
    
    # Construct URL - the site uses mixed case in URL (Mdsd, Mdpc, etc.)
    # First letter uppercase, rest lowercase
    icao_formatted = icao_code[0].upper() + icao_code[1:].lower()
    url = f"{BASE_URL}/Map/{icao_formatted}"
    
    try:
        response = requests.get(url, timeout=30, verify=False)
        
        if response.status_code == 404:
            print(f"Airport {icao_code} not found in Dominican Republic AIP")
            return []
        
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'lxml')
        
        # Find all collapsible sections with their content
        # The structure uses data-toggle="collapse" for section headers
        # and div id='xxx' for section content
        
        # Section mappings: div id -> chart type
        section_mappings = {
            'ad0': 'data',      # Aerodrome Data
            'map': 'map',       # Aerodrome Charts
            'sid0': 'sid',      # SID
            'sid1': 'sid',      # Additional SID section (some airports)
            'arr0': 'star',     # STAR
            'arr1': 'star',     # Additional STAR section
            'chart0': 'iac',    # IAC
            'chart1': 'area',   # Area Chart - Departure/Transit
            'chart2': 'radar',  # Minimum Radar Altitude
            'chart3': 'area',   # Area Chart - Arrival/Transit
            'chart4': 'visual', # Visual Approach
        }
        
        for section_id, section_type in section_mappings.items():
            section_div = soup.find('div', {'id': section_id})
            
            if not section_div:
                continue
            
            # Find all PDF links in this section
            for link in section_div.find_all('a', href=True):
                href = link['href']
                
                # Only process PDF links
                if '.pdf' not in href.lower():
                    continue
                
                # Skip Aerodrome Data section (AD 2.1-2.23) as they are not charts
                # but keep AD 2.24 (Charts Related to Aerodrome)
                if section_type == 'data':
                    if 'ad_2-24' not in href.lower() and 'ad_2_24' not in href.lower():
                        continue
                
                # Get chart name from link text
                chart_name = link.get_text(strip=True)
                
                # Remove FontAwesome icon text if present (unicode characters)
                chart_name = re.sub(r'^[\s\u200b\uf000-\uf0ff]*', '', chart_name)
                chart_name = chart_name.strip()
                
                if not chart_name:
                    # Try to get name from filename
                    chart_name = href.split('/')[-1].replace('.pdf', '').replace('_', ' ')
                
                # Build full URL
                if href.startswith('../'):
                    # Handle relative paths like "../Datos/..."
                    href = href.replace('../', '/')
                
                if not href.startswith('http'):
                    full_url = urljoin(BASE_URL, href)
                else:
                    full_url = href
                
                # URL encode spaces in filename
                url_parts = full_url.rsplit('/', 1)
                if len(url_parts) == 2:
                    base_part, filename = url_parts
                    encoded_filename = quote(filename, safe='')
                    full_url = f"{base_part}/{encoded_filename}"
                
                # Skip duplicates
                if full_url in seen_urls:
                    continue
                
                seen_urls.add(full_url)
                
                # Categorize the chart
                chart_type = categorize_chart(chart_name, section_type)
                
                charts.append({
                    'name': chart_name,
                    'url': full_url,
                    'type': chart_type
                })
        
        return charts
        
    except requests.exceptions.RequestException as e:
        print(f"Error fetching charts for {icao_code}: {e}")
        return []
    except Exception as e:
        print(f"Error parsing charts for {icao_code}: {e}")
        import traceback
        traceback.print_exc()
        return []


def main():
    """Command line interface for testing."""
    if len(sys.argv) < 2:
        print("Usage: python dominican_republic_scraper.py <ICAO_CODE>")
        print("Example: python dominican_republic_scraper.py MDSD")
        print("\nAvailable airports: MDSD, MDPC, MDST, MDLR, MDJB, MDCY, MDBH, MDSI, MDPP")
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

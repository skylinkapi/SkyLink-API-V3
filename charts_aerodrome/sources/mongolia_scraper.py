#!/usr/bin/env python3
"""
Mongolia eAIP Scraper
Scrapes aerodrome charts from Mongolia AIS following Eurocontrol structure
https://ais.mn/files/aip/eAIP/valid/html/index-en-MN.html
"""

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote
import sys


# Base URL already points to latest valid eAIP
BASE_URL = "https://ais.mn/files/aip/eAIP/valid/html/"
EAIP_URL = f"{BASE_URL}eAIP/"


def categorize_chart(chart_name):
    """Categorize chart based on its name"""
    chart_name_upper = chart_name.upper()
    
    if 'SID' in chart_name_upper or 'STANDARD DEPARTURE' in chart_name_upper:
        return 'SID'
    elif 'STAR' in chart_name_upper or 'STANDARD ARRIVAL' in chart_name_upper:
        return 'STAR'
    elif 'APPROACH' in chart_name_upper or 'ILS' in chart_name_upper or 'LOC' in chart_name_upper \
            or 'NDB' in chart_name_upper or 'RNP' in chart_name_upper or 'VOR' in chart_name_upper \
            or 'GLS' in chart_name_upper or 'RNAV' in chart_name_upper:
        return 'APP'
    elif 'AERODROME CHART' in chart_name_upper or 'GROUND MOVEMENT' in chart_name_upper \
            or 'PARKING' in chart_name_upper or 'ADC' in chart_name_upper \
            or 'APRON' in chart_name_upper or 'AIRCRAFT STAND' in chart_name_upper:
        return 'GND'
    else:
        return 'GEN'


def get_aerodrome_charts(icao_code, verbose=False):
    """
    Get all aerodrome charts for a given ICAO code from Mongolia eAIP
    
    Args:
        icao_code: 4-letter ICAO code (e.g., 'ZMUB')
        verbose: Print debug information
        
    Returns:
        List of dictionaries with 'name', 'url', and 'type' keys
    """
    charts = []
    icao_code = icao_code.upper()
    
    # Airport page URL format: ZM-AD-2.{ICAO}-en-MN.html
    airport_url = f"{EAIP_URL}ZM-AD-2.{icao_code}-en-MN.html"
    
    if verbose:
        print(f"Fetching {airport_url}")
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(airport_url, headers=headers, timeout=30)
        
        if response.status_code != 200:
            if verbose:
                print(f"Error: Got status code {response.status_code}")
            return charts
        
        soup = BeautifulSoup(response.text, 'lxml')
        
        # Find all PDF links in the page (typically in AD 2.24 section)
        for link in soup.find_all('a', href=True):
            href = link['href']
            
            # Only process PDF links
            if '.pdf' not in href.lower():
                continue
            
            # Get chart name - try multiple methods
            chart_name = None
            
            # Method 1: Check parent td and previous row
            td_parent = link.find_parent('td')
            if td_parent:
                tr_parent = td_parent.find_parent('tr')
                if tr_parent:
                    # Find the previous sibling row which contains the chart name
                    prev_row = tr_parent.find_previous_sibling('tr')
                    if prev_row:
                        name_td = prev_row.find('td')
                        if name_td:
                            chart_name = name_td.get_text(strip=True)
            
            # Method 2: Link text itself
            if not chart_name or len(chart_name) < 3:
                chart_name = link.get_text(strip=True)
            
            # Method 3: Extract from href
            if not chart_name or len(chart_name) < 3:
                # Extract filename from href
                chart_name = href.rsplit('/', 1)[-1].replace('.pdf', '').replace('%20', ' ')
            
            if not chart_name:
                continue
            
            # Build full URL
            full_url = urljoin(airport_url, href)
            
            # URL encode the PDF filename (spaces and special characters)
            url_parts = full_url.rsplit('/', 1)
            if len(url_parts) == 2:
                base_url, filename = url_parts
                # Decode first in case it's already encoded, then re-encode
                from urllib.parse import unquote
                filename = unquote(filename)
                encoded_filename = quote(filename, safe='')
                full_url = f"{base_url}/{encoded_filename}"
            
            # Categorize the chart
            chart_type = categorize_chart(chart_name)
            
            # Avoid duplicates
            if not any(c['url'] == full_url for c in charts):
                charts.append({
                    'name': chart_name,
                    'url': full_url,
                    'type': chart_type
                })
        
        if verbose:
            print(f"Found {len(charts)} charts")
        
        return charts
        
    except Exception as e:
        if verbose:
            print(f"Error scraping {icao_code}: {e}")
            import traceback
            traceback.print_exc()
        return charts


def main():
    if len(sys.argv) < 2:
        print("Usage: python mongolia_scraper.py <ICAO_CODE>")
        print("Example: python mongolia_scraper.py ZMUB")
        sys.exit(1)
    
    icao_code = sys.argv[1].upper()
    
    print(f"Fetching charts for {icao_code}...")
    charts = get_aerodrome_charts(icao_code, verbose=True)
    
    if charts:
        print(f"\nFound {len(charts)} charts:")
        for chart in charts:
            print(f"  [{chart['type']}] {chart['name']}")
            print(f"    {chart['url']}")
    else:
        print("No charts found")


if __name__ == "__main__":
    main()

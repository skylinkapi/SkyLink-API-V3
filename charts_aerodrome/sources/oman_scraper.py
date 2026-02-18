#!/usr/bin/env python3
"""
Oman eAIP Scraper
Scrapes aerodrome charts from Oman CAA eAIP (Eurocontrol-style)
https://aim.caa.gov.om/eAIP_Oman/index-en-GB.html
"""

import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin, quote
import sys

BASE_URL = "https://aim.caa.gov.om/eAIP_Oman"


def get_current_airac_date(verbose=False):
    """Get the current AIRAC date from the index page"""
    index_url = f"{BASE_URL}/index-en-GB.html"
    
    if verbose:
        print(f"Fetching eAIP index from {index_url}")
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(index_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        # Extract date from script src like "final/2026-02-19/html/menu.js"
        match = re.search(r'final/(\d{4}-\d{2}-\d{2})/html/', response.text)
        if match:
            if verbose:
                print(f"Found AIRAC date: {match.group(1)}")
            return match.group(1)
        
        raise Exception("Could not find AIRAC date in index page")
        
    except Exception as e:
        if verbose:
            print(f"Error getting AIRAC date: {e}")
        return None


def categorize_chart(chart_name):
    """Categorize chart based on its name"""
    name_upper = chart_name.upper()
    
    # SID
    if 'SID' in name_upper or 'DEPARTURE' in name_upper:
        return 'SID'
    
    # STAR
    if 'STAR' in name_upper or 'ARRIVAL' in name_upper:
        return 'STAR'
    
    # APP - Approach charts
    if any(keyword in name_upper for keyword in [
        'ILS', 'VOR', 'NDB', 'RNP', 'RNAV', 'APPROACH',
        'LOC', 'VISUAL', 'INSTRUMENT', 'PRECISION', 'PATC',
        'MINIMUM SECTOR', 'MSA'
    ]):
        return 'APP'
    
    # GND - Ground charts
    if any(keyword in name_upper for keyword in [
        'AERODROME CHART', 'PARKING', 'DOCKING', 'GROUND',
        'TAXIWAY', 'OBSTACLE', 'ADC', 'APRON', 'STAND'
    ]):
        return 'GND'
    
    # Default to GEN
    return 'GEN'


def get_aerodrome_charts(icao_code, verbose=False):
    """
    Get all aerodrome charts for a given ICAO code from Oman eAIP
    
    Args:
        icao_code: 4-letter ICAO code (e.g., 'OOMS')
        verbose: Print debug information
        
    Returns:
        List of dictionaries with 'name', 'url', and 'type' keys
    """
    charts = []
    icao_code = icao_code.upper()
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    # Get current AIRAC date
    airac_date = get_current_airac_date(verbose)
    if not airac_date:
        if verbose:
            print("Could not determine current AIRAC date")
        return []
    
    # First, get the menu to find the actual airport page URL
    menu_url = f"{BASE_URL}/final/{airac_date}/html/eAIP/menu-en-GB.html"
    
    if verbose:
        print(f"Fetching menu page: {menu_url}")
    
    try:
        response = requests.get(menu_url, headers=headers, timeout=30)
        if response.status_code != 200:
            if verbose:
                print(f"Menu page error: {response.status_code}")
            return []
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find the airport link in the menu
        airport_url = None
        for link in soup.find_all('a', href=True):
            href = link['href']
            if f'AD-2.{icao_code}-en-GB.html' in href:
                airport_url = urljoin(menu_url, href.split('#')[0])
                if verbose:
                    print(f"Found airport page: {airport_url}")
                break
        
        if not airport_url:
            if verbose:
                print(f"Airport {icao_code} not found in menu")
            return []
        
        # Fetch the airport page
        response = requests.get(airport_url, headers=headers, timeout=30)
        if response.status_code != 200:
            if verbose:
                print(f"Airport page error: {response.status_code}")
            return []
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find all PDF links
        seen_urls = set()
        
        for link in soup.find_all('a', href=True):
            href = link['href']
            
            # Only process PDF links
            if '.pdf' not in href.lower():
                continue
            
            # Build full URL
            full_url = urljoin(airport_url, href)
            
            # URL encode spaces in the path
            url_parts = full_url.rsplit('/', 1)
            if len(url_parts) == 2:
                base_url, filename = url_parts
                encoded_filename = quote(filename, safe='')
                full_url = f"{base_url}/{encoded_filename}"
            
            # Skip duplicates
            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)
            
            # Get chart name from link text
            name = link.get_text(strip=True)
            name = ' '.join(name.split())  # Normalize whitespace
            
            if not name or len(name) < 3:
                # Extract from filename
                filename = href.split('/')[-1]
                name = filename.replace('.pdf', '').replace('%20', ' ')
            
            # Categorize
            chart_type = categorize_chart(name)
            
            charts.append({
                'name': name,
                'url': full_url,
                'type': chart_type
            })
        
        # Sort by type then name
        type_order = {'GEN': 0, 'GND': 1, 'SID': 2, 'STAR': 3, 'APP': 4}
        charts.sort(key=lambda x: (type_order.get(x['type'], 99), x['name']))
        
        if verbose:
            print(f"Found {len(charts)} charts")
        
        return charts
        
    except Exception as e:
        if verbose:
            print(f"Error scraping {icao_code}: {e}")
            import traceback
            traceback.print_exc()
        return []


def main():
    if len(sys.argv) < 2:
        print("Usage: python oman_scraper.py <ICAO_CODE>")
        print("Example: python oman_scraper.py OOMS")
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

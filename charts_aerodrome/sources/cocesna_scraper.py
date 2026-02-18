#!/usr/bin/env python3
"""
COCESNA (Central American Corporation for Air Navigation Services) eAIP Scraper
Scrapes aerodrome charts from COCESNA AIP following Eurocontrol structure.

Covers 6 Central American countries:
- Belize (MZ*)
- Costa Rica (MR*)
- El Salvador (MS*)
- Guatemala (MG*)
- Honduras (MH*)
- Nicaragua (MN*)

Base URL: https://www.cocesna.org/aipca/history.html
"""

import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote
import sys


BASE_URL = "https://www.cocesna.org/aipca/"


def get_latest_eaip_folder():
    """
    Get the latest eAIP folder path from the history page.
    
    Returns:
        str: Path to latest eAIP folder (e.g., "AIP_2655/Eurocontrol/COCESNA/2026-01-22-NON AIRAC")
    """
    try:
        response = requests.get(f"{BASE_URL}history.html", timeout=30)
        response.raise_for_status()
        
        # Find the first (latest) AIP folder link
        # Pattern: href="AIP_XXXX/Eurocontrol/COCESNA/YYYY-MM-DD-NON AIRAC/html/index-xx-XX.html"
        match = re.search(r'href="(AIP_\d+/Eurocontrol/COCESNA/[^"]+)/html/index-[a-z]{2}-[A-Z]{2}\.html"', response.text)
        
        if match:
            return match.group(1)
        
        # Fallback: look for any AIP folder pattern
        match = re.search(r'(AIP_\d+/Eurocontrol/COCESNA/[\d-]+-(?:NON\s*)?AIRAC)', response.text)
        if match:
            return match.group(1)
        
        raise Exception("Could not find eAIP folder in history page")
        
    except Exception as e:
        raise Exception(f"Failed to get latest eAIP folder: {e}")


def get_airport_page_url(icao_code):
    """
    Construct the URL for an airport's eAIP page.
    
    Args:
        icao_code (str): 4-letter ICAO code (e.g., 'MROC', 'MGGT')
        
    Returns:
        str: Full URL to airport page
    """
    folder = get_latest_eaip_folder()
    # URL encode the folder path (spaces in "NON AIRAC")
    folder_encoded = folder.replace(" ", "%20")
    
    # Airport pages use format: EN-AD-2.{ICAO}-en-EN.html
    airport_page = f"html/eAIP/EN-AD-2.{icao_code}-en-EN.html"
    
    return f"{BASE_URL}{folder_encoded}/{airport_page}"


def categorize_chart(chart_name):
    """
    Categorize a chart based on its name.
    
    Args:
        chart_name (str): Name of the chart
        
    Returns:
        str: Chart category (SID/STAR/Approach/Airport Diagram/General)
    """
    name_upper = chart_name.upper()
    
    # SID charts
    if ' SID ' in name_upper or name_upper.endswith(' SID') or 'DEPARTURE' in name_upper:
        return 'SID'
    
    # STAR charts
    if ' STAR ' in name_upper or name_upper.endswith(' STAR') or 'ARRIVAL' in name_upper:
        return 'STAR'
    
    # Approach charts - check various approach types
    if any(keyword in name_upper for keyword in [
        'IAC', 'ILS', 'LOC', 'VOR', 'NDB', 'RNAV', 'RNP', 'GPS', 'VISUAL APPR',
        'INSTRUMENT APPROACH', 'APPROACH CHART', 'CIRCLING'
    ]):
        return 'Approach'
    
    # Airport diagrams and ground charts
    if any(keyword in name_upper for keyword in [
        'ADC', 'AERODROME CHART', 'AIRPORT DIAGRAM', 'APC', 'PARKING',
        'AOC', 'AIRCRAFT OPERATING', 'GROUND', 'GMC', 'TAXI', 'APRON',
        'AC TMA', 'AREA CHART'
    ]):
        return 'Airport Diagram'
    
    # Default to General
    return 'General'


def get_aerodrome_charts(icao_code):
    """
    Fetch aerodrome charts for a given ICAO code from COCESNA eAIP.
    
    Args:
        icao_code (str): 4-letter ICAO code (e.g., 'MROC', 'MGGT', 'MZBZ')
        
    Returns:
        list: List of dictionaries with 'name', 'url', and 'type' keys
    """
    icao_code = icao_code.upper()
    charts = []
    
    try:
        # Get the airport page URL
        airport_url = get_airport_page_url(icao_code)
        
        # Fetch the airport page
        response = requests.get(airport_url, timeout=30)
        
        if response.status_code == 404:
            print(f"Airport {icao_code} not found in COCESNA eAIP")
            return []
        
        response.raise_for_status()
        
        # Parse the HTML
        soup = BeautifulSoup(response.text, 'lxml')
        
        # Get the base URL for resolving relative PDF paths
        # PDFs are relative to the eAIP folder
        folder = get_latest_eaip_folder()
        folder_encoded = folder.replace(" ", "%20")
        eaip_base_url = f"{BASE_URL}{folder_encoded}/html/eAIP/"
        
        # Find all PDF links
        seen_urls = set()
        
        for link in soup.find_all('a', href=True):
            href = link['href']
            
            # Only process PDF links
            if not href.lower().endswith('.pdf'):
                continue
            
            # Get chart name from link text
            chart_name = link.get_text(strip=True)
            if not chart_name:
                # Use filename as fallback
                chart_name = href.rsplit('/', 1)[-1].replace('.pdf', '').replace('%20', ' ')
            
            # Build full URL with proper encoding
            # PDFs are in Maps/{ICAO}/AD/ or Maps/{COUNTRY}/ folders relative to eAIP
            if href.startswith('Maps/'):
                # Relative path from eAIP folder
                # Split path and filename, encode each part
                path_parts = href.split('/')
                encoded_parts = []
                for part in path_parts:
                    # Encode spaces and special characters
                    encoded_parts.append(quote(part, safe=''))
                full_url = eaip_base_url + '/'.join(encoded_parts)
            elif href.startswith('../'):
                # Relative path going up
                full_url = urljoin(airport_url, href)
                # Re-encode the filename part
                url_parts = full_url.rsplit('/', 1)
                if len(url_parts) == 2:
                    full_url = url_parts[0] + '/' + quote(url_parts[1], safe='')
            else:
                full_url = urljoin(airport_url, href)
                # Re-encode the filename part
                url_parts = full_url.rsplit('/', 1)
                if len(url_parts) == 2:
                    base_part = url_parts[0]
                    filename = url_parts[1]
                    # Don't double-encode if already encoded
                    if '%20' not in filename and ' ' in filename:
                        filename = quote(filename, safe='')
                    full_url = base_part + '/' + filename
            
            # Skip duplicates
            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)
            
            # Categorize the chart
            chart_type = categorize_chart(chart_name)
            
            charts.append({
                'name': chart_name,
                'url': full_url,
                'type': chart_type
            })
        
        return charts
        
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            print(f"Airport {icao_code} not found in COCESNA eAIP")
            return []
        raise Exception(f"HTTP error fetching charts for {icao_code}: {e}")
    except Exception as e:
        raise Exception(f"Error fetching charts for {icao_code}: {e}")


# For CLI compatibility
if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python cocesna_scraper.py <ICAO_CODE>")
        print("Example: python cocesna_scraper.py MROC")
        print("\nSupported countries:")
        print("  - Belize (MZ*): MZBZ")
        print("  - Costa Rica (MR*): MROC, MRLB, MRPV")
        print("  - El Salvador (MS*): MSSS, MSLP")
        print("  - Guatemala (MG*): MGGT, MGPB")
        print("  - Honduras (MH*): MHTG, MHLM")
        print("  - Nicaragua (MN*): MNMG")
        sys.exit(1)
    
    icao = sys.argv[1].upper()
    
    print(f"Fetching charts for {icao}...")
    charts = get_aerodrome_charts(icao)
    
    if charts:
        print(f"\nFound {len(charts)} charts for {icao}:")
        for chart in charts:
            print(f"  [{chart['type']}] {chart['name']}")
            print(f"     {chart['url']}")
    else:
        print(f"No charts found for {icao}")

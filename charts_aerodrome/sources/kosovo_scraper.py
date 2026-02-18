#!/usr/bin/env python3
"""
Kosovo eAIP Scraper
Scrapes aerodrome charts from ASHNA Kosovo AIP (www.ashna-ks.org/eAIP)

Base URL: https://www.ashna-ks.org/eAIP/
Structure:
- default.html contains links to AIRAC versions with backslash paths
- AIRAC folder pattern: "AIRAC AMDT XX-YYYY_YYYY_MM_DD"
- Airport pages: eAIP/BK-AD 2 {ICAO}-en-GB.html (spaces in filename)
- Charts are PDF links in ../documents/Root_WePub/Charts/AD/{ICAO} AD 2/ folder

ICAO prefix: BK*
Examples: BKPR (Pristina International Airport)
"""

import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote
import sys


BASE_URL = "https://www.ashna-ks.org/eAIP/"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}


def get_latest_airac_folder():
    """
    Get the latest AIRAC folder name from the default page.
    
    Returns:
        str: AIRAC folder name (e.g., "AIRAC AMDT 01-2026_2026_01_22")
    """
    try:
        response = requests.get(BASE_URL + "default.html", headers=HEADERS, timeout=30)
        if response.status_code != 200:
            return None
        
        # Find AIRAC folder links - they use backslash paths like:
        # "AIRAC AMDT 01-2026_2026_01_22\index.html"
        # Match pattern that captures the folder name before \index.html
        matches = re.findall(r'href="(AIRAC AMDT [^"\\]+)\\index\.html"', response.text)
        
        if not matches:
            # Try alternate pattern with forward slash
            matches = re.findall(r'href="(AIRAC AMDT [^"/]+)/index\.html"', response.text)
        
        if matches:
            # Return the first (most recent) AIRAC folder
            return matches[0]
        
        return None
        
    except Exception as e:
        print(f"Error getting latest AIRAC folder: {e}")
        return None


def get_airport_page_url(icao_code, airac_folder):
    """
    Construct the URL for an airport's AD 2 page.
    
    Args:
        icao_code: 4-letter ICAO code (e.g., 'BKPR')
        airac_folder: AIRAC folder name
        
    Returns:
        str: Full URL to airport AD 2 page
    """
    # Airport page pattern: BK-AD 2 {ICAO}-en-GB.html (with spaces)
    airport_filename = f"BK-AD 2 {icao_code}-en-GB.html"
    
    # URL encode the folder and filename (spaces become %20)
    return f"{BASE_URL}{quote(airac_folder)}/eAIP/{quote(airport_filename)}"


def categorize_chart(chart_name):
    """
    Categorize a chart based on its filename/name.
    
    Args:
        chart_name: Chart name or filename
        
    Returns:
        str: Category (SID/STAR/Approach/Airport Diagram/General)
    """
    name_upper = chart_name.upper()
    
    # SID - Standard Instrument Departure
    if any(keyword in name_upper for keyword in ['SID', 'STANDARD_DEPARTURE', 'DEPARTURE_CHART']):
        return 'SID'
    
    # STAR - Standard Terminal Arrival
    if any(keyword in name_upper for keyword in ['STAR', 'STANDARD_ARRIVAL', 'ARRIVAL_CHART']):
        return 'STAR'
    
    # Approach charts
    if any(keyword in name_upper for keyword in [
        'IAC', 'ILS', 'LOC', 'VOR', 'NDB', 'RNAV', 'RNP', 'DME', 'APPROACH', 'RNP_AR'
    ]):
        return 'Approach'
    
    # Airport diagrams and ground charts
    if any(keyword in name_upper for keyword in [
        'AERODROME', 'HELIPORT', 'PARKING', 'DOCKING', 'GROUND_MOVEMENT', 
        'GROUND MOVEMENT', 'TAXI', 'AIRPORT'
    ]):
        return 'Airport Diagram'
    
    # General - everything else (obstacle charts, terrain charts, area charts, etc.)
    return 'General'


def clean_chart_name(filename):
    """
    Convert a PDF filename to a readable chart name.
    
    Args:
        filename: PDF filename (e.g., "STANDARD_DEPARTURE_CHART_INSTRUMENT_SID_ICAO_RWY17.pdf")
        
    Returns:
        str: Cleaned chart name
    """
    # Remove .pdf extension
    name = filename.replace('.pdf', '')
    
    # Replace underscores with spaces
    name = name.replace('_', ' ')
    
    # Clean up common patterns
    name = name.replace('ICAO', '- ICAO')
    name = name.replace('RWY', 'RWY ')
    
    # Remove duplicate spaces
    name = re.sub(r'\s+', ' ', name).strip()
    
    return name


def get_aerodrome_charts(icao_code):
    """
    Get all aerodrome charts for a given ICAO code from Kosovo eAIP.
    
    Args:
        icao_code: 4-letter ICAO code (e.g., 'BKPR')
        
    Returns:
        List of dictionaries with 'name', 'url', and 'type' keys
    """
    charts = []
    icao_code = icao_code.upper()
    
    try:
        # Get the latest AIRAC folder
        airac_folder = get_latest_airac_folder()
        if not airac_folder:
            print("Could not determine current AIRAC version")
            return charts
        
        # Get the airport page URL
        airport_url = get_airport_page_url(icao_code, airac_folder)
        
        # Fetch the airport page
        response = requests.get(airport_url, headers=HEADERS, timeout=30)
        
        if response.status_code == 404:
            print(f"Airport {icao_code} not found in Kosovo AIP")
            return charts
        elif response.status_code != 200:
            print(f"Error accessing airport page: HTTP {response.status_code}")
            return charts
        
        # Parse the HTML
        soup = BeautifulSoup(response.text, 'lxml')
        
        # Find all PDF links
        seen_urls = set()
        
        for link in soup.find_all('a', href=True):
            href = link['href']
            
            # Only process PDF links
            if '.pdf' not in href.lower():
                continue
            
            # Build full URL
            # PDFs are in ../documents/Root_WePub/Charts/AD/{ICAO} AD 2/
            # Relative to eAIP folder, so we need to resolve properly
            full_url = urljoin(airport_url, href)
            
            # Skip duplicates
            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)
            
            # Get chart name from filename
            filename = href.split('/')[-1]
            chart_name = clean_chart_name(filename)
            
            # URL encode the filename part (for spaces and special chars)
            url_parts = full_url.rsplit('/', 1)
            if len(url_parts) == 2:
                base_url, pdf_filename = url_parts
                full_url = f"{base_url}/{quote(pdf_filename)}"
            
            # Categorize the chart
            chart_type = categorize_chart(filename)
            
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


def main():
    if len(sys.argv) < 2:
        print("Usage: python kosovo_scraper.py <ICAO_CODE>")
        print("Example: python kosovo_scraper.py BKPR")
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

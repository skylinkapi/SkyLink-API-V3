#!/usr/bin/env python3
"""
Poland eAIP Scraper
Scrapes aerodrome charts from Poland AIP (PANSA - Polish Air Navigation Services Agency)

Base URL: https://www.ais.pansa.pl/en/publications/aip-poland/
eAIP IFR URL: https://docs.pansa.pl/ais/eaipifr/

ICAO prefix: EP*
Examples: EPWA (Warsaw Chopin), EPPO (Poznań), EPKK (Kraków), EPGD (Gdańsk)

Structure:
- Main page lists eAIP IFR link which changes with AIRAC cycles
- "Currently Effective Issue" row has cell with background-color:#ADFF2F
- From the effective link, extract AIRAC folder (e.g., "AIRAC AMDT 01-26_2026_01_22")
- Airport pages at: eAIP/AD%202%20{ICAO}%201-en-GB.html
- Charts in AD 2.24 section (MAPY DOTYCZĄCE LOTNISKA / Charts related to an aerodrome)
- PDF links have class "ulink" with full URLs to docs.pansa.pl
"""

import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote, unquote
import sys


# Base URLs
MAIN_PAGE_URL = "https://www.ais.pansa.pl/en/publications/aip-poland/"
EAIP_BASE_URL = "https://docs.pansa.pl/ais/eaipifr/"


def get_latest_eaip_url():
    """
    Get the URL of the latest Poland eAIP IFR from the main page.
    
    Returns:
        str: URL to the currently effective eAIP, e.g.:
             'https://docs.pansa.pl/ais/eaipifr/default_offline_2026-01-22.html'
    """
    try:
        response = requests.get(MAIN_PAGE_URL, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'lxml')
        
        # Find the eAIP IFR link - it's in a table with link to docs.pansa.pl/ais/eaipifr
        for link in soup.find_all('a', href=True):
            href = link['href']
            if 'docs.pansa.pl/ais/eaipifr' in href and 'default_offline' in href:
                return href
        
        # Fallback: search for any eaipifr link
        for link in soup.find_all('a', href=True):
            href = link['href']
            if 'eaipifr' in href and href.endswith('.html'):
                if href.startswith('http'):
                    return href
                return urljoin(MAIN_PAGE_URL, href)
        
        return None
        
    except Exception as e:
        print(f"Error getting latest eAIP URL: {e}")
        return None


def get_currently_effective_airac_folder(eaip_url):
    """
    From the eAIP landing page, find the "Currently Effective Issue" AIRAC folder.
    The currently effective row has a cell with background-color:#ADFF2F
    
    Args:
        eaip_url: URL to the eAIP landing page
        
    Returns:
        str: AIRAC folder name (URL-encoded), e.g., "AIRAC%20AMDT%2001-26_2026_01_22"
    """
    try:
        response = requests.get(eaip_url, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'lxml')
        
        # Find td with green background (currently effective)
        # Style contains "background-color:#ADFF2F"
        green_cells = soup.find_all('td', style=lambda s: s and 'ADFF2F' in s.upper() if s else False)
        
        for cell in green_cells:
            # Find the link in the same cell or row
            link = cell.find('a', href=True)
            if not link:
                row = cell.find_parent('tr')
                if row:
                    link = row.find('a', href=True)
            
            if link:
                href = link['href']
                # Extract AIRAC folder from href like "AIRAC AMDT 01-26_2026_01_22\index-v2.html"
                # or "AIRAC%20AMDT%2001-26_2026_01_22/index-v2.html"
                # Normalize backslashes to forward slashes
                href = href.replace('\\', '/')
                
                # Extract the AIRAC folder part
                if 'AIRAC' in href:
                    # Split on / and find the AIRAC part
                    parts = href.split('/')
                    for part in parts:
                        if 'AIRAC' in part:
                            # URL encode the folder name
                            return quote(unquote(part), safe='')
        
        # Fallback: look for any link with AIRAC in href
        for link in soup.find_all('a', href=True):
            href = link['href'].replace('\\', '/')
            if 'AIRAC' in href:
                parts = href.split('/')
                for part in parts:
                    if 'AIRAC' in part:
                        return quote(unquote(part), safe='')
        
        return None
        
    except Exception as e:
        print(f"Error getting currently effective AIRAC folder: {e}")
        return None


def get_airport_page_url(icao_code, airac_folder):
    """
    Construct the URL for a specific airport's AD 2 page.
    
    Args:
        icao_code: 4-letter ICAO code (e.g., 'EPWA')
        airac_folder: URL-encoded AIRAC folder name
        
    Returns:
        str: Full URL to airport page
    """
    # Airport pages are at: eAIP/AD%202%20{ICAO}%201-en-GB.html
    # e.g., https://docs.pansa.pl/ais/eaipifr/AIRAC%20AMDT%2001-26_2026_01_22/eAIP/AD%202%20EPPO%201-en-GB.html
    
    # URL encode the page name components
    page_name = f"AD 2 {icao_code} 1-en-GB.html"
    encoded_page = quote(page_name, safe='')
    
    return f"{EAIP_BASE_URL}{airac_folder}/eAIP/{encoded_page}"


def categorize_chart(chart_name):
    """
    Categorize chart based on its name.
    
    Args:
        chart_name: Name of the chart
        
    Returns:
        str: Chart category (SID/STAR/Approach/Airport Diagram/General)
    """
    name_upper = chart_name.upper()
    
    # SID charts
    if any(keyword in name_upper for keyword in [
        'STANDARD DEPARTURE', 'SID', 'DEP CHART', 'DEPARTURE CHART'
    ]):
        return 'SID'
    
    # STAR charts
    if any(keyword in name_upper for keyword in [
        'STANDARD ARRIVAL', 'STAR', 'ARR CHART', 'ARRIVAL CHART'
    ]):
        return 'STAR'
    
    # Approach charts
    if any(keyword in name_upper for keyword in [
        'APPROACH', 'ILS', 'VOR', 'RNP', 'RNAV', 'LOC', 'NDB', 'DME',
        'INSTRUMENT APPROACH', 'CIRCLING', 'PRECISION APPROACH', 'IAC'
    ]):
        return 'Approach'
    
    # Airport diagrams / Ground charts
    if any(keyword in name_upper for keyword in [
        'AERODROME CHART', 'AIRPORT CHART', 'PARKING', 'DOCKING',
        'GROUND MOVEMENT', 'TAXI', 'APRON', 'AIRCRAFT STAND'
    ]):
        return 'Airport Diagram'
    
    # VFR charts
    if any(keyword in name_upper for keyword in ['VFR', 'VISUAL']):
        return 'General'
    
    # Everything else (obstacles, terrain, etc.)
    return 'General'


def get_aerodrome_charts(icao_code):
    """
    Fetch aerodrome charts for a given ICAO code from Poland eAIP.
    
    Args:
        icao_code: 4-letter ICAO code (e.g., 'EPWA')
        
    Returns:
        list: List of dictionaries with 'name', 'url', and 'type' keys
    """
    charts = []
    icao_code = icao_code.upper()
    
    try:
        # Step 1: Get the latest eAIP URL from main page
        eaip_url = get_latest_eaip_url()
        if not eaip_url:
            print(f"Could not find eAIP IFR link on main page")
            return charts
        
        print(f"Found eAIP landing page: {eaip_url}")
        
        # Step 2: Get the currently effective AIRAC folder
        airac_folder = get_currently_effective_airac_folder(eaip_url)
        if not airac_folder:
            print(f"Could not find currently effective eAIP")
            return charts
        
        print(f"Found AIRAC folder: {unquote(airac_folder)}")
        
        # Step 3: Construct and fetch airport page
        airport_url = get_airport_page_url(icao_code, airac_folder)
        print(f"Fetching airport page: {airport_url}")
        
        response = requests.get(airport_url, timeout=30)
        if response.status_code == 404:
            print(f"Airport {icao_code} not found in Poland eAIP")
            return charts
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'lxml')
        
        # Step 4: Find the charts table (AD 2.24 section)
        # Tables have class containing "CHARTS_TABLE"
        charts_tables = soup.find_all('table', class_=lambda c: c and 'CHARTS_TABLE' in c if c else False)
        
        if not charts_tables:
            # Fallback: find any table in AD 2.24 section
            # Look for header containing "Charts" or "MAPY"
            for table in soup.find_all('table'):
                header = table.find('th')
                if header and ('Charts' in header.get_text() or 'MAPY' in header.get_text()):
                    charts_tables.append(table)
        
        if not charts_tables:
            print(f"Could not find charts table for {icao_code}")
            return charts
        
        # Step 5: Extract chart links from the table(s)
        seen_urls = set()
        
        for table in charts_tables:
            rows = table.find_all('tr')
            
            for row in rows:
                # Skip header rows
                if row.find('th'):
                    continue
                
                cells = row.find_all('td')
                if len(cells) < 2:
                    continue
                
                # First cell contains chart name (in nested spans)
                name_cell = cells[0]
                chart_name = name_cell.get_text(strip=True)
                
                # Clean up chart name - remove ICAO prefix if duplicated
                chart_name = re.sub(rf'^{icao_code}\s*-?\s*', '', chart_name)
                chart_name = chart_name.strip()
                
                if not chart_name:
                    continue
                
                # Second cell contains PDF link
                link_cell = cells[1]
                pdf_link = link_cell.find('a', class_='ulink', href=True)
                
                if not pdf_link:
                    pdf_link = link_cell.find('a', href=True)
                
                if not pdf_link:
                    continue
                
                href = pdf_link['href']
                
                # Skip non-PDF links
                if '.pdf' not in href.lower():
                    continue
                
                # Build full URL if relative
                if href.startswith('http'):
                    chart_url = href
                else:
                    chart_url = urljoin(airport_url, href)
                
                # URL-encode spaces and special characters in the path
                # Split URL into parts, encode the path portion
                if ' ' in chart_url:
                    # Parse URL and encode spaces in path
                    from urllib.parse import urlsplit, urlunsplit
                    parts = urlsplit(chart_url)
                    encoded_path = quote(unquote(parts.path), safe='/:')
                    chart_url = urlunsplit((parts.scheme, parts.netloc, encoded_path, parts.query, parts.fragment))
                
                # Skip duplicates
                if chart_url in seen_urls:
                    continue
                seen_urls.add(chart_url)
                
                # Categorize the chart
                chart_type = categorize_chart(chart_name)
                
                charts.append({
                    'name': chart_name,
                    'url': chart_url,
                    'type': chart_type
                })
        
        return charts
        
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            print(f"Airport {icao_code} not found in Poland eAIP")
        else:
            print(f"HTTP error fetching charts for {icao_code}: {e}")
        return charts
    except Exception as e:
        print(f"Error scraping {icao_code}: {e}")
        import traceback
        traceback.print_exc()
        return charts


def main():
    """CLI entry point for testing"""
    if len(sys.argv) < 2:
        print("Usage: python poland_scraper.py <ICAO_CODE>")
        print("Example: python poland_scraper.py EPWA")
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

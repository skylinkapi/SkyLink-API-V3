#!/usr/bin/env python3
"""
Slovakia eAIP Scraper
Scrapes aerodrome charts from Slovakia AIP (aim.lps.sk)

Base URL: https://aim.lps.sk/web/index.php?fn=200&lng=en
eAIP base: https://aim.lps.sk/web/eAIP_SR/AIP_SR_EFF_{DATE}/html/

ICAO prefix: LZ*
Examples: LZIB (Bratislava), LZKZ (Košice), LZPP (Piešťany), LZSL (Sliač)

Structure:
- Main page contains link to "Currently Effective" eAIP
- URL pattern: AIP_SR_EFF_{DDMMMYYYY} or AIP_SR_EFF_{DDMMMYYYY}_amdt
- Airport pages: LZ-AD-2.{ICAO}-en-SK.html
- Charts in AD 2.24 section with PDF links in graphics/ folder
"""

import re
import requests
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
from urllib.parse import urljoin, quote
import sys
import warnings

# Suppress XML parsing warnings (Slovakia AIP pages may be served as XML)
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

# Base URL for the AIP main page (session-based access may be required)
MAIN_PAGE_URL = "https://aim.lps.sk/web/index.php?fn=200&lng=en"
BASE_URL = "https://aim.lps.sk/web/"


def get_latest_eaip_base_url():
    """
    Get the URL of the latest Slovakia eAIP from the main page.
    
    Returns:
        str: Base URL like 'https://aim.lps.sk/web/eAIP_SR/AIP_SR_EFF_22JAN2026_amdt/html/'
    """
    try:
        response = requests.get(MAIN_PAGE_URL, timeout=30)
        soup = BeautifulSoup(response.text, 'lxml')
        
        # Find the "Currently Effective" link in the eAIP SR online table
        # Look for links containing 'eAIP_SR' and 'Currently Effective'
        for link in soup.find_all('a', href=True):
            href = link['href']
            text = link.get_text(strip=True)
            
            # Check for Currently Effective eAIP link
            if 'eAIP_SR' in href and ('Currently Effective' in text or 'AIP_SR_EFF' in href):
                # Extract the base URL (remove frameset file)
                # href might be: https://aim.lps.sk/web/eAIP_SR/AIP_SR_EFF_22JAN2026_amdt/html/LZ-frameset-en-SK.html
                if 'LZ-frameset' in href:
                    base_url = href.rsplit('/', 1)[0] + '/'
                else:
                    base_url = href
                
                if not base_url.endswith('/'):
                    base_url += '/'
                    
                return base_url
        
        # Fallback: search for any AIP_SR_EFF pattern
        for link in soup.find_all('a', href=True):
            href = link['href']
            if 'AIP_SR_EFF_' in href:
                match = re.search(r'(https?://[^"\']+eAIP_SR/AIP_SR_EFF_[^/]+/html/)', href)
                if match:
                    return match.group(1)
        
        return None
        
    except Exception as e:
        print(f"Error getting latest eAIP URL: {e}")
        return None


def get_airport_page_url(icao_code, base_url):
    """
    Get the URL for a specific airport's AD 2 page.
    
    Args:
        icao_code: 4-letter ICAO code (e.g., 'LZIB')
        base_url: Base eAIP URL
        
    Returns:
        str: Full URL to airport page
    """
    # Airport pages: LZ-AD-2.{ICAO}-en-SK.html
    airport_page = f"LZ-AD-2.{icao_code}-en-SK.html"
    return urljoin(base_url, airport_page)


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
    if any(keyword in name_upper for keyword in ['DEPARTURE', 'SID', 'DEP CHART']):
        return 'SID'
    
    # STAR charts
    if any(keyword in name_upper for keyword in ['ARRIVAL', 'STAR', 'ARR CHART']):
        return 'STAR'
    
    # Approach charts
    if any(keyword in name_upper for keyword in [
        'APPROACH', 'ILS', 'VOR', 'RNP', 'RNAV', 'LOC', 'NDB', 'DME',
        'INSTRUMENT APPROACH', 'CIRCLING', 'PRECISION APPROACH'
    ]):
        return 'Approach'
    
    # Airport diagrams / Ground charts
    if any(keyword in name_upper for keyword in [
        'AERODROME CHART', 'AIRPORT CHART', 'PARKING', 'DOCKING',
        'GROUND MOVEMENT', 'TAXI', 'APRON'
    ]):
        return 'Airport Diagram'
    
    # Everything else is general (obstacles, bird concentrations, noise, ATC surveillance, etc.)
    return 'General'


def get_aerodrome_charts(icao_code):
    """
    Fetch aerodrome charts for a given ICAO code from Slovakia eAIP.
    
    Args:
        icao_code: 4-letter ICAO code (e.g., 'LZIB')
        
    Returns:
        list: List of dictionaries with 'name', 'url', and 'type' keys
    """
    charts = []
    
    try:
        # Get the latest eAIP base URL
        base_url = get_latest_eaip_base_url()
        if not base_url:
            print(f"Could not determine eAIP base URL")
            return charts
        
        # Get airport page URL
        airport_url = get_airport_page_url(icao_code, base_url)
        
        print(f"Fetching {airport_url}")
        
        # Get the airport page
        response = requests.get(airport_url, timeout=30)
        if response.status_code == 404:
            print(f"Airport {icao_code} not found in Slovakia eAIP")
            return charts
        
        if response.status_code != 200:
            print(f"Error: Got status code {response.status_code}")
            return charts
        
        soup = BeautifulSoup(response.text, 'lxml')
        
        # Find all PDF links in the page
        # Charts are typically in the AD 2.24 section but we'll collect all PDF links
        # that match the pattern for chart files
        
        seen_urls = set()
        
        for link in soup.find_all('a', href=True):
            href = link['href']
            
            # Only process PDF links
            if '.pdf' not in href.lower():
                continue
            
            # Get the chart name
            chart_name = link.get_text(strip=True)
            
            # Skip empty names or page references like "AD 2-LZIB-2-1"
            if not chart_name or chart_name.startswith('AD 2-'):
                # Try to get name from parent or sibling elements
                parent_td = link.find_parent('td')
                if parent_td:
                    # Look for text in the row
                    parent_tr = parent_td.find_parent('tr')
                    if parent_tr:
                        # Get all text from the row
                        row_text = parent_tr.get_text(' ', strip=True)
                        # Extract chart name (usually before "AD 2-")
                        if 'AD 2-' in row_text:
                            chart_name = row_text.split('AD 2-')[0].strip()
                        else:
                            chart_name = row_text
            
            # Clean up chart name
            if chart_name:
                chart_name = re.sub(r'\s+', ' ', chart_name).strip()
                # Remove trailing page references
                chart_name = re.sub(r'\s*AD\s*2-[A-Z]{4}-\d+-\d+.*$', '', chart_name).strip()
                
            # Skip if still no meaningful name
            if not chart_name or len(chart_name) < 3:
                continue
            
            # Build full URL
            full_url = urljoin(airport_url, href)
            
            # URL encode the PDF filename (spaces and special characters)
            url_parts = full_url.rsplit('/', 1)
            if len(url_parts) == 2:
                url_base, filename = url_parts
                encoded_filename = quote(filename, safe='')
                full_url = f"{url_base}/{encoded_filename}"
            
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
            print(f"Airport {icao_code} not found in Slovakia eAIP")
        else:
            print(f"HTTP error fetching charts for {icao_code}: {e}")
        return charts
    except Exception as e:
        print(f"Error scraping {icao_code}: {e}")
        import traceback
        traceback.print_exc()
        return charts


def main():
    if len(sys.argv) < 2:
        print("Usage: python slovakia_scraper.py <ICAO_CODE>")
        print("Example: python slovakia_scraper.py LZIB")
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

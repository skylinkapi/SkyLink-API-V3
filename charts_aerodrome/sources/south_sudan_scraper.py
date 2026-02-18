#!/usr/bin/env python3
"""
South Sudan (SSCAA) Aerodrome Chart Scraper

Scrapes aerodrome charts from South Sudan Civil Aviation Authority AIP.
Source: https://sscaa.co/

ICAO prefix: HJ* (e.g., HJJJ - Juba, HJMK - Malakal, HJWW - Wau)

Structure:
- Main site has navigation to Part 3 Aerodromes (AD)
- AD 2 lists all aerodromes with ICAO codes
- Only some airports have AD 2.24 charts section (currently only HJJJ - Juba)
- Charts are served via API endpoint returning signed S3 URLs
"""

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote
import re
import json


BASE_URL = "https://sscaa.co"
TITLE_SHEET_URL = f"{BASE_URL}/part-0/aip-title-sheet/"
PDF_ENDPOINT = f"{BASE_URL}/endpoints/main-getpdf-endpoint.html"

# Mapping of ICAO codes to their URL slugs (from navigation)
# Only airports with AD 2.24 charts section are useful
AIRPORT_SLUGS = {
    'HJAK': 'hjak-akobo',
    'HJAR': 'hjar-adareil',
    'HJAW': 'hjaw-aweil',
    'HJBR': 'hjbr-bor',
    'HJBT': 'hjbt-bentiu',
    'HJFA': 'hjfa-paloich',
    'HJJJ': 'hjjj-juba',
    'HJKP': 'hjkp-kapoeta',
    'HJMD': 'hjmd-maridi',
    'HJMK': 'hjmk-malakal',
    'HJPI': 'hjpi-pibor',
    'HJRB': 'hjrb-rumbek',
    'HJRJ': 'hjrj-raga',
    'HJTR': 'hjtr-torit',
    'HJTU': 'hjtu-timbura',
    'HJWW': 'hjww-wau',
    'HJYA': 'hjya-yambio',
    'HJYE': 'hjye-yei',
    'HJYL': 'hjyl-yirol',
}


def categorize_chart(chart_name):
    """
    Categorize chart based on its name.
    
    Args:
        chart_name: Name/title of the chart
        
    Returns:
        Category string: 'SID', 'STAR', 'Approach', 'Airport Diagram', or 'General'
    """
    name_upper = chart_name.upper()
    
    # SID - Standard Instrument Departure
    if 'SID' in name_upper or 'DEPARTURE' in name_upper:
        return 'SID'
    
    # STAR - Standard Terminal Arrival
    if 'STAR' in name_upper or 'ARRIVAL' in name_upper:
        return 'STAR'
    
    # Approach charts (but not coding tables which are supporting docs)
    if any(kw in name_upper for kw in ['APPROACH', 'ILS', 'LOC', 'VOR', 'DME', 'RNP', 'RNAV', 'NDB']):
        # Coding tables are supporting docs, not approach charts
        if 'CODING TABLE' not in name_upper:
            return 'Approach'
    
    # Airport diagrams (aerodrome chart, parking, ground movement)
    if any(kw in name_upper for kw in ['AERODROME CHART', 'AIRPORT CHART', 'PARKING', 'GROUND', 'TAXI']):
        return 'Airport Diagram'
    
    # General/Other (minimums, coding tables, AMA, etc.)
    return 'General'


def get_airport_charts_url(icao_code):
    """
    Construct the AD 2.24 charts page URL for an airport.
    
    Args:
        icao_code: 4-letter ICAO code (e.g., 'HJJJ')
        
    Returns:
        URL string or None if airport not found
    """
    icao_upper = icao_code.upper()
    
    if icao_upper not in AIRPORT_SLUGS:
        return None
    
    slug = AIRPORT_SLUGS[icao_upper]
    return f"{BASE_URL}/part-3-aerodromes-(ad)/ad-2-aerodromes/{slug}/ad-2.24-charts/"


def get_chart_pages(charts_url):
    """
    Get list of chart page URLs from AD 2.24 section.
    
    Args:
        charts_url: URL to AD 2.24 charts index page
        
    Returns:
        List of tuples: (chart_page_url, chart_name_from_link)
    """
    try:
        response = requests.get(charts_url, timeout=30)
        if response.status_code == 404:
            return []
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'lxml')
        
        chart_pages = []
        
        # Find links to chart pages (they end with .html and contain ICAO code)
        for link in soup.find_all('a', href=True):
            href = link['href']
            
            # Skip non-chart links
            if not href.endswith('.html'):
                continue
            
            # Only process chart pages (contain /ad-2.24-charts/ and hjjj- in path)
            if '/ad-2.24-charts/' not in href:
                continue
                
            # Get just the filename
            filename = href.split('/')[-1]
            
            # Skip table of contents or index pages
            if 'table-of-contents' in filename or filename == 'index.html':
                continue
            
            # Must start with airport ICAO code pattern (hjXX-)
            if not re.match(r'^hj[a-z]{2}-', filename):
                continue
            
            # Extract chart name from link text or filename
            link_text = link.get_text(strip=True)
            if not link_text:
                # Convert filename to name: hjjj-aerodrome-chart-icao.html -> Aerodrome Chart ICAO
                link_text = filename.replace('.html', '').replace('-', ' ').title()
            
            # Build full URL - use BASE_URL + the relative path from href
            # The href contains full relative path like: part-3-aerodromes-(ad)/ad-2-aerodromes/hjjj-juba/ad-2.24-charts/hjjj-aerodrome-chart-icao.html
            full_url = f"{BASE_URL}/{href}"
            
            chart_pages.append((full_url, link_text))
        
        # Remove duplicates while preserving order
        seen = set()
        unique_pages = []
        for url, name in chart_pages:
            if url not in seen:
                seen.add(url)
                unique_pages.append((url, name))
        
        return unique_pages
        
    except Exception as e:
        print(f"Error fetching chart pages: {e}")
        return []


def extract_chart_info(chart_page_url):
    """
    Extract chart ID and pagetitle from a chart HTML page.
    
    Args:
        chart_page_url: URL to individual chart page
        
    Returns:
        Tuple: (chart_id, pagetitle) or (None, None) if not found
    """
    try:
        response = requests.get(chart_page_url, timeout=30)
        response.raise_for_status()
        
        html = response.text
        
        # Extract dataJSON.id
        id_match = re.search(r"dataJSON\.id\s*=\s*'(\d+)'", html)
        chart_id = id_match.group(1) if id_match else None
        
        # Extract dataJSON.pagetitle
        title_match = re.search(r"dataJSON\.pagetitle\s*=\s*'([^']+)'", html)
        pagetitle = title_match.group(1) if title_match else None
        
        return chart_id, pagetitle
        
    except Exception as e:
        print(f"Error extracting chart info from {chart_page_url}: {e}")
        return None, None


def get_signed_pdf_url(chart_id, pagetitle):
    """
    Get signed S3 URL for a chart PDF via API endpoint.
    
    Args:
        chart_id: Chart ID string
        pagetitle: Chart page title
        
    Returns:
        Signed URL string or None if failed
    """
    try:
        payload = {
            'id': chart_id,
            'pagetitle': pagetitle
        }
        
        response = requests.post(
            PDF_ENDPOINT,
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        
        data = response.json()
        return data.get('signedURL')
        
    except Exception as e:
        print(f"Error getting PDF URL for chart {chart_id}: {e}")
        return None


def get_aerodrome_charts(icao_code):
    """
    Get all aerodrome charts for a given ICAO code from South Sudan AIP.
    
    Args:
        icao_code: 4-letter ICAO code (e.g., 'HJJJ')
        
    Returns:
        List of dictionaries with 'name', 'url', and 'type' keys
    """
    icao_upper = icao_code.upper()
    charts = []
    
    # Get charts URL for this airport
    charts_url = get_airport_charts_url(icao_upper)
    
    if not charts_url:
        print(f"Airport {icao_upper} not found in South Sudan AIP")
        print(f"Available airports: {', '.join(sorted(AIRPORT_SLUGS.keys()))}")
        return charts
    
    # Get list of chart pages
    chart_pages = get_chart_pages(charts_url)
    
    if not chart_pages:
        print(f"No charts found for {icao_upper} (airport may not have AD 2.24 section)")
        return charts
    
    # Process each chart page
    for page_url, link_name in chart_pages:
        # Extract chart ID and title from page
        chart_id, pagetitle = extract_chart_info(page_url)
        
        if not chart_id or not pagetitle:
            continue
        
        # Get signed PDF URL
        pdf_url = get_signed_pdf_url(chart_id, pagetitle)
        
        if not pdf_url:
            continue
        
        # Clean up chart name from pagetitle
        # Format: "HJJJ-01 AERODROME CHART - ICAO" -> "AERODROME CHART - ICAO"
        chart_name = pagetitle
        if '-' in chart_name:
            # Remove ICAO-XX prefix
            parts = chart_name.split(' ', 1)
            if len(parts) > 1 and re.match(r'^[A-Z]{4}-\d+$', parts[0]):
                chart_name = parts[1]
        
        # Categorize chart
        chart_type = categorize_chart(chart_name)
        
        charts.append({
            'name': f"{icao_upper} - {chart_name}",
            'url': pdf_url,
            'type': chart_type
        })
    
    return charts


def list_available_airports():
    """
    List all airports available in South Sudan AIP.
    
    Returns:
        List of tuples: (icao_code, airport_name)
    """
    airports = []
    
    try:
        response = requests.get(TITLE_SHEET_URL, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'lxml')
        
        # Find airport links in navigation
        for link in soup.find_all('a', href=True):
            href = link['href']
            
            # Match airport links pattern
            match = re.search(r'/ad-2-aerodromes/(hj[a-z]{2})-([^/]+)/', href)
            if match:
                icao = match.group(1).upper()
                name = match.group(2).replace('-', ' ').title()
                airports.append((icao, name))
        
        # Remove duplicates
        airports = list(set(airports))
        airports.sort()
        
        return airports
        
    except Exception as e:
        print(f"Error listing airports: {e}")
        return list(AIRPORT_SLUGS.items())


# For CLI testing
if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1:
        icao = sys.argv[1].upper()
        print(f"Fetching charts for {icao}...")
        
        charts = get_aerodrome_charts(icao)
        
        if charts:
            print(f"\nFound {len(charts)} charts for {icao}:")
            for chart in charts:
                print(f"  [{chart['type']}] {chart['name']}")
                print(f"     {chart['url'][:80]}...")
        else:
            print(f"No charts found for {icao}")
    else:
        print("South Sudan AIP Airports:")
        print("-" * 40)
        for icao, name in AIRPORT_SLUGS.items():
            name_clean = name.split('-', 1)[1].replace('-', ' ').title()
            print(f"  {icao}: {name_clean}")
        print("\nNote: Currently only HJJJ (Juba) has AD 2.24 charts")
        print("\nUsage: python south_sudan_scraper.py <ICAO_CODE>")
        print("Example: python south_sudan_scraper.py HJJJ")

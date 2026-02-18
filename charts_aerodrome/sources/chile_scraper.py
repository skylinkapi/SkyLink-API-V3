#!/usr/bin/env python3
"""
Chile DGAC AIP Scraper
Scrapes aerodrome charts from Chile's official aeronautical information publication.

Base URL: https://aipchile.dgac.gob.cl/aip/vol2/seccion/proc
ICAO prefix: SC* (SCEL, SCIE, SCDA, SCFA, etc.)

Charts are stored at: http://aipchile.dgac.gob.cl/dasa/aip_chile_con_contenido/aipmap/{ICAO}/
"""

import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote, unquote
import sys


BASE_URL = "https://aipchile.dgac.gob.cl"
PROC_URL = "https://aipchile.dgac.gob.cl/aip/vol2/seccion/proc"


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
    if 'SID' in name_upper:
        return 'SID'
    
    # STAR charts
    if 'STAR' in name_upper:
        return 'STAR'
    
    # Approach charts (IAC = Instrument Approach Chart)
    if any(keyword in name_upper for keyword in [
        'IAC', 'ILS', 'LOC', 'VOR', 'NDB', 'RNAV', 'RNP', 'GPS'
    ]):
        return 'Approach'
    
    # Airport diagrams and ground charts
    if any(keyword in name_upper for keyword in [
        'ADC', 'AERODROME CHART', 'PDC', 'PARKING', 
        'VAC', 'VISUAL', 'BCAC', 'SMGCS', 'GMC',
        'ATCSMAC', 'AREA CHART'
    ]):
        return 'Airport Diagram'
    
    # Default to General
    return 'General'


def get_all_proc_pages():
    """
    Get all procedure pages (handles pagination).
    
    Returns:
        list: List of page URLs
    """
    pages = [PROC_URL]
    
    try:
        response = requests.get(PROC_URL, timeout=30)
        response.raise_for_status()
        
        # Find pagination links
        soup = BeautifulSoup(response.text, 'lxml')
        
        # Look for pagination links like /aip/vol2/seccion/proc/pagina/01
        for link in soup.find_all('a', href=True):
            href = link['href']
            if '/proc/pagina/' in href:
                full_url = urljoin(BASE_URL, href)
                if full_url not in pages:
                    pages.append(full_url)
        
        return pages
        
    except Exception as e:
        print(f"Error getting procedure pages: {e}")
        return pages


def get_aerodrome_charts(icao_code):
    """
    Fetch aerodrome charts for a given ICAO code from Chile AIP.
    
    Args:
        icao_code (str): 4-letter ICAO code (e.g., 'SCEL', 'SCIE')
        
    Returns:
        list: List of dictionaries with 'name', 'url', and 'type' keys
    """
    icao_code = icao_code.upper()
    charts = []
    seen_urls = set()
    
    try:
        # Get all procedure pages
        pages = get_all_proc_pages()
        
        for page_url in pages:
            response = requests.get(page_url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'lxml')
            
            # Find all PDF links for this ICAO code
            for link in soup.find_all('a', href=True):
                href = link['href']
                
                # Only process PDF links for this airport
                if not href.lower().endswith('.pdf'):
                    continue
                
                # Check if this is for our airport
                if f'/{icao_code}/' not in href.upper():
                    continue
                
                # Skip blank/placeholder pages
                if 'LEFT%20BLANK' in href or 'LEFT BLANK' in href:
                    continue
                
                # Get chart name from link text or extract from URL
                chart_name = link.get_text(strip=True)
                if not chart_name or chart_name == '#':
                    # Extract from filename
                    filename = href.rsplit('/', 1)[-1]
                    filename = unquote(filename)  # Decode %20 etc
                    chart_name = filename.replace('.pdf', '').replace(icao_code + ' ', '')
                
                # Build full URL (already absolute in source)
                if href.startswith('http'):
                    full_url = href
                else:
                    full_url = urljoin(BASE_URL, href)
                
                # Ensure URL is properly encoded
                # The source URLs are already encoded, but let's normalize
                if '%20' not in full_url and ' ' in full_url:
                    # Split and encode filename
                    parts = full_url.rsplit('/', 1)
                    if len(parts) == 2:
                        full_url = parts[0] + '/' + quote(parts[1], safe='')
                
                # Skip duplicates
                if full_url in seen_urls:
                    continue
                seen_urls.add(full_url)
                
                # Categorize the chart
                chart_type = categorize_chart(chart_name)
                
                # Clean up chart name - add ICAO prefix if not present
                if not chart_name.upper().startswith(icao_code):
                    chart_name = f"{icao_code} {chart_name}"
                
                charts.append({
                    'name': chart_name,
                    'url': full_url,
                    'type': chart_type
                })
        
        return charts
        
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            print(f"Airport {icao_code} not found in Chile AIP")
            return []
        raise Exception(f"HTTP error fetching charts for {icao_code}: {e}")
    except Exception as e:
        raise Exception(f"Error fetching charts for {icao_code}: {e}")


# For CLI compatibility
if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python chile_scraper.py <ICAO_CODE>")
        print("Example: python chile_scraper.py SCEL")
        print("\nCommon airports:")
        print("  - SCEL: Santiago (Arturo Merino Benítez)")
        print("  - SCIE: Concepción (Carriel Sur)")
        print("  - SCDA: Iquique (Diego Aracena)")
        print("  - SCFA: Antofagasta (Andrés Sabella)")
        print("  - SCAR: Arica (Chacalluta)")
        print("  - SCIP: Isla de Pascua (Mataveri)")
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

#!/usr/bin/env python3
"""
Belgium and Luxembourg eAIP Scraper
Scrapes aerodrome charts from skeyes.be eAIP (Eurocontrol standard)

ICAO prefixes:
- EB** : Belgium (EBBR Brussels, EBAW Antwerp, EBCI Charleroi, EBLG Liege, EBOS Ostend)
- EL** : Luxembourg (ELLX Luxembourg)

Base URL: https://ops.skeyes.be/html/belgocontrol_static/eaip/eAIP_Main/
Airport pages: html/eAIP/EB-AD-2.{ICAO}-en-GB.html
Charts in AD 2.24 section tables with full PDF URLs
"""

import requests
from bs4 import BeautifulSoup
import re
import sys


BASE_URL = "https://ops.skeyes.be/html/belgocontrol_static/eaip/eAIP_Main"


def get_session():
    """Create a session with browser-like headers to avoid 403 blocks"""
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    })
    return session


def get_airport_page_url(icao_code):
    """
    Construct the URL for an airport's eAIP page.
    
    Args:
        icao_code (str): 4-letter ICAO code (e.g., 'EBBR', 'ELLX')
        
    Returns:
        str: Full URL to airport page
    """
    # Determine country prefix for the page URL
    # Belgium uses EB- prefix, Luxembourg uses EL- prefix in the URL
    if icao_code.startswith('EB'):
        country_prefix = 'EB'
    elif icao_code.startswith('EL'):
        country_prefix = 'EB'  # Luxembourg is also in the EB (Belgium) AIP
    else:
        country_prefix = 'EB'
    
    return f"{BASE_URL}/html/eAIP/{country_prefix}-AD-2.{icao_code}-en-GB.html"


def categorize_chart(chart_name, chart_code):
    """
    Categorize a chart based on its name and code.
    
    Args:
        chart_name (str): Name/description of the chart
        chart_code (str): Chart code like AD 2.EBBR-SID.01
        
    Returns:
        str: Chart category (SID/STAR/Approach/Airport Diagram/General)
    """
    name_upper = chart_name.upper()
    code_upper = chart_code.upper()
    
    # Check chart code first (more reliable)
    if '-SID' in code_upper:
        return 'SID'
    if '-STAR' in code_upper:
        return 'STAR'
    if '-IAC' in code_upper:
        return 'Approach'
    if '-ADC' in code_upper or '-GMC' in code_upper or '-APDC' in code_upper:
        return 'Airport Diagram'
    if '-VAC' in code_upper:
        return 'Approach'  # Visual approach charts
    if '-AOC' in code_upper or '-PATC' in code_upper or '-ATCSMAC' in code_upper:
        return 'General'
    
    # Fallback to name-based categorization
    if 'SID' in name_upper or 'DEPARTURE' in name_upper:
        return 'SID'
    if 'STAR' in name_upper or 'ARRIVAL' in name_upper:
        return 'STAR'
    if any(kw in name_upper for kw in ['APPROACH', 'ILS', 'LOC', 'VOR', 'RNP', 'RNAV', 'NDB', 'IAC']):
        return 'Approach'
    if any(kw in name_upper for kw in ['AERODROME CHART', 'GROUND MOVEMENT', 'PARKING', 'DOCKING', 'GMC', 'ADC', 'APDC']):
        return 'Airport Diagram'
    
    return 'General'


def get_aerodrome_charts(icao_code):
    """
    Fetch aerodrome charts for a given ICAO code from Belgium/Luxembourg eAIP.
    
    Args:
        icao_code (str): 4-letter ICAO code (e.g., 'EBBR', 'ELLX')
        
    Returns:
        list: List of dictionaries with 'name', 'url', and 'type' keys
    """
    charts = []
    icao_code = icao_code.upper()
    
    # Validate ICAO prefix
    if not icao_code.startswith(('EB', 'EL')):
        print(f"Warning: {icao_code} doesn't appear to be a Belgium (EB) or Luxembourg (EL) airport")
        return charts
    
    try:
        session = get_session()
        airport_url = get_airport_page_url(icao_code)
        
        print(f"Fetching {airport_url}")
        
        response = session.get(airport_url, timeout=30)
        
        if response.status_code == 404:
            print(f"Airport {icao_code} not found in Belgium/Luxembourg eAIP")
            return charts
        
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find all PDF links in the page
        # The structure has tables with chart codes and PDF links
        # PDF URLs are absolute: https://ops.skeyes.be/html/belgocontrol_static/eaip/eAIP_Main/graphics/eAIP/ICAO_TYPE_vXX.pdf
        
        for link in soup.find_all('a', href=True):
            href = link.get('href', '')
            
            # Only process PDF links from graphics/eAIP
            if not href.endswith('.pdf') or 'graphics/eAIP' not in href:
                continue
            
            # Extract chart name - look in the parent table structure
            # The chart name is usually in a previous <td> in the same or previous row
            chart_name = ''
            chart_code = ''
            
            # Navigate up to find the table row
            parent_td = link.find_parent('td')
            if parent_td:
                parent_tr = parent_td.find_parent('tr')
                if parent_tr:
                    # Look for the previous row which might have the chart name
                    prev_tr = parent_tr.find_previous_sibling('tr')
                    if prev_tr:
                        tds = prev_tr.find_all('td')
                        if len(tds) >= 2:
                            # First td often has the chart code, second has the name
                            chart_code = tds[0].get_text(strip=True)
                            chart_name = tds[1].get_text(strip=True)
                        elif len(tds) == 1:
                            chart_name = tds[0].get_text(strip=True)
            
            # If we couldn't find the name, extract from filename
            if not chart_name:
                # Extract from URL like ELLX_ADC01_v52.pdf
                filename = href.split('/')[-1]
                chart_name = filename.replace('.pdf', '').replace('_', ' ')
            
            # Clean up chart code
            if not chart_code:
                # Try to extract from filename
                filename = href.split('/')[-1]
                # Pattern: ICAO_TYPE##_vXX.pdf
                match = re.match(r'([A-Z]{4})_([A-Z]+\d*[a-z]?)_v\d+\.pdf', filename)
                if match:
                    chart_code = f"AD 2.{match.group(1)}-{match.group(2)}"
            
            # Get the PDF URL (it should be absolute already)
            if href.startswith('http'):
                pdf_url = href
            else:
                # Make it absolute if needed
                pdf_url = f"{BASE_URL}/{href.lstrip('../')}"
            
            # Categorize the chart
            chart_type = categorize_chart(chart_name, chart_code)
            
            charts.append({
                'name': chart_name if chart_name else chart_code,
                'url': pdf_url,
                'type': chart_type
            })
        
        # Remove duplicates while preserving order
        seen_urls = set()
        unique_charts = []
        for chart in charts:
            if chart['url'] not in seen_urls:
                seen_urls.add(chart['url'])
                unique_charts.append(chart)
        
        return unique_charts
        
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            print(f"Airport {icao_code} not found in Belgium/Luxembourg eAIP")
        else:
            print(f"HTTP error fetching charts for {icao_code}: {e}")
        return charts
    except Exception as e:
        print(f"Error fetching charts for {icao_code}: {e}")
        import traceback
        traceback.print_exc()
        return charts


def main():
    if len(sys.argv) < 2:
        print("Usage: python belgium_luxembourg_scraper.py <ICAO_CODE>")
        print("Example: python belgium_luxembourg_scraper.py EBBR")
        print("         python belgium_luxembourg_scraper.py ELLX")
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

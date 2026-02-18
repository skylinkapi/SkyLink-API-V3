#!/usr/bin/env python3
"""
UK eAIP Scraper
Scrapes aerodrome charts from UK NATS AIP (Eurocontrol structure)
https://www.aurora.nats.co.uk/

ICAO prefix: EG* (EGLL, EGKK, EGCC, EGGW, EGSS, etc.)
"""

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote
import re
import sys
import warnings

# Suppress XML parsed as HTML warning
warnings.filterwarnings("ignore", category=UserWarning, module='bs4')


NATS_AIP_PAGE = "https://nats-uk.ead-it.com/cms-nats/opencms/en/Publications/AIP/"
BASE_URL = "https://www.aurora.nats.co.uk/htmlAIP/Publications/"


def get_current_airac_folder():
    """
    Get the current AIRAC folder from the NATS AIP page.
    Looks for the "Online Version" link containing the AIRAC date.
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(NATS_AIP_PAGE, headers=headers, timeout=30)
        response.raise_for_status()
        
        # Look for the Online Version link with AIRAC pattern
        # Pattern: https://www.aurora.nats.co.uk/htmlAIP/Publications/2026-01-22-AIRAC/html/index-en-GB.html
        match = re.search(r'Publications/(\d{4}-\d{2}-\d{2}-AIRAC)/html/index-en-GB\.html', response.text)
        if match:
            return match.group(1)
        
        # Alternative: parse the HTML
        soup = BeautifulSoup(response.text, 'html.parser')
        for link in soup.find_all('a', href=True):
            href = link['href']
            match = re.search(r'(\d{4}-\d{2}-\d{2}-AIRAC)', href)
            if match:
                return match.group(1)
        
        return None
        
    except Exception as e:
        print(f"Error getting AIRAC folder: {e}")
        return None


def get_airport_page_url(icao_code, airac_folder):
    """
    Construct the URL for an airport's eAIP page.
    Format: EG-AD-2.{ICAO}-en-GB.html
    """
    return f"{BASE_URL}{airac_folder}/html/eAIP/EG-AD-2.{icao_code}-en-GB.html"


def categorize_chart(chart_name):
    """Categorize chart based on its name."""
    name_upper = chart_name.upper()
    
    # SID charts - check before ground (some charts mention "departure" in context)
    if any(keyword in name_upper for keyword in ['SID', 'STANDARD INSTRUMENT DEPARTURE']):
        return 'sid'
    # Generic departure (but not ground movement)
    if 'DEPARTURE' in name_upper and 'GROUND' not in name_upper:
        return 'sid'
    
    # STAR charts - check before approach
    if any(keyword in name_upper for keyword in ['STAR', 'STANDARD ARRIVAL']):
        return 'star'
    # Generic arrival (but not visual approach)
    if 'ARRIVAL' in name_upper and 'APPROACH' not in name_upper:
        return 'star'
    
    # Approach charts
    if any(keyword in name_upper for keyword in ['APPROACH', 'ILS', 'LOC', 'VOR', 'NDB', 
                                                   'RNP', 'RNAV', 'GLS', 'IAC', 'CAT II',
                                                   'CAT III', 'CATII', 'CATIII']):
        return 'approach'
    
    # Ground/Airport diagrams
    if any(keyword in name_upper for keyword in ['AERODROME CHART', 'ADC', 'GROUND MOVEMENT', 
                                                   'PARKING', 'DOCKING', 'AIRCRAFT STAND',
                                                   'AERODROME OBSTACLE', 'TERRAIN', 'GMC',
                                                   'TAXI', 'APRON', 'HOT SPOT']):
        return 'airport_diagram'
    
    # Noise, procedures, general info
    if any(keyword in name_upper for keyword in ['NOISE', 'VISUAL MANOEUVRING', 'VFR',
                                                   'HELICOPTER', 'RADAR', 'INITIAL APPROACH']):
        return 'airport_diagram'
    
    # Default
    return 'airport_diagram'


def extract_chart_name_from_reference(ref_code, icao_code):
    """
    Extract a readable chart name from the UK AIP reference code.
    
    UK AIP chart references are like: AD 2.EGLL-2-1, AD 2.EGLL-6-3, etc.
    The number after the hyphen indicates chart category:
    - 2: Aerodrome Chart (ADC) / Ground Movement
    - 3: Helicopter 
    - 4: Visual Approach / Area chart
    - 5: Initial Approach / Radio Failure
    - 6: SID (Standard Instrument Departure)
    - 7: STAR (Standard Terminal Arrival Route)
    - 8: Instrument Approach Chart (IAC)
    
    Args:
        ref_code: Reference like "AD 2.EGLL-2-1"
        icao_code: ICAO code like "EGLL"
        
    Returns:
        Tuple of (chart_name, chart_type)
    """
    # Pattern: AD 2.XXXX-section-number
    match = re.search(rf'{icao_code}-(\d+)-(\d+)', ref_code, re.IGNORECASE)
    if not match:
        return ref_code, 'airport_diagram'
    
    section = int(match.group(1))
    chart_num = match.group(2)
    
    # Map section numbers to chart types and names
    section_info = {
        2: ('Aerodrome Chart', 'airport_diagram'),
        3: ('Helicopter Chart', 'airport_diagram'),
        4: ('Visual Approach Chart', 'airport_diagram'),
        5: ('Initial Approach Chart', 'approach'),
        6: ('SID', 'sid'),
        7: ('STAR', 'star'),
        8: ('Instrument Approach Chart', 'approach'),
        9: ('Missed Approach', 'approach')
    }
    
    section_name, chart_type = section_info.get(section, (f'Chart Section {section}', 'airport_diagram'))
    
    # Build descriptive name
    chart_name = f"{icao_code} {section_name} {chart_num}"
    
    return chart_name, chart_type


def get_aerodrome_charts(icao_code):
    """
    Get all aerodrome charts for a given ICAO code from UK eAIP.
    
    Args:
        icao_code: 4-letter ICAO code (e.g., 'EGLL', 'EGKK')
        
    Returns:
        List of dictionaries with 'name', 'url', and 'type' keys
    """
    charts = []
    icao_code = icao_code.upper()
    
    try:
        # Get current AIRAC folder
        airac_folder = get_current_airac_folder()
        if not airac_folder:
            print("Could not determine current AIRAC folder")
            return charts
        
        print(f"Using AIRAC: {airac_folder}")
        
        # Get airport page
        airport_url = get_airport_page_url(icao_code, airac_folder)
        print(f"Fetching: {airport_url}")
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(airport_url, headers=headers, timeout=30)
        
        if response.status_code == 404:
            print(f"Airport {icao_code} not found in UK eAIP")
            return charts
        
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find all PDF links
        seen_urls = set()
        
        for link in soup.find_all('a', href=True):
            href = link['href']
            
            # Only process PDF links
            if '.pdf' not in href.lower():
                continue
            
            # Get the link text (reference code like "AD 2.EGLL-2-1")
            ref_code = link.get_text(strip=True)
            
            # Build full URL
            if href.startswith('http'):
                chart_url = href
            else:
                chart_url = urljoin(airport_url, href)
            
            # Skip duplicates
            if chart_url in seen_urls:
                continue
            seen_urls.add(chart_url)
            
            # Extract chart name and type from the reference code
            chart_name, chart_type = extract_chart_name_from_reference(ref_code, icao_code)
            
            charts.append({
                'name': chart_name,
                'url': chart_url,
                'type': chart_type
            })
        
        return charts
        
    except requests.exceptions.HTTPError as e:
        print(f"HTTP error fetching charts for {icao_code}: {e}")
        return charts
    except Exception as e:
        print(f"Error scraping {icao_code}: {e}")
        import traceback
        traceback.print_exc()
        return charts


def main():
    if len(sys.argv) < 2:
        print("Usage: python uk_scraper.py <ICAO_CODE>")
        print("Example: python uk_scraper.py EGLL")
        sys.exit(1)
    
    icao_code = sys.argv[1].upper()
    
    print(f"Fetching charts for {icao_code}...")
    charts = get_aerodrome_charts(icao_code)
    
    if charts:
        print(f"\nFound {len(charts)} charts:")
        
        # Group by type
        by_type = {}
        for chart in charts:
            t = chart['type']
            if t not in by_type:
                by_type[t] = []
            by_type[t].append(chart)
        
        for chart_type in ['airport_diagram', 'sid', 'star', 'approach']:
            if chart_type in by_type:
                print(f"\n  {chart_type}:")
                for chart in by_type[chart_type]:
                    print(f"    - {chart['name']}")
                    print(f"      {chart['url']}")
    else:
        print("No charts found")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Pakistan eAIP Scraper
Scrapes aerodrome charts from Pakistan PAA eAIP
https://paa.gov.pk/aeronautical-information/electronic-aeronautical-information-publication

This scraper fetches the left menu HTML directly and parses PDF links for airports.
"""

import re
import sys
import requests

# Disable SSL warnings
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# eAIP base URL pattern - update the date portion for new cycles
EAIP_BASE = "https://paawebadmin.paa.gov.pk/media/eaip/04-25/eAIP"
LEFT_MENU_URL = f"{EAIP_BASE}/left.htm"

# Mapping of ICAO codes to filename prefixes used in the eAIP
# This mapping is based on the actual file naming in the Pakistan eAIP
ICAO_TO_FILENAME = {
    'OPBW': 'bah',              # Bahawalpur
    'OPCH': 'chitral',          # Chitral
    'OPDB': 'dalbandin',        # Dalbandin
    'OPDI': 'di_khan',          # Dera Ismail Khan
    'OPDG': 'dg_khan',          # Dera Ghazi Khan
    'OPFA': 'faislabad',        # Faisalabad (note: misspelling in eAIP)
    'OPGT': 'gilgit',           # Gilgit
    'OPGW': 'NewGwadar',        # New Gwadar
    'OPKC': 'karachi',          # Karachi/Jinnah International
    'OPKD': 'HYDERABAD',        # Hyderabad
    'OPLA': 'lahore',           # Lahore
    'OPMJ': 'moenjodaro',       # Mohenjo-daro
    'OPMT': 'multan',           # Multan
    'OPNH': 'nawabshah',        # Nawabshah
    'OPPG': 'panjgur',          # Panjgur
    'OPPS': 'pasni',            # Pasni
    'OPPC': 'peshawar',         # Peshawar
    'OPQT': 'quetta',           # Quetta
    'OPRK': 'rahim_yar_khan',   # Rahim Yar Khan
    'OPIS': 'OPIS',             # Islamabad
    'OPSD': 'skardu',           # Skardu
    'OPSS': 'saidu_sharif',     # Saidu Sharif
    'OPSK': 'sukkur',           # Sukkur
    'OPST': 'sialkot',          # Sialkot
    'OPTA': 'turbat',           # Turbat
    'OPZB': 'zhob',             # Zhob
}


def get_aerodrome_charts(icao_code, verbose=False):
    """
    Get aerodrome charts for a given ICAO code from Pakistan eAIP
    
    Args:
        icao_code: 4-letter ICAO code (e.g., 'OPKC', 'OPLA', 'OPIS')
        verbose: Print debug information
        
    Returns:
        List of dictionaries with 'name', 'url', and 'type' keys
    """
    icao_code = icao_code.upper()
    charts = []
    
    try:
        if verbose:
            print(f"Fetching eAIP menu from {LEFT_MENU_URL}")
        
        response = requests.get(LEFT_MENU_URL, verify=False, timeout=30)
        response.raise_for_status()
        html_content = response.text
        
        if verbose:
            print(f"Menu fetched ({len(html_content)} bytes), searching for {icao_code}...")
        
        # Parse the JavaScript menu structure to find airport entries
        # Pattern: stIT("...",["AIRPORT NAME (ICAO)"],"p3i0");
        # Pattern: stIT("...",["Aerodrome Data","AD/filename_data.pdf"],"p1i0");
        # Pattern: stIT("...",["Charts related to Aerodrome","AD/filename_chart.pdf"],"p1i0");
        
        # First, try to find the airport by ICAO code in the menu
        icao_pattern = re.compile(rf'\(({icao_code})\)', re.IGNORECASE)
        if icao_pattern.search(html_content):
            if verbose:
                print(f"Found airport {icao_code} in menu")
        else:
            if verbose:
                print(f"Airport {icao_code} not found directly in menu")
        
        # Try to find the filename prefix for this ICAO
        filename_prefix = ICAO_TO_FILENAME.get(icao_code)
        
        if filename_prefix:
            # Construct PDF URL for charts
            chart_pdf = f"{EAIP_BASE}/AD/{filename_prefix}_chart.pdf"
            charts.append({
                'name': f'{icao_code} - Charts',
                'url': chart_pdf,
                'type': 'GND'
            })
            if verbose:
                print(f"Added: {icao_code} - Charts -> {chart_pdf}")
        else:
            # Try to find PDF links that contain the ICAO code
            pdf_pattern = re.compile(rf'"AD/([^"]*\.pdf)"', re.IGNORECASE)
            all_pdfs = pdf_pattern.findall(html_content)
            
            # Look for chart PDFs that might match this airport (skip data PDFs)
            for pdf_file in all_pdfs:
                if icao_code.lower() in pdf_file.lower() and 'chart' in pdf_file.lower():
                    pdf_url = f"{EAIP_BASE}/AD/{pdf_file}"
                    charts.append({'name': f'{icao_code} - Charts', 'url': pdf_url, 'type': 'GND'})
                    if verbose:
                        print(f"Found: {icao_code} - Charts -> {pdf_url}")
                    break
            
            if not charts and verbose:
                print(f"No matching PDFs found for {icao_code}")
                print(f"Available airport PDFs ({len(all_pdfs)} total):")
                for pdf in sorted(set(all_pdfs))[:20]:
                    print(f"  {pdf}")
        
        return charts
        
    except requests.RequestException as e:
        if verbose:
            print(f"Error fetching eAIP: {e}")
        return []
    except Exception as e:
        if verbose:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
        return []


def categorize_chart(name):
    """Categorize chart by name."""
    name_upper = name.upper()
    if 'SID' in name_upper or 'DEPARTURE' in name_upper:
        return 'SID'
    elif 'STAR' in name_upper or 'ARRIVAL' in name_upper:
        return 'STAR'
    elif 'APPROACH' in name_upper or 'APP' in name_upper or 'ILS' in name_upper or 'VOR' in name_upper or 'RNAV' in name_upper:
        return 'APP'
    elif 'TAXI' in name_upper or 'GROUND' in name_upper or 'PARKING' in name_upper or 'CHART' in name_upper:
        return 'GND'
    else:
        return 'GEN'


if __name__ == "__main__":
    # Test with command line argument
    if len(sys.argv) > 1:
        icao = sys.argv[1]
        print(f"Fetching charts for {icao}...")
        charts = get_aerodrome_charts(icao, verbose=True)
        if charts:
            print(f"\nFound {len(charts)} chart(s):")
            for chart in charts:
                print(f"  - {chart['name']} ({chart['type']})")
                print(f"    URL: {chart['url']}")
        else:
            print("No charts found")
    else:
        # Default test with Karachi
        print("Testing with OPKC (Karachi)...")
        charts = get_aerodrome_charts("OPKC", verbose=True)
        if charts:
            print(f"\nFound {len(charts)} chart(s):")
            for chart in charts:
                print(f"  - {chart['name']} ({chart['type']})")
                print(f"    URL: {chart['url']}")

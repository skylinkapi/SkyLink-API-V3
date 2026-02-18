#!/usr/bin/env python3
"""
ASECNA eAIP Scraper
Scrapes aerodrome charts from ASECNA AIP covering 18 African countries.

Base URL: https://aim.asecna.aero/html/eAIP/
Charts URL pattern: FR-_{CC}AD-2.ATLAS.{ICAO}-fr-FR.html

ASECNA Countries and codes:
01 = Bénin (DB*)
02 = Burkina Faso (DF*)
03 = Cameroun (FK*)
04 = Centrafrique (FE*)
05 = Congo (FC*)
06 = Côte d'Ivoire (DI*)
07 = Gabon (FO*)
08 = Guinée Equatoriale (FG*)
09 = Madagascar (FM*)
10 = Mali (GA*)
11 = Mauritanie (GQ*)
12 = Niger (DR*)
13 = Sénégal (GO*)
14 = Tchad (FT*)
15 = Togo (DX*)
16 = Comores (FM* - shared with Madagascar)
17 = Guinée Bissau (GG*)

Note: Rwanda has separate AIP at eAIP_Rwanda/
"""

import requests
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
from urllib.parse import urljoin, quote
import re
import sys
import warnings

# Suppress the XML/HTML parser warning
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)


BASE_URL = "https://aim.asecna.aero/html/eAIP/"

# ICAO prefix to country code mapping
ICAO_TO_COUNTRY = {
    'DB': '01',  # Bénin
    'DF': '02',  # Burkina Faso
    'FK': '03',  # Cameroun
    'FE': '04',  # Centrafrique
    'FC': '05',  # Congo
    'DI': '06',  # Côte d'Ivoire
    'FO': '07',  # Gabon
    'FG': '08',  # Guinée Equatoriale
    'FM': '09',  # Madagascar (also Comores)
    'GA': '10',  # Mali
    'GQ': '11',  # Mauritanie
    'DR': '12',  # Niger
    'GO': '13',  # Sénégal
    'FT': '14',  # Tchad
    'DX': '15',  # Togo
    'GG': '17',  # Guinée Bissau
    # Note: Comores (16) uses FM* prefix like Madagascar - needs special handling
}

# Country code to name mapping
COUNTRY_NAMES = {
    '01': 'Bénin',
    '02': 'Burkina Faso', 
    '03': 'Cameroun',
    '04': 'Centrafrique',
    '05': 'Congo',
    '06': "Côte d'Ivoire",
    '07': 'Gabon',
    '08': 'Guinée Equatoriale',
    '09': 'Madagascar',
    '10': 'Mali',
    '11': 'Mauritanie',
    '12': 'Niger',
    '13': 'Sénégal',
    '14': 'Tchad',
    '15': 'Togo',
    '16': 'Comores',
    '17': 'Guinée Bissau',
}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}


def get_country_code(icao_code):
    """Get ASECNA country code from ICAO prefix."""
    prefix = icao_code[:2].upper()
    return ICAO_TO_COUNTRY.get(prefix)


def categorize_chart(chart_name):
    """Categorize chart based on its filename."""
    name_upper = chart_name.upper()
    
    # SID charts (Standard Instrument Departure)
    if 'SID' in name_upper or '-DEP' in name_upper:
        return 'SID'
    
    # STAR charts (Standard Terminal Arrival Route)
    if 'STAR' in name_upper or '-ARR' in name_upper:
        return 'STAR'
    
    # Approach charts (IAC = Instrument Approach Chart)
    if any(x in name_upper for x in ['IAC', 'ILS', 'RNP', 'VOR', 'NDB', 'LOC', 'RNAV']):
        # Exclude STAR charts that might contain these
        if 'STAR' not in name_upper:
            return 'Approach'
    
    # Airport diagrams and ground charts
    if any(x in name_upper for x in ['ADC', 'APDC', 'AOC', 'PDC', 'GMC', 'PARK']):
        return 'Airport Diagram'
    
    # Visual charts
    if any(x in name_upper for x in ['VAC', 'VLC', 'VFR', 'VISUAL']):
        return 'Visual'
    
    # Area/Regional charts
    if any(x in name_upper for x in ['ARC', 'AREA', 'RMAC']):
        return 'Area Chart'
    
    # Instrument Landing Chart
    if 'ILC' in name_upper:
        return 'Approach'
    
    # Default
    return 'General'


def get_aerodrome_charts(icao_code):
    """
    Get all aerodrome charts for a given ICAO code from ASECNA eAIP.
    
    Args:
        icao_code: 4-letter ICAO code (e.g., 'DBBB', 'DFFD')
        
    Returns:
        List of dictionaries with 'name', 'url', and 'type' keys
    """
    icao_code = icao_code.upper()
    charts = []
    
    # Get country code from ICAO prefix
    country_code = get_country_code(icao_code)
    if not country_code:
        print(f"Unknown ICAO prefix for {icao_code}")
        return charts
    
    # Build the ATLAS page URL
    # Format: FR-_{CC}AD-2.ATLAS.{ICAO}-fr-FR.html
    atlas_url = f"{BASE_URL}FR-_{country_code}AD-2.ATLAS.{icao_code}-fr-FR.html"
    
    try:
        response = requests.get(atlas_url, headers=HEADERS, timeout=30)
        
        if response.status_code == 404:
            print(f"Airport {icao_code} not found in ASECNA eAIP")
            return charts
        
        if response.status_code != 200:
            print(f"Error fetching {atlas_url}: HTTP {response.status_code}")
            return charts
        
        soup = BeautifulSoup(response.text, 'lxml')
        
        # Find all PDF links
        for link in soup.find_all('a', href=True):
            href = link['href']
            
            if not href.lower().endswith('.pdf'):
                continue
            
            # Get chart name from link text or href
            chart_name = link.get_text(strip=True)
            if not chart_name:
                # Extract name from filename
                chart_name = href.split('/')[-1].replace('.pdf', '')
            
            # Build full URL - handle spaces in paths
            # The href is relative like: cartes/atlas/benin/Cotonou - Cadjehoun/01AD2-DBBB-ADC.pdf
            # Need to URL encode the path parts with spaces
            href_parts = href.split('/')
            encoded_parts = []
            for part in href_parts:
                if '.pdf' in part:
                    # Encode the filename
                    encoded_parts.append(quote(part, safe=''))
                else:
                    # Encode folder names with spaces
                    encoded_parts.append(quote(part, safe=''))
            
            encoded_href = '/'.join(encoded_parts)
            full_url = urljoin(atlas_url, encoded_href)
            
            # Categorize the chart
            chart_type = categorize_chart(chart_name)
            
            charts.append({
                'name': chart_name,
                'url': full_url,
                'type': chart_type
            })
        
        return charts
        
    except requests.exceptions.Timeout:
        print(f"Timeout fetching charts for {icao_code}")
        return charts
    except Exception as e:
        print(f"Error scraping {icao_code}: {e}")
        import traceback
        traceback.print_exc()
        return charts


def get_airports_for_country(country_code):
    """
    Get list of airport ICAO codes for a given ASECNA country code.
    Parses the menu page to find all airports.
    
    Args:
        country_code: 2-digit country code (e.g., '01' for Benin)
        
    Returns:
        List of ICAO codes
    """
    airports = []
    
    try:
        menu_url = f"{BASE_URL}FR-menu-fr-FR.html"
        response = requests.get(menu_url, headers=HEADERS, timeout=30)
        
        if response.status_code != 200:
            return airports
        
        # Find all AD 2.24 links for this country
        # Pattern: FR-{CC}-AD-2.html#_{CC}AD-2.24.{ICAO}
        pattern = rf'_{country_code}AD-2\.24\.([A-Z]{{4}})'
        matches = re.findall(pattern, response.text)
        
        airports = list(set(matches))
        return sorted(airports)
        
    except Exception as e:
        print(f"Error getting airports for country {country_code}: {e}")
        return airports


def main():
    if len(sys.argv) < 2:
        print("Usage: python asecna_scraper.py <ICAO_CODE>")
        print("Example: python asecna_scraper.py DBBB")
        print("\nSupported ICAO prefixes:")
        for prefix, code in sorted(ICAO_TO_COUNTRY.items()):
            print(f"  {prefix}* - {COUNTRY_NAMES.get(code, 'Unknown')}")
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

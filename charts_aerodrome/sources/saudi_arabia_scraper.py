#!/usr/bin/env python3
"""
Saudi Arabia eAIP Scraper
Scrapes aerodrome charts from Saudi Air Navigation Services (SANS) eAIP
https://aimss.sans.com.sa/assets/FileManagerFiles/History-en-SA.html

Eurocontrol-style eAIP with AD 2.24 charts section.
"""

import re
import sys
import requests
from urllib.parse import urljoin, quote

# Disable SSL warnings
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Base URLs
HISTORY_PAGE = "https://aimss.sans.com.sa/assets/FileManagerFiles/History-en-SA.html"
FILES_BASE = "https://aimss.sans.com.sa/assets/FileManagerFiles"


def get_latest_airac_folder(verbose=False):
    """Get the latest AIRAC folder name from the history page."""
    try:
        response = requests.get(HISTORY_PAGE, verify=False, timeout=30)
        response.raise_for_status()
        
        # Find AIRAC folder links
        airac_folders = re.findall(r'href="([^"]*AIRAC[^"]*)/index\.html"', response.text)
        
        if airac_folders:
            # Get the first one (currently effective)
            latest = airac_folders[0]
            if verbose:
                print(f"Found latest AIRAC folder: {latest}")
            return latest
        else:
            if verbose:
                print("No AIRAC folders found")
            return None
            
    except Exception as e:
        if verbose:
            print(f"Error getting AIRAC folder: {e}")
        return None


def get_airport_page_name(menu_content, icao_code):
    """Extract the full airport page filename from the menu content."""
    # Pattern: AD 2 OEJN JEDDAH - KING ABDULAZIZ INTERNATIONAL-en-GB.html
    pattern = rf'(AD 2 {icao_code} [^"\'<>]+-en-GB\.html)'
    match = re.search(pattern, menu_content)
    if match:
        return match.group(1)
    return None


def get_aerodrome_charts(icao_code, verbose=False):
    """
    Get aerodrome charts for a given ICAO code from Saudi Arabia eAIP.
    
    Args:
        icao_code: 4-letter ICAO code (e.g., 'OEJN', 'OERK')
        verbose: Print debug information
        
    Returns:
        List of dictionaries with 'name', 'url', and 'type' keys
    """
    icao_code = icao_code.upper()
    charts = []
    
    try:
        # Get the latest AIRAC folder
        airac_folder = get_latest_airac_folder(verbose)
        if not airac_folder:
            if verbose:
                print("Could not determine AIRAC folder")
            return []
        
        # Construct base URL (with encoded spaces in folder name)
        eaip_base = f"{FILES_BASE}/{quote(airac_folder)}/eAIP"
        
        # Fetch the menu to find airport page filename
        menu_url = f"{eaip_base}/menu.html"
        if verbose:
            print(f"Fetching menu: {menu_url}")
        
        response = requests.get(menu_url, verify=False, timeout=30)
        response.raise_for_status()
        
        # Find airport page name
        airport_page_name = get_airport_page_name(response.text, icao_code)
        if not airport_page_name:
            if verbose:
                print(f"Airport {icao_code} not found in Saudi eAIP menu")
            return []
        
        if verbose:
            print(f"Found airport page: {airport_page_name}")
        
        # Fetch the airport page (URL-encode the filename)
        airport_url = f"{eaip_base}/{quote(airport_page_name)}"
        if verbose:
            print(f"Fetching airport page: {airport_url}")
        
        response = requests.get(airport_url, verify=False, timeout=60)
        
        if response.status_code == 404:
            if verbose:
                print(f"Airport page not found for {icao_code}")
            return []
        
        response.raise_for_status()
        html_content = response.text
        
        if verbose:
            print(f"Airport page fetched ({len(html_content)} bytes)")
        
        # Find all PDF links
        pdf_pattern = re.compile(r'href="([^"]*\.pdf)"', re.IGNORECASE)
        pdf_links = pdf_pattern.findall(html_content)
        
        if verbose:
            print(f"Found {len(pdf_links)} PDF links")
        
        # Process each PDF link
        seen_urls = set()
        for pdf_href in pdf_links:
            # Skip obstacle data PDFs (not charts)
            if 'eTOD' in pdf_href or 'Obstacle' in pdf_href:
                continue
            
            # Resolve relative URL
            pdf_url = urljoin(airport_url, pdf_href)
            
            # URL-encode spaces in the path
            # The URLs have spaces in folder and file names
            pdf_url = pdf_url.replace(' ', '%20')
            
            # Skip duplicates
            if pdf_url in seen_urls:
                continue
            seen_urls.add(pdf_url)
            
            # Extract chart name from filename
            filename = pdf_href.split('/')[-1]
            chart_name = filename.replace('.pdf', '')
            
            # Categorize the chart
            chart_type = categorize_chart(chart_name)
            
            charts.append({
                'name': chart_name,
                'url': pdf_url,
                'type': chart_type
            })
        
        if verbose:
            print(f"Processed {len(charts)} unique charts")
        
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


def categorize_chart(chart_name):
    """Categorize chart based on chart name."""
    name_upper = chart_name.upper()
    
    # SID charts
    if 'SID' in name_upper or 'STANDARD DEPARTURE' in name_upper or 'DEPARTURE CHART' in name_upper:
        return 'SID'
    
    # STAR charts
    elif 'STAR' in name_upper or 'STANDARD ARRIVAL' in name_upper or 'ARRIVAL CHART' in name_upper:
        return 'STAR'
    
    # Approach charts
    elif any(x in name_upper for x in ['APPROACH', 'IAC', 'ILS', 'RNP', 'VOR', 'NDB', 'VISUAL']):
        return 'APP'
    
    # Ground charts
    elif any(x in name_upper for x in ['GROUND', 'TAXI', 'PARKING', 'DOCKING', 'APRON', 'ADC', 'AERODROME CHART']):
        return 'GND'
    
    # Area/general
    elif 'AREA CHART' in name_upper or 'TERRAIN' in name_upper or 'OBSTACLE' in name_upper:
        return 'GEN'
    
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
            
            # Group by type
            by_type = {}
            for chart in charts:
                t = chart['type']
                if t not in by_type:
                    by_type[t] = []
                by_type[t].append(chart)
            
            for chart_type in ['GEN', 'GND', 'SID', 'STAR', 'APP']:
                if chart_type in by_type:
                    print(f"\n{chart_type} ({len(by_type[chart_type])} charts):")
                    for chart in by_type[chart_type][:5]:
                        print(f"  - {chart['name']}")
                    if len(by_type[chart_type]) > 5:
                        print(f"  ... and {len(by_type[chart_type]) - 5} more")
        else:
            print("No charts found")
    else:
        # Default test with OEJN (Jeddah)
        print("Testing with OEJN (Jeddah - King Abdulaziz International)...")
        charts = get_aerodrome_charts("OEJN", verbose=True)
        if charts:
            print(f"\nFound {len(charts)} chart(s)")

#!/usr/bin/env python3
"""
Singapore eAIP Scraper
Scrapes aerodrome charts from Singapore CAAS AIM eAIP
https://aim-sg.caas.gov.sg/aip/

Eurocontrol-style eAIP with standard AD-2.24 charts section.
"""

import re
import sys
import requests
from urllib.parse import urljoin

# Disable SSL warnings
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Base URLs
BASE_URL = "https://aim-sg.caas.gov.sg"
AIP_PAGE = f"{BASE_URL}/aip/"


def get_latest_eaip_base(verbose=False):
    """Get the latest eAIP HTML base URL from the AIP page."""
    try:
        response = requests.get(AIP_PAGE, verify=False, timeout=30)
        response.raise_for_status()
        
        # Find eAIP index link
        # Pattern: /aim-content/uploads/aip/05-FEB-2026/AIP-1/2026-01-22-000000/html/index-en-GB.html
        eaip_links = re.findall(
            r'href="([^"]*aim-content/uploads/aip[^"]+index-en-GB\.html[^"]*)"', 
            response.text
        )
        
        if eaip_links:
            # Get the first (latest) link and extract base path
            eaip_path = eaip_links[0]
            # Remove the filename to get the html folder path
            html_base = eaip_path.rsplit('/', 1)[0]
            if verbose:
                print(f"Found latest eAIP base: {html_base}")
            return html_base
        else:
            if verbose:
                print("No eAIP links found on AIP page")
            return None
            
    except Exception as e:
        if verbose:
            print(f"Error getting eAIP base: {e}")
        return None


def get_aerodrome_charts(icao_code, verbose=False):
    """
    Get aerodrome charts for a given ICAO code from Singapore eAIP.
    
    Args:
        icao_code: 4-letter ICAO code (e.g., 'WSSS', 'WSSL')
        verbose: Print debug information
        
    Returns:
        List of dictionaries with 'name', 'url', and 'type' keys
    """
    icao_code = icao_code.upper()
    charts = []
    
    try:
        # Get the latest eAIP base path
        html_base = get_latest_eaip_base(verbose)
        if not html_base:
            if verbose:
                print("Could not determine eAIP base URL")
            return []
        
        # Construct the airport page URL
        # Pattern: SG-AD-2-WSSS-en-GB.html
        airport_page_url = f"{BASE_URL}{html_base}/eAIP/SG-AD-2-{icao_code}-en-GB.html"
        
        if verbose:
            print(f"Fetching airport page: {airport_page_url}")
        
        response = requests.get(airport_page_url, verify=False, timeout=60)
        
        if response.status_code == 404:
            if verbose:
                print(f"Airport {icao_code} not found in Singapore eAIP")
            return []
        
        response.raise_for_status()
        html_content = response.text
        
        if verbose:
            print(f"Airport page fetched ({len(html_content)} bytes)")
        
        # Find all PDF links with query string
        # Pattern: href="../../pdf/SG-AD-2-WSSS-*.pdf?s=..."
        pdf_pattern = re.compile(r'href="([^"]*\.pdf\?[^"]*)"', re.IGNORECASE)
        pdf_links = pdf_pattern.findall(html_content)
        
        if verbose:
            print(f"Found {len(pdf_links)} PDF links")
        
        # Process each PDF link
        seen_filenames = set()
        for pdf_href in pdf_links:
            # Skip old versions
            if '/old/' in pdf_href:
                continue
            
            # Get the base filename (before query string)
            filename = pdf_href.split('?')[0].split('/')[-1]
            
            # Skip duplicates
            if filename in seen_filenames:
                continue
            seen_filenames.add(filename)
            
            # Skip the main AD-2 document (not a chart)
            if filename == f'SG-AD-2-{icao_code}.pdf':
                continue
            
            # Resolve full URL
            pdf_url = urljoin(airport_page_url, pdf_href)
            
            # Extract chart name from filename
            chart_name = filename.replace('.pdf', '')
            # Remove redundant prefix like "SG-AD-2-WSSS-AD-2-WSSS-"
            chart_name = re.sub(rf'^SG-AD-2-{icao_code}-AD-2-{icao_code}-', '', chart_name)
            
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
    if 'SID' in name_upper:
        return 'SID'
    
    # STAR charts
    elif 'STAR' in name_upper:
        return 'STAR'
    
    # Approach charts
    elif any(x in name_upper for x in ['IAC', 'ILS', 'RNP', 'VOR', 'NDB', 'VISUAL', 'APCH']):
        return 'APP'
    
    # Ground/aerodrome charts
    elif any(x in name_upper for x in ['ADC', 'AOC', 'PATC', 'GMC', 'APDC', 'PARKING', 'TAXI']):
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
        # Default test with WSSS (Changi)
        print("Testing with WSSS (Singapore Changi Airport)...")
        charts = get_aerodrome_charts("WSSS", verbose=True)
        if charts:
            print(f"\nFound {len(charts)} chart(s)")

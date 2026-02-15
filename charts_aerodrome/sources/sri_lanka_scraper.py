#!/usr/bin/env python3
"""
Sri Lanka eAIP Scraper
Scrapes aerodrome charts from Sri Lanka AASL eAIP
https://www.aimibsrilanka.lk/eaip/current/index.html

Eurocontrol-style eAIP with standard AD-2.24 charts section.
"""

import re
import sys
import requests
from urllib.parse import urljoin, quote

# Disable SSL warnings
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Base URLs
BASE_URL = "https://www.aimibsrilanka.lk"
CURRENT_EAIP = f"{BASE_URL}/eaip/current/index.html"


def get_latest_eaip_base(verbose=False):
    """Get the latest eAIP HTML base URL by following redirects."""
    try:
        response = requests.get(CURRENT_EAIP, verify=False, timeout=30)
        response.raise_for_status()
        
        # Extract redirect path from meta refresh
        # Pattern: URL=../AIP_2503/Eurocontrol/SRI LANKA/2025-11-27-NON AIRAC/html/index.html
        redirect = re.search(r'URL=\.\./(.*?)"', response.text)
        
        if redirect:
            redirect_path = redirect.group(1)
            # URL-encode spaces in path
            encoded_path = quote(redirect_path, safe='/')
            # Build base URL (remove index.html)
            html_base = f"{BASE_URL}/eaip/{encoded_path}".rsplit('/', 1)[0]
            if verbose:
                print(f"Found eAIP base: {html_base}")
            return html_base
        else:
            if verbose:
                print("No redirect path found")
            return None
            
    except Exception as e:
        if verbose:
            print(f"Error getting eAIP base: {e}")
        return None


def get_aerodrome_charts(icao_code, verbose=False):
    """
    Get aerodrome charts for a given ICAO code from Sri Lanka eAIP.
    
    Args:
        icao_code: 4-letter ICAO code (e.g., 'VCBI', 'VCRI')
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
        # Pattern: EN-AD-2.VCBI-en-EN.html
        airport_page_url = f"{html_base}/eAIP/EN-AD-2.{icao_code}-en-EN.html"
        
        if verbose:
            print(f"Fetching airport page: {airport_page_url}")
        
        response = requests.get(airport_page_url, verify=False, timeout=60)
        
        if response.status_code == 404:
            if verbose:
                print(f"Airport {icao_code} not found in Sri Lanka eAIP")
            return []
        
        response.raise_for_status()
        html_content = response.text
        
        if verbose:
            print(f"Airport page fetched ({len(html_content)} bytes)")
        
        # Find all PDF links
        # Pattern: Maps/AD/VCBI/AD2.VCBI-ADC.pdf
        pdf_pattern = re.compile(r'href="([^"]*\.pdf)"', re.IGNORECASE)
        pdf_links = pdf_pattern.findall(html_content)
        
        if verbose:
            print(f"Found {len(pdf_links)} PDF links")
        
        # Process each PDF link
        seen_urls = set()
        for pdf_href in pdf_links:
            # Skip the main AD-2 document (not a chart)
            if pdf_href.startswith('../../pdf/'):
                continue
            
            # Resolve full URL
            pdf_url = urljoin(airport_page_url, pdf_href)
            
            # Skip duplicates
            if pdf_url in seen_urls:
                continue
            seen_urls.add(pdf_url)
            
            # Extract chart name from filename
            filename = pdf_href.split('/')[-1]
            chart_name = filename.replace('.pdf', '')
            # Clean up name (e.g., "AD2.VCBI-ADC" -> "ADC")
            chart_name = re.sub(rf'^AD2\.{icao_code}-', '', chart_name)
            
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
    elif any(x in name_upper for x in ['ADC', 'AOC', 'APDC', 'GMC', 'PATC', 'PARKING', 'TAXI']):
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
        # Default test with VCBI (Colombo Bandaranaike)
        print("Testing with VCBI (Colombo Bandaranaike International)...")
        charts = get_aerodrome_charts("VCBI", verbose=True)
        if charts:
            print(f"\nFound {len(charts)} chart(s)")

#!/usr/bin/env python3
"""
Qatar eAIP Scraper
Scrapes aerodrome charts from Qatar CAA eAIP
https://www.caa.gov.qa/en/aeronautical-information-management

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
CAA_AIM_PAGE = "https://www.caa.gov.qa/en/aeronautical-information-management"
EAIP_BASE = "https://www.aim.gov.qa/eaip"


def get_latest_airac_date(verbose=False):
    """Get the latest AIRAC effective date from the CAA AIM page."""
    try:
        response = requests.get(CAA_AIM_PAGE, verify=False, timeout=30)
        response.raise_for_status()
        
        # Find all AIRAC dates in the page
        airac_dates = re.findall(r'(\d{4}-\d{2}-\d{2})-AIRAC', response.text)
        
        if airac_dates:
            # Get the most recent date
            latest = sorted(set(airac_dates), reverse=True)[0]
            if verbose:
                print(f"Found latest AIRAC date: {latest}")
            return latest
        else:
            if verbose:
                print("No AIRAC dates found, using fallback")
            return None
            
    except Exception as e:
        if verbose:
            print(f"Error getting AIRAC date: {e}")
        return None


def get_aerodrome_charts(icao_code, verbose=False):
    """
    Get aerodrome charts for a given ICAO code from Qatar eAIP.
    
    Args:
        icao_code: 4-letter ICAO code (e.g., 'OTHH', 'OTBD')
        verbose: Print debug information
        
    Returns:
        List of dictionaries with 'name', 'url', and 'type' keys
    """
    icao_code = icao_code.upper()
    charts = []
    
    try:
        # Get the latest AIRAC date
        airac_date = get_latest_airac_date(verbose)
        if not airac_date:
            if verbose:
                print("Could not determine AIRAC date")
            return []
        
        # Construct the eAIP base URL
        eaip_html_base = f"{EAIP_BASE}/{airac_date}-AIRAC/html/eAIP"
        airport_page_url = f"{eaip_html_base}/AD-2.{icao_code}-en-GB.html"
        
        if verbose:
            print(f"Fetching airport page: {airport_page_url}")
        
        response = requests.get(airport_page_url, verify=False, timeout=30)
        
        if response.status_code == 404:
            if verbose:
                print(f"Airport {icao_code} not found in Qatar eAIP")
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
            # Skip AD-2 text document PDFs (not charts, often 404)
            if '/pdf/' in pdf_href or pdf_href.startswith('../../pdf/'):
                continue
            
            # Resolve relative URL
            pdf_url = urljoin(airport_page_url, pdf_href)
            
            # Skip duplicates
            if pdf_url in seen_urls:
                continue
            seen_urls.add(pdf_url)
            
            # Extract chart name from filename
            filename = pdf_href.split('/')[-1]
            chart_name = filename.replace('.pdf', '').replace('_', ' ')
            
            # Categorize the chart
            chart_type = categorize_chart(filename)
            
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


def categorize_chart(filename):
    """Categorize chart based on filename."""
    filename_upper = filename.upper()
    
    if 'SID' in filename_upper:
        return 'SID'
    elif 'STAR' in filename_upper:
        return 'STAR'
    elif 'IAC' in filename_upper or 'ILS' in filename_upper or 'RNP' in filename_upper or 'VOR' in filename_upper:
        return 'APP'
    elif 'ADC' in filename_upper or 'AD CHART' in filename_upper or 'CHART' in filename_upper.replace('_', ' '):
        return 'GND'
    elif 'AOC' in filename_upper or 'APDC' in filename_upper or 'PARK' in filename_upper or 'DOCK' in filename_upper:
        return 'GND'
    elif 'PATC' in filename_upper:
        return 'GND'
    elif 'ATSMAC' in filename_upper or 'BIRD' in filename_upper:
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
        # Default test with OTHH (Hamad International)
        print("Testing with OTHH (Hamad International Airport)...")
        charts = get_aerodrome_charts("OTHH", verbose=True)
        if charts:
            print(f"\nFound {len(charts)} chart(s)")

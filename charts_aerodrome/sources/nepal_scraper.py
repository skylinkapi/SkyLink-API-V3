#!/usr/bin/env python3
"""
Nepal eAIP Scraper
Scrapes aerodrome charts from Nepal CAAN eAIP
https://e-aip.caanepal.gov.np/welcome/listall/1
"""

import requests
from bs4 import BeautifulSoup
import re
import sys

BASE_URL = "https://e-aip.caanepal.gov.np"
AIP_URL = f"{BASE_URL}/welcome/listall/1"


def get_aerodrome_charts(icao_code, verbose=False):
    """
    Get aerodrome charts for a given ICAO code from Nepal eAIP
    
    Args:
        icao_code: 4-letter ICAO code (e.g., 'VNKT')
        verbose: Print debug information
        
    Returns:
        List of dictionaries with 'name', 'url', and 'type' keys
    """
    icao_code = icao_code.upper()
    
    if verbose:
        print(f"Fetching Nepal eAIP from {AIP_URL}")
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(AIP_URL, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find the link for the airport
        # Links are in format: <a href="...pdf">VNKT</a>
        for link in soup.find_all('a', href=True):
            link_text = link.get_text(strip=True)
            
            # Match exact ICAO code
            if link_text == icao_code:
                href = link['href']
                
                # Make sure it's a PDF link
                if '.pdf' in href.lower():
                    pdf_url = href if href.startswith('http') else f"{BASE_URL}{href}"
                    
                    if verbose:
                        print(f"Found PDF for {icao_code}: {pdf_url}")
                    
                    # Return single AD 2 document
                    return [{
                        'name': f'{icao_code} AD 2 Aerodrome',
                        'url': pdf_url,
                        'type': 'GEN'
                    }]
        
        if verbose:
            print(f"Airport {icao_code} not found in Nepal eAIP")
        
        return []
        
    except Exception as e:
        if verbose:
            print(f"Error scraping {icao_code}: {e}")
            import traceback
            traceback.print_exc()
        return []


def main():
    if len(sys.argv) < 2:
        print("Usage: python nepal_scraper.py <ICAO_CODE>")
        print("Example: python nepal_scraper.py VNKT")
        sys.exit(1)
    
    icao_code = sys.argv[1].upper()
    
    print(f"Fetching charts for {icao_code}...")
    charts = get_aerodrome_charts(icao_code, verbose=True)
    
    if charts:
        print(f"\nFound {len(charts)} document:")
        for chart in charts:
            print(f"  [{chart['type']}] {chart['name']}")
            print(f"    {chart['url']}")
    else:
        print("No charts found")


if __name__ == "__main__":
    main()

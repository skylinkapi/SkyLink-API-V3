#!/usr/bin/env python3
"""
Haiti AIP Scraper
Scrapes AIP document link from OFNAC (Office de la Navigation Aérienne de la Caraïbe)
URL: https://ofnac.gouv.ht/index.php/iaip/

ICAO prefix: MT*
Examples: MTPP (Port-au-Prince), MTCH (Cap-Haïtien), MTJA (Jacmel), MTCA (Les Cayes)

Haiti's AIP is provided as a single consolidated PDF document.
This scraper returns the latest AIP PDF link for any Haiti airport.
"""

import requests
from bs4 import BeautifulSoup
import re
import sys
import urllib3

# Disable SSL warnings for sites with certificate issues
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


BASE_URL = "https://ofnac.gouv.ht"
IAIP_URL = f"{BASE_URL}/index.php/iaip/"


def get_latest_aip_link():
    """
    Get the latest AIP Haiti PDF link from OFNAC website.
    
    Returns:
        tuple: (name, url) of the latest AIP document, or (None, None) if not found
    """
    try:
        response = requests.get(IAIP_URL, timeout=30, verify=False)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'lxml')
        
        # Find all links containing "AIP" and ".pdf"
        for link in soup.find_all('a', href=True):
            href = link['href']
            text = link.get_text(strip=True)
            
            # Look for the main AIP HAITI PDF link (not amendments or supplements pages)
            if 'AIP' in href.upper() and 'HAITI' in href.upper() and href.endswith('.pdf'):
                # Extract name from link text or construct from href
                if text and 'AIP HAITI' in text.upper():
                    name = text
                else:
                    # Extract from filename
                    filename = href.split('/')[-1].replace('.pdf', '').replace('-', ' ').replace('_', ' ')
                    name = filename
                
                return name, href
        
        # Fallback: search with regex in case BeautifulSoup parsing fails
        aip_pattern = r'href="([^"]*AIP[^"]*HAITI[^"]*\.pdf)"'
        match = re.search(aip_pattern, response.text, re.IGNORECASE)
        if match:
            url = match.group(1)
            # Try to find the link text
            text_pattern = r'>([^<]*AIP\s*HAITI[^<]*)<'
            text_match = re.search(text_pattern, response.text, re.IGNORECASE)
            name = text_match.group(1).strip() if text_match else "AIP HAITI"
            return name, url
        
        return None, None
        
    except requests.exceptions.RequestException as e:
        print(f"Error fetching AIP link: {e}")
        return None, None


def get_aerodrome_charts(icao_code):
    """
    Get the AIP document for a given Haiti ICAO code.
    
    Since Haiti provides a single consolidated AIP document,
    this returns the full AIP PDF link for any Haiti airport.
    
    Args:
        icao_code: 4-letter ICAO code (e.g., 'MTPP')
        
    Returns:
        List of dictionaries with 'name', 'url', and 'type' keys
    """
    icao_code = icao_code.upper()
    
    # Validate ICAO code is for Haiti (MT prefix)
    if not icao_code.startswith('MT'):
        print(f"Warning: {icao_code} does not appear to be a Haiti airport (MT* prefix)")
    
    charts = []
    
    name, url = get_latest_aip_link()
    
    if name and url:
        charts.append({
            'name': f"{icao_code} - {name}",
            'url': url,
            'type': 'General'
        })
    
    return charts


def main():
    """Command line interface for testing."""
    if len(sys.argv) < 2:
        print("Usage: python haiti_scraper.py <ICAO_CODE>")
        print("Example: python haiti_scraper.py MTPP")
        print("\nHaiti airports: MTPP (Port-au-Prince), MTCH (Cap-Haïtien), MTJA (Jacmel), MTCA (Les Cayes)")
        sys.exit(1)
    
    icao_code = sys.argv[1].upper()
    
    print(f"Fetching AIP for {icao_code}...")
    charts = get_aerodrome_charts(icao_code)
    
    if charts:
        print(f"\nFound {len(charts)} document:")
        for chart in charts:
            print(f"  [{chart['type']}] {chart['name']}")
            print(f"    {chart['url']}")
    else:
        print("No AIP document found")


if __name__ == "__main__":
    main()

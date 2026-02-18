#!/usr/bin/env python3
"""
Cayman Islands AIP Scraper
Scrapes AIP Aerodrome document link from Cayman Islands Airports Authority
URL: https://www.caymanairports.com/aeronautical-information-publication/

ICAO prefix: MW*
Examples: MWCR (Owen Roberts International, Grand Cayman), MWCB (Charles Kirkconnell, Cayman Brac)

Cayman Islands provides separate AIP PDFs (General, Enroute, Aerodrome).
This scraper returns the Aerodrome PDF link for any Cayman airport.
"""

import requests
from bs4 import BeautifulSoup
import re
import sys


BASE_URL = "https://www.caymanairports.com"
AIP_URL = f"{BASE_URL}/aeronautical-information-publication/"


def get_aerodrome_pdf_link():
    """
    Get the Aerodrome PDF link from Cayman Islands AIP page.
    
    Returns:
        tuple: (name, url) of the Aerodrome document, or (None, None) if not found
    """
    try:
        response = requests.get(AIP_URL, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'lxml')
        
        # Find the Aerodrome link under "Current AIP" section
        for link in soup.find_all('a', href=True):
            href = link['href']
            text = link.get_text(strip=True)
            
            # Look for the Aerodrome PDF link
            if text.lower() == 'aerodrome' and href.endswith('.pdf'):
                # Ensure full URL
                if not href.startswith('http'):
                    href = BASE_URL + href if href.startswith('/') else f"{BASE_URL}/{href}"
                
                return "Cayman Islands AIP - Aerodrome", href
        
        # Fallback: search with regex for Aerodrome PDF
        aerodrome_pattern = r'href="([^"]*Aerodrome[^"]*\.pdf)"'
        match = re.search(aerodrome_pattern, response.text, re.IGNORECASE)
        if match:
            url = match.group(1)
            if not url.startswith('http'):
                url = BASE_URL + url if url.startswith('/') else f"{BASE_URL}/{url}"
            return "Cayman Islands AIP - Aerodrome", url
        
        return None, None
        
    except requests.exceptions.RequestException as e:
        print(f"Error fetching AIP link: {e}")
        return None, None


def get_aerodrome_charts(icao_code):
    """
    Get the AIP Aerodrome document for a given Cayman Islands ICAO code.
    
    Args:
        icao_code: 4-letter ICAO code (e.g., 'MWCR', 'MWCB')
        
    Returns:
        List of dictionaries with 'name', 'url', and 'type' keys
    """
    icao_code = icao_code.upper()
    
    # Validate ICAO code is for Cayman Islands (MW prefix)
    if not icao_code.startswith('MW'):
        print(f"Warning: {icao_code} does not appear to be a Cayman Islands airport (MW* prefix)")
    
    charts = []
    
    name, url = get_aerodrome_pdf_link()
    
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
        print("Usage: python cayman_scraper.py <ICAO_CODE>")
        print("Example: python cayman_scraper.py MWCR")
        print("\nCayman Islands airports:")
        print("  MWCR - Owen Roberts International (Grand Cayman)")
        print("  MWCB - Charles Kirkconnell International (Cayman Brac)")
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

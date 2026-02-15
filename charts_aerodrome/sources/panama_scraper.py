#!/usr/bin/env python3
"""
Panama AIP Scraper
Scrapes aerodrome charts from Panama Civil Aviation Authority
URL: https://www.aeronautica.gob.pa/ais-aip/

ICAO prefix: MP*
Examples: MPTO (Tocumen International), MPMG (Marcos A. Gelabert), 
          MPDA (David), MPBO (Bocas del Toro), MPCH (Changuinola),
          MPPA (Panamá Pacífico), MPEJ (Enrique Malek), MPSM (Scarlett Martínez)

Panama provides individual aerodrome PDFs under section "3. AD"
with all airport info including charts in a single PDF per airport.
"""

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote
import re
import sys


BASE_URL = "https://www.aeronautica.gob.pa"
AIP_URL = f"{BASE_URL}/ais-aip/"


def get_aerodrome_pdf_link(icao_code):
    """
    Get the aerodrome PDF link for a given ICAO code from Panama AIP.
    
    Args:
        icao_code: 4-letter ICAO code (e.g., 'MPTO')
        
    Returns:
        tuple: (name, url) of the aerodrome document, or (None, None) if not found
    """
    icao_code = icao_code.upper()
    
    try:
        response = requests.get(AIP_URL, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'lxml')
        
        # Find links containing the ICAO code in section 3. AD
        # Format: AD 2.X-ICAO
        for link in soup.find_all('a', href=True):
            href = link['href']
            text = link.get_text(strip=True)
            
            # Look for aerodrome PDF with the ICAO code
            # The href format is like: "AIP PDF COMPLETO/1. AIP - Publicacion de Informacion Aeronautica/3. AD/AD 2.1-MPTO.pdf"
            if icao_code in href.upper() and '3. AD' in href and href.endswith('.pdf'):
                # Build full URL - the href is relative with spaces
                # Need to URL encode spaces and join with base URL
                encoded_href = href.replace(' ', '%20')
                full_url = urljoin(AIP_URL, encoded_href)
                
                # Get the name from link text
                name = text if text else f"AD - {icao_code}"
                
                return name, full_url
        
        # Fallback: search with regex for links with ICAO code in AD section
        # Pattern matches: href="...3. AD/AD 2.X-ICAO.pdf"
        pattern = rf'href="([^"]*3\. AD[^"]*{icao_code}[^"]*\.pdf)"'
        match = re.search(pattern, response.text, re.IGNORECASE)
        if match:
            href = match.group(1)
            encoded_href = href.replace(' ', '%20')
            full_url = urljoin(AIP_URL, encoded_href)
            
            return f"AD - {icao_code}", full_url
        
        return None, None
        
    except requests.exceptions.RequestException as e:
        print(f"Error fetching AIP page: {e}")
        return None, None


def get_aerodrome_charts(icao_code):
    """
    Get the aerodrome PDF for a given Panama ICAO code.
    
    Args:
        icao_code: 4-letter ICAO code (e.g., 'MPTO')
        
    Returns:
        List of dictionaries with 'name', 'url', and 'type' keys
    """
    icao_code = icao_code.upper()
    
    # Validate ICAO code is for Panama (MP prefix)
    if not icao_code.startswith('MP'):
        print(f"Warning: {icao_code} does not appear to be a Panama airport (MP* prefix)")
    
    charts = []
    
    name, url = get_aerodrome_pdf_link(icao_code)
    
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
        print("Usage: python panama_scraper.py <ICAO_CODE>")
        print("Example: python panama_scraper.py MPTO")
        print("\nPanama airports:")
        print("  MPTO - Tocumen International (Panama City)")
        print("  MPMG - Marcos A. Gelabert (Albrook)")
        print("  MPDA - David (Enrique Malek)")
        print("  MPBO - Bocas del Toro")
        print("  MPCH - Changuinola")
        print("  MPPA - Panama Pacifico")
        print("  MPEJ - Enrique Adolfo Jimenez")
        print("  MPSM - Scarlett Martinez")
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
        print(f"No aerodrome PDF found for {icao_code}")


if __name__ == "__main__":
    main()

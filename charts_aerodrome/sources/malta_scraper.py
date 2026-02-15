#!/usr/bin/env python3
"""
Malta AIP Scraper
Provides the link to the current Malta Aeronautical Information Publication (AIP) PDF

Process:
1. Get current AIP PDF URL from https://www.transport.gov.mt/aviation/air-navigation-services-aerodromes/aeronautical-information-publication-3764
2. Return the PDF link as a single GEN chart entry

ICAO prefix: LM* (LMML - Malta International Airport)
"""

import requests
import re
from bs4 import BeautifulSoup
import sys


BASE_URL = "https://www.transport.gov.mt/aviation/air-navigation-services-aerodromes/aeronautical-information-publication-3764"


def get_current_aip_url():
    """Get the URL of the current AIP PDF"""
    try:
        response = requests.get(BASE_URL, timeout=30, allow_redirects=True)
        final_url = response.url  # Get the final URL after redirects
        soup = BeautifulSoup(response.text, 'lxml')
        
        # Look for the "Click here for the Current Aeronautical Information Publication" link
        for link in soup.find_all('a', href=True):
            text = link.get_text().replace('\xa0', ' ').replace('\n', ' ').strip()
            if 'Click here for the Current' in text and 'Aeronautical Information Publication' in text:
                href = link['href']
                if '.pdf' in href:
                    # Return the full URL if it's already absolute, otherwise join with base
                    if href.startswith('http'):
                        pdf_url = href
                    else:
                        pdf_url = urljoin(BASE_URL, href)
                    
                    # Strip any fragment (like #page=1) from the URL
                    pdf_url = pdf_url.split('#')[0]
                    return pdf_url
    except Exception as e:
        return None


def get_aerodrome_charts(icao_code):
    """
    Get the Malta AIP PDF link for a given ICAO code

    Args:
        icao_code: 4-letter ICAO code (e.g., 'LMML')

    Returns:
        List with single dictionary containing the AIP PDF link as a GEN chart
    """
    charts = []

    try:
        # Get current AIP PDF URL
        pdf_url = get_current_aip_url()
        if not pdf_url:
            return charts

        # Return the main AIP PDF as a GEN chart
        charts.append({
            'name': f'Malta AIP - {icao_code}',
            'url': pdf_url,
            'type': 'GEN'
        })

        return charts

    except Exception as e:
        return charts


def main():
    if len(sys.argv) < 2:
        print("Usage: python malta_scraper.py <ICAO_CODE>")
        print("Example: python malta_scraper.py LMML")
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
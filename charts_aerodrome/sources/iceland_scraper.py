#!/usr/bin/env python3
"""
Iceland eAIP Scraper
Scrapes aerodrome charts from Iceland AIP following Eurocontrol structure
"""

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote
import re
import sys


BASE_URL = "https://eaip.isavia.is"


def get_latest_eaip_url():
    """Get the URL of the latest Iceland eAIP"""
    try:
        # Check the main page for current effective issue
        response = requests.get(f"{BASE_URL}/", timeout=30)
        soup = BeautifulSoup(response.text, 'lxml')
        
        # Look for the current effective date
        # The URL pattern is A_01-{AIRAC}_2026_{month}_{day}/
        # We need to find the latest one
        
        # For now, use the known current URL
        # TODO: Make this dynamic by parsing the main page
        return f"{BASE_URL}/A_01-2026_2026_01_22/"
        
    except Exception as e:
        print(f"Error getting latest eAIP URL: {e}")
        return None


def get_airport_page_url(icao_code):
    """Get the URL for a specific airport's page"""
    base_eaip = get_latest_eaip_url()
    if not base_eaip:
        return None
    
    # For Iceland, we need to find the correct airport page URL
    # This requires parsing the menu to find the mapping
    menu_url = f"{base_eaip}eAIP/menu.html"
    
    try:
        response = requests.get(menu_url, timeout=30)
        soup = BeautifulSoup(response.text, 'lxml')
        
        # Find the link for this ICAO - look for both BI-LS and BI-AD patterns
        for link in soup.find_all('a', href=True):
            href = link['href']
            text = link.get_text().strip()
            
            # Decode href properly - it may have UTF-8 encoding issues
            try:
                # Try to decode as UTF-8 if it contains encoding errors
                href_decoded = href.encode('latin1').decode('utf-8')
            except (UnicodeDecodeError, UnicodeEncodeError):
                href_decoded = href
            
            if f'BI-LS {icao_code}' in href_decoded and 'en-GB.html' in href_decoded and 'AD 2.24' in text:
                # Found the airport page URL
                url_part = href_decoded.split('#')[0]  # Remove anchor
                print(f"Found BI-LS URL: {url_part}")
                return urljoin(menu_url, url_part)
            elif f'BI-AD {icao_code}' in href_decoded and 'en-GB.html' in href_decoded and 'AD 2.24' in text:
                # Found the airport page URL (alternative pattern)
                url_part = href_decoded.split('#')[0]  # Remove anchor
                print(f"Found BI-AD URL: {url_part}")
                return urljoin(menu_url, url_part)
        
        # Fallback: try to construct the URL manually for known airports
        # This handles cases where the menu parsing fails due to encoding issues
        # Note: The general decoding fix above should handle most cases now
        
        return None
        
    except Exception as e:
        print(f"Error finding airport page URL for {icao_code}: {e}")
        return None


def categorize_chart(chart_name):
    """Categorize chart based on its name"""
    chart_name_upper = chart_name.upper()
    
    if 'SID' in chart_name_upper or 'DEPARTURE' in chart_name_upper:
        return 'SID'
    elif 'STAR' in chart_name_upper or 'ARRIVAL' in chart_name_upper:
        return 'STAR'
    elif 'APPROACH' in chart_name_upper or 'ILS' in chart_name_upper or 'LOC' in chart_name_upper \
            or 'NDB' in chart_name_upper or 'RNP' in chart_name_upper or 'GLS' in chart_name_upper:
        return 'APP'
    elif 'AERODROME' in chart_name_upper or 'GROUND' in chart_name_upper \
            or 'PARKING' in chart_name_upper or 'TAXI' in chart_name_upper:
        return 'GND'
    else:
        return 'GEN'


def get_aerodrome_charts(icao_code):
    """
    Get all aerodrome charts for a given ICAO code from Iceland eAIP
    
    Args:
        icao_code: 4-letter ICAO code (e.g., 'BIRK')
        
    Returns:
        List of dictionaries with 'name', 'url', and 'type' keys
    """
    charts = []
    
    try:
        # Get airport page URL
        airport_url = get_airport_page_url(icao_code)
        if not airport_url:
            print(f"Could not determine airport page URL for {icao_code}")
            return charts
        
        print(f"Fetching {airport_url}")
        
        # Get the airport page
        response = requests.get(airport_url, timeout=30)
        if response.status_code != 200:
            print(f"Error: Got status code {response.status_code}")
            return charts
        
        soup = BeautifulSoup(response.text, 'lxml')
        html_content = response.text
        
        # Look for PDF links in the page
        pdf_count = html_content.lower().count('.pdf')
        print(f"Found {pdf_count} PDF references in HTML")
        
        # Find all PDF links
        for link in soup.find_all('a', href=True):
            href = link['href']
            
            # Only process PDF links
            if '.pdf' not in href.lower():
                continue
            
            # Get the chart name from the link text or nearby text
            chart_name = link.get_text(strip=True)
            
            # If no text in link, try to find it from parent elements
            if not chart_name:
                td_parent = link.find_parent('td')
                if td_parent:
                    chart_name = td_parent.get_text(strip=True)
            
            # If still no name, use the filename
            if not chart_name:
                chart_name = href.split('/')[-1].replace('.pdf', '')
            
            # Build full URL
            full_url = urljoin(airport_url, href)
            
            # URL encode the PDF filename (spaces and special characters)
            url_parts = full_url.rsplit('/', 1)
            if len(url_parts) == 2:
                base_url, filename = url_parts
                encoded_filename = quote(filename, safe='')
                full_url = f"{base_url}/{encoded_filename}"
            
            # Categorize the chart
            chart_type = categorize_chart(chart_name)
            
            charts.append({
                'name': chart_name,
                'url': full_url,
                'type': chart_type
            })
        
        if not charts:
            print(f"No digital charts found for {icao_code} in Iceland eAIP.")
            print(f"Charts may be available in paper form or through other sources.")
        
        return charts
        
    except Exception as e:
        print(f"Error scraping {icao_code}: {e}")
        import traceback
        traceback.print_exc()
        return charts


def main():
    if len(sys.argv) < 2:
        print("Usage: python iceland_scraper.py <ICAO_CODE>")
        print("Example: python iceland_scraper.py BIRK")
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
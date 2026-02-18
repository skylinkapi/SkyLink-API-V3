#!/usr/bin/env python3
"""
Belarus eAIP Scraper
Scrapes aerodrome charts from Belarus AIP following Eurocontrol structure
"""

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote
import re
import sys


BASE_URL = "https://www.ban.by"


def get_latest_eaip_url():
    """Get the URL of the latest Belarus eAIP"""
    try:
        response = requests.get(f"{BASE_URL}/en/aeronautical-information-aip/amdt", timeout=30)
        soup = BeautifulSoup(response.text, 'lxml')
        
        # Find all eAIP links and get the latest one
        eaip_links = []
        for link in soup.find_all('a', href=True):
            href = link['href']
            if '/AIP/Belarus' in href and 'html/index.html' in href:
                # Extract date from href like /AIP/Belarus260122/html/index.html
                match = re.search(r'/AIP/Belarus(\d{6})/html/index.html', href)
                if match:
                    date_str = match.group(1)
                    eaip_links.append((date_str, href))
        
        if not eaip_links:
            return None
        
        # Sort by date and get the latest
        eaip_links.sort(reverse=True)
        latest_url = eaip_links[0][1]
        
        # Convert to full URL and get the eAIP directory
        if not latest_url.startswith('http'):
            latest_url = urljoin(BASE_URL, latest_url)
        
        # Get the base directory (remove index.html)
        base_dir = latest_url.replace('html/index.html', 'html/eAIP/')
        
        return base_dir
        
    except Exception as e:
        print(f"Error getting latest eAIP URL: {e}")
        return None


def get_airport_page_url(icao_code):
    """Get the URL for a specific airport's AD 2 page"""
    base_eaip = get_latest_eaip_url()
    if not base_eaip:
        return None
    
    # Format: UM-AD-2.ICAO-en-GB.html
    airport_page = f"UM-AD-2.{icao_code}-en-GB.html"
    return urljoin(base_eaip, airport_page)


def categorize_chart(chart_name):
    """Categorize chart based on its name"""
    chart_name_upper = chart_name.upper()
    
    if 'SID' in chart_name_upper or 'STANDARD DEPARTURE' in chart_name_upper:
        return 'SID'
    elif 'STAR' in chart_name_upper or 'STANDARD ARRIVAL' in chart_name_upper:
        return 'STAR'
    elif 'APPROACH' in chart_name_upper or 'ILS' in chart_name_upper or 'LOC' in chart_name_upper \
            or 'NDB' in chart_name_upper or 'RNP' in chart_name_upper or 'GLS' in chart_name_upper:
        return 'Approach'
    elif 'AERODROME CHART' in chart_name_upper or 'GROUND MOVEMENT' in chart_name_upper \
            or 'PARKING' in chart_name_upper or 'VISUAL APPROACH' in chart_name_upper:
        return 'Airport Diagram'
    else:
        return 'General'


def get_aerodrome_charts(icao_code):
    """
    Get all aerodrome charts for a given ICAO code from Belarus eAIP
    
    Args:
        icao_code: 4-letter ICAO code (e.g., 'UMMS')
        
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
        
        # Find AD 2.24 section (charts section)
        # Look for all PDF links in the page
        for link in soup.find_all('a', href=True):
            href = link['href']
            
            # Only process PDF links
            if '.pdf' not in href.lower():
                continue
            
            # Get the chart name from the row
            td_parent = link.find_parent('td')
            if not td_parent:
                continue
            
            tr_parent = td_parent.find_parent('tr')
            if not tr_parent:
                continue
            
            # Find the previous sibling row which contains the chart name
            prev_row = tr_parent.find_previous_sibling('tr')
            if prev_row:
                name_td = prev_row.find('td')
                if name_td:
                    chart_name = name_td.get_text(strip=True)
                    
                    # Build full URL
                    # href is like ../../graphics/eAIP/UMMS AD 2.24.1.pdf
                    # We need to resolve this relative to the current page
                    full_url = urljoin(airport_url, href)
                    
                    # URL encode the PDF filename (spaces and special characters)
                    # Split URL into base and filename, encode filename only
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
        
        return charts
        
    except Exception as e:
        print(f"Error scraping {icao_code}: {e}")
        import traceback
        traceback.print_exc()
        return charts


def main():
    if len(sys.argv) < 2:
        print("Usage: python belarus_scraper.py <ICAO_CODE>")
        print("Example: python belarus_scraper.py UMMS")
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

#!/usr/bin/env python3
"""
Portugal eAIP Scraper
Scrapes aerodrome charts from Portugal AIP following Eurocontrol structure
"""

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote
import re
import sys


BASE_URL = "https://ais.nav.pt/wp-content/uploads/AIS_Files/eAIP_Current/eAIP_Online/eAIP/html/eAIP/"


def get_airport_page_url(icao_code):
    """Get the URL for a specific airport's AD 2 page"""
    # Portugal eAIP structure: LP-AD-2.{ICAO}-en-PT.html
    airport_page = f"LP-AD-2.{icao_code}-en-PT.html"
    return urljoin(BASE_URL, airport_page)


def categorize_chart(chart_name):
    """Categorize chart based on its name"""
    chart_name_upper = chart_name.upper()
    
    if 'SID' in chart_name_upper or 'STANDARD DEPARTURE' in chart_name_upper or 'STANDARD INSTRUMENT DEPARTURE' in chart_name_upper:
        return 'SID'
    elif 'STAR' in chart_name_upper or 'STANDARD ARRIVAL' in chart_name_upper or 'STANDARD INSTRUMENT ARRIVAL' in chart_name_upper:
        return 'STAR'
    elif 'APPROACH' in chart_name_upper or 'ILS' in chart_name_upper or 'LOC' in chart_name_upper \
            or 'NDB' in chart_name_upper or 'RNP' in chart_name_upper or 'GLS' in chart_name_upper \
            or 'VOR' in chart_name_upper or 'RNAV' in chart_name_upper or 'DME' in chart_name_upper:
        return 'Approach'
    elif 'AERODROME CHART' in chart_name_upper or 'GROUND MOVEMENT' in chart_name_upper \
            or 'PARKING' in chart_name_upper or 'VISUAL APPROACH' in chart_name_upper \
            or 'AIRCRAFT PARKING' in chart_name_upper or 'DOCKING' in chart_name_upper:
        return 'Airport Diagram'
    else:
        return 'General'


def get_aerodrome_charts(icao_code):
    """
    Get all aerodrome charts for a given ICAO code from Portugal eAIP
    
    Args:
        icao_code: 4-letter ICAO code (e.g., 'LPPT', 'LPPR')
        
    Returns:
        List of dictionaries with 'name', 'url', and 'type' keys
    """
    charts = []
    
    try:
        # Get airport page URL
        airport_url = get_airport_page_url(icao_code)
        
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
            chart_name = None
            
            if prev_row:
                name_td = prev_row.find('td')
                if name_td:
                    chart_name = name_td.get_text(strip=True)
            
            # If we didn't find a name in the previous row, try the current row
            if not chart_name:
                # Look for text in the same row
                tds = tr_parent.find_all('td')
                for td in tds:
                    text = td.get_text(strip=True)
                    if text and text != href and not text.startswith('http'):
                        chart_name = text
                        break
            
            # If still no name, use the PDF filename
            if not chart_name:
                chart_name = href.split('/')[-1].replace('.pdf', '')
            
            # Build full URL
            # href might be like ../../graphics/eAIP/LPPT AD 2.24.1.pdf
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
        print(f"Error fetching charts: {e}")
        import traceback
        traceback.print_exc()
        return charts


if __name__ == '__main__':
    # Test with Lisbon (LPPT)
    if len(sys.argv) > 1:
        icao = sys.argv[1].upper()
    else:
        icao = 'LPPT'
    
    print(f"Testing Portugal scraper with {icao}...")
    charts = get_aerodrome_charts(icao)
    
    if charts:
        print(f"\nFound {len(charts)} charts:")
        for chart in charts:
            print(f"  [{chart['type']}] {chart['name']}")
            print(f"      {chart['url']}")
    else:
        print("No charts found")

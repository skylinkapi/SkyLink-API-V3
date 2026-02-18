#!/usr/bin/env python3
"""
Spain ENAIRE Scraper
Scrapes aerodrome charts from Spain's ENAIRE AIP
"""

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote
import re
import sys


BASE_URL = "https://aip.enaire.es/aip/"


def get_airport_page_url(icao_code):
    """Get the URL for a specific airport's page"""
    # Spain uses fragment-based navigation: aip-en.html#{ICAO}
    return f"{BASE_URL}aip-en.html#{icao_code}"


def categorize_chart(chart_name):
    """Categorize chart based on its name"""
    chart_name_upper = chart_name.upper()
    
    if 'SID' in chart_name_upper or 'STANDARD DEPARTURE' in chart_name_upper or 'STANDARD INSTRUMENT DEPARTURE' in chart_name_upper or 'SALIDA' in chart_name_upper:
        return 'SID'
    elif 'STAR' in chart_name_upper or 'STANDARD ARRIVAL' in chart_name_upper or 'STANDARD INSTRUMENT ARRIVAL' in chart_name_upper or 'LLEGADA' in chart_name_upper:
        return 'STAR'
    elif 'APPROACH' in chart_name_upper or 'ILS' in chart_name_upper or 'LOC' in chart_name_upper \
            or 'NDB' in chart_name_upper or 'RNP' in chart_name_upper or 'GLS' in chart_name_upper \
            or 'VOR' in chart_name_upper or 'RNAV' in chart_name_upper or 'DME' in chart_name_upper \
            or 'APROXIMACIÓN' in chart_name_upper or 'APROXIMACION' in chart_name_upper \
            or 'IAC' in chart_name_upper:
        return 'Approach'
    elif 'AERODROME CHART' in chart_name_upper or 'GROUND MOVEMENT' in chart_name_upper \
            or 'PARKING' in chart_name_upper or 'AIRCRAFT PARKING' in chart_name_upper \
            or 'DOCKING' in chart_name_upper or 'PLANO' in chart_name_upper:
        return 'Airport Diagram'
    else:
        return 'General'


def get_aerodrome_charts(icao_code):
    """
    Get all aerodrome charts for a given ICAO code from Spain ENAIRE AIP
    
    Args:
        icao_code: 4-letter ICAO code (e.g., 'LEMD', 'LEBL')
        
    Returns:
        List of dictionaries with 'name', 'url', and 'type' keys
    """
    charts = []
    
    try:
        # Get airport page URL
        airport_url = get_airport_page_url(icao_code)
        
        # Get the airport page
        # Note: This page uses JavaScript/fragments, but we can still try to parse it
        response = requests.get(airport_url, timeout=30)
        if response.status_code != 200:
            print(f"Error: Got status code {response.status_code}")
            return charts
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find all links with class "far fa-file-pdf"
        # These are the PDF chart links
        pdf_links = soup.find_all('i', class_='far fa-file-pdf')
        
        seen_urls = set()
        
        for pdf_icon in pdf_links:
            # The PDF icon is inside an <a> tag
            link = pdf_icon.find_parent('a')
            if not link or not link.get('href'):
                continue
            
            href = link.get('href')
            
            # Filter by ICAO code - only include charts that belong to this airport
            # Chart URLs are like: contenido_AIP/AD/AD2/LEMD/LE_AD_2_LEMD_...pdf
            if icao_code not in href:
                continue
            
            # Get the chart name
            # Try to find the name in the link text or nearby elements
            chart_name = link.get_text(strip=True)
            
            # If the link itself doesn't have text, look for nearby text
            if not chart_name or chart_name == '':
                # Look for text in parent elements
                parent = link.find_parent(['li', 'div', 'td', 'tr'])
                if parent:
                    # Get all text but remove the icon classes
                    chart_name = parent.get_text(strip=True)
                    # Clean up icon text
                    chart_name = re.sub(r'\s+', ' ', chart_name)
            
            # If still no name, use the filename
            if not chart_name or chart_name == '':
                chart_name = href.split('/')[-1].replace('.pdf', '')
            
            # Skip if we've already seen this URL
            if href in seen_urls:
                continue
            
            seen_urls.add(href)
            
            # Build full URL
            full_url = urljoin(BASE_URL, href)
            
            # URL encode if needed
            if ' ' in full_url:
                url_parts = full_url.rsplit('/', 1)
                if len(url_parts) == 2:
                    base_url_part, filename = url_parts
                    encoded_filename = quote(filename, safe='')
                    full_url = f"{base_url_part}/{encoded_filename}"
            
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
    # Test with Madrid (LEMD)
    if len(sys.argv) > 1:
        icao = sys.argv[1].upper()
    else:
        icao = 'LEMD'
    
    print(f"Testing Spain scraper with {icao}...")
    charts = get_aerodrome_charts(icao)
    
    if charts:
        print(f"\nFound {len(charts)} charts:")
        for chart in charts:
            print(f"  [{chart['type']}] {chart['name']}")
            print(f"      {chart['url']}")
    else:
        print("No charts found")

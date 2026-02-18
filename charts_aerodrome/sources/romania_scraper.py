#!/usr/bin/env python3
"""
Romania eAIP Scraper
Scrapes aerodrome charts from Romania AIP following Eurocontrol structure
"""

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote
import re
import sys


BASE_URL = "https://aisro.ro/aip/"


def get_latest_aip_url():
    """Get the URL of the latest Romania AIP"""
    try:
        response = requests.get(f"{BASE_URL}aip.php", timeout=30)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find the "Click here to access AIP ROMANIA" link
        for link in soup.find_all('a', href=True):
            if 'Click here to access AIP ROMANIA' in link.get_text():
                href = link['href']
                # Returns something like "2026-01-01/index.html"
                aip_dir = href.split('/')[0]
                return f"{BASE_URL}{aip_dir}/html/en/"
        
        return None
        
    except Exception as e:
        print(f"Error getting latest AIP URL: {e}")
        return None


def get_ad_toc_content():
    """Get the AD table of contents with all airports and charts"""
    try:
        base_url = get_latest_aip_url()
        if not base_url:
            return None, None
        
        toc_url = urljoin(base_url, "aip_toc_ad.html")
        response = requests.get(toc_url, timeout=30)
        
        if response.status_code != 200:
            print(f"Error: Got status code {response.status_code}")
            return None, None
        
        return response.text, base_url
        
    except Exception as e:
        print(f"Error getting AD TOC: {e}")
        return None, None


def categorize_chart(chart_name):
    """Categorize chart based on its name"""
    chart_name_upper = chart_name.upper()
    
    if 'SID' in chart_name_upper or 'STANDARD DEPARTURE' in chart_name_upper or 'STANDARD INSTRUMENT DEPARTURE' in chart_name_upper:
        return 'SID'
    elif 'STAR' in chart_name_upper or 'STANDARD ARRIVAL' in chart_name_upper or 'STANDARD INSTRUMENT ARRIVAL' in chart_name_upper:
        return 'STAR'
    elif 'APPROACH' in chart_name_upper or 'ILS' in chart_name_upper or 'LOC' in chart_name_upper \
            or 'NDB' in chart_name_upper or 'RNP' in chart_name_upper or 'VOR' in chart_name_upper \
            or 'RNAV' in chart_name_upper:
        return 'Approach'
    elif 'AERODROME CHART' in chart_name_upper or 'GROUND MOVEMENT' in chart_name_upper \
            or 'PARKING' in chart_name_upper or 'DOCKING' in chart_name_upper \
            or 'VISUAL APPROACH' in chart_name_upper or 'AIRCRAFT PARKING' in chart_name_upper:
        return 'Airport Diagram'
    else:
        return 'General'


def get_aerodrome_charts(icao_code):
    """
    Get all aerodrome charts for a given ICAO code from Romania eAIP
    
    Args:
        icao_code: 4-letter ICAO code (e.g., 'LROP')
        
    Returns:
        List of dictionaries with 'name', 'url', and 'type' keys
    """
    charts = []
    
    try:
        # Get the AD TOC content
        toc_html, base_url = get_ad_toc_content()
        if not toc_html or not base_url:
            print(f"Could not get AD TOC content")
            return charts
        
        soup = BeautifulSoup(toc_html, 'html.parser')
        
        # Find all links with ICAO code and AD 2.24
        all_text = toc_html
        
        # Find the airport section by looking for the HTML comment marker
        # (e.g., "<!-- ################################ LRBS ################################ -->")
        comment_pattern = rf'<!-- #+\s*{icao_code}\s+#+ -->'
        comment_match = re.search(comment_pattern, all_text, re.IGNORECASE)
        
        if not comment_match:
            print(f"Could not find airport section for {icao_code}")
            return charts
        
        # Find where this airport's section ends (next airport comment)
        search_start = comment_match.start()
        next_airport_pattern = r'<!-- ################################ [A-Z]{4} ################################ -->'
        next_airport_match = re.search(next_airport_pattern, all_text[search_start+100:])
        
        if next_airport_match:
            search_end = search_start + 100 + next_airport_match.start()
        else:
            search_end = len(all_text)
        
        # Now search for AD 2.24 within this airport's section only
        airport_section = all_text[search_start:search_end]
        chart_pattern = rf'AD 2\.24</span>.*?{icao_code}.*?Charts? related'
        chart_match = re.search(chart_pattern, airport_section, re.IGNORECASE | re.DOTALL)
        
        if not chart_match:
            print(f"Could not find AD 2.24 section for {icao_code}")
            return charts
        
        # Get the position where charts start (relative to all_text)
        start_pos = search_start + chart_match.end()
        
        # Extract the section after AD 2.24 until the next major section
        # Find the next airport or end of AD 2 section
        next_section_pattern = r'<div class="H3">.*?AD 2\.\d+.*?</div>'
        next_match = re.search(next_section_pattern, all_text[start_pos:], re.DOTALL)
        
        if next_match:
            end_pos = start_pos + next_match.start()
            section_html = all_text[start_pos:end_pos]
        else:
            # Take a reasonable chunk (next 50000 chars)
            section_html = all_text[start_pos:start_pos + 50000]
        
        # Parse the section to find all PDF links
        section_soup = BeautifulSoup(section_html, 'html.parser')
        
        for link in section_soup.find_all('a', href=True):
            href = link['href']
            if href.endswith('.pdf'):
                chart_name = link.get_text(strip=True)
                
                # Build full URL
                full_url = urljoin(base_url, href)
                
                # URL encode the PDF filename
                url_parts = full_url.rsplit('/', 1)
                if len(url_parts) == 2:
                    base_part, filename = url_parts
                    encoded_filename = quote(filename, safe='')
                    full_url = f"{base_part}/{encoded_filename}"
                
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
        print("Usage: python romania_scraper.py <ICAO_CODE>")
        print("Example: python romania_scraper.py LROP")
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

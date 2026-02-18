#!/usr/bin/env python3
"""
Latvia eAIP Scraper
Scrapes aerodrome charts from Latvia AIP (LGS)

Base URL: https://ais.lgs.lv/aiseaip
ICAO prefix: EV* (EVRA - Riga, EVLA - Liepāja)

Structure:
1. Main page has link to current AIRAC: eAIPfiles/2026_001_22-JAN-2026/data/2026-01-22/html/index.html
2. Airport pages: EV-AD-2.{ICAO}-en-GB.html
3. Charts in table id="chartTable"
4. PDF links are absolute URLs
"""

import re
import requests
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
from urllib.parse import urljoin, quote
import sys
import warnings

# Suppress XML parsed as HTML warning
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

BASE_URL = "https://ais.lgs.lv/"
MAIN_PAGE = "https://ais.lgs.lv/aiseaip"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
}


def get_latest_airac_info():
    """
    Get the latest AIRAC folder info from main page.
    
    Returns:
        tuple: (airac_folder, date_folder) e.g., ('2026_001_22-JAN-2026', '2026-01-22')
    """
    try:
        response = requests.get(MAIN_PAGE, headers=HEADERS, timeout=30)
        response.raise_for_status()
        
        # Find AIRAC link: eAIPfiles/2026_001_22-JAN-2026/data/2026-01-22/html/index.html
        match = re.search(
            r'href="eAIPfiles/(\d{4}_\d{3}_\d{2}-[A-Z]{3}-\d{4})/data/(\d{4}-\d{2}-\d{2})/html/index\.html',
            response.text
        )
        
        if match:
            airac_folder = match.group(1)
            date_folder = match.group(2)
            return airac_folder, date_folder
        
        return None, None
        
    except Exception as e:
        print(f"Error getting AIRAC info: {e}")
        return None, None


def get_airport_page_url(icao_code, airac_folder, date_folder):
    """Construct URL for airport page."""
    # Pattern: EV-AD-2.{ICAO}-en-GB.html
    return f"{BASE_URL}eAIPfiles/{airac_folder}/data/{date_folder}/html/eAIP/EV-AD-2.{icao_code}-en-GB.html"


def categorize_chart(chart_name):
    """Categorize chart based on its name."""
    name_upper = chart_name.upper()
    
    if any(kw in name_upper for kw in ['SID', 'DEPARTURE CHART', 'STANDARD DEPARTURE']):
        return 'SID'
    if any(kw in name_upper for kw in ['STAR', 'ARRIVAL CHART', 'STANDARD ARRIVAL']):
        return 'STAR'
    if any(kw in name_upper for kw in ['INSTRUMENT APPROACH', 'ILS', 'VOR', 'RNP', 'RNAV', 'LOC', 'NDB', 'DME', 'IAC']):
        return 'Approach'
    if any(kw in name_upper for kw in ['VISUAL APPROACH']):
        return 'Approach'
    if any(kw in name_upper for kw in ['AERODROME CHART', 'PARKING', 'DOCKING', 'GROUND MOVEMENT', 'TAXI', 'ADC']):
        return 'Airport Diagram'
    
    return 'General'


def get_aerodrome_charts(icao_code):
    """
    Fetch aerodrome charts for a given ICAO code from Latvia eAIP.
    
    Args:
        icao_code: 4-letter ICAO code (e.g., 'EVRA')
        
    Returns:
        list: List of dicts with 'name', 'url', and 'type' keys
    """
    charts = []
    icao_code = icao_code.upper()
    
    try:
        # Get AIRAC info
        airac_folder, date_folder = get_latest_airac_info()
        
        if not airac_folder:
            print("Could not determine current AIRAC")
            return charts
        
        print(f"Using AIRAC: {airac_folder}")
        
        # Fetch airport page
        airport_url = get_airport_page_url(icao_code, airac_folder, date_folder)
        print(f"Fetching: {airport_url}")
        
        response = requests.get(airport_url, headers=HEADERS, timeout=30)
        
        if response.status_code == 404:
            print(f"Airport {icao_code} not found in Latvia eAIP")
            return charts
        
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'lxml')
        
        # Find chart table (id="chartTable")
        chart_table = soup.find('table', id='chartTable')
        
        if not chart_table:
            # Fallback: find any table with PDF links
            for table in soup.find_all('table'):
                if table.find('a', href=lambda h: h and '.pdf' in h.lower()):
                    chart_table = table
                    break
        
        if not chart_table:
            print(f"No charts table found for {icao_code}")
            return charts
        
        seen_urls = set()
        
        # Process each row in the chart table
        for row in chart_table.find_all('tr', {'data-id': re.compile(r'chartRow\d+')}):
            # Get chart title from div[data-id="chartTitleN"]
            title_div = row.find('div', {'data-id': re.compile(r'chartTitle\d+')})
            if not title_div:
                continue
            
            chart_title = title_div.get_text(strip=True)
            # Remove leading number like "1. " or "13. "
            chart_title = re.sub(r'^\d+\.\s*', '', chart_title)
            
            # Skip NIL entries
            if 'NIL' in chart_title.upper():
                continue
            
            # Find all PDF links in this row
            pdf_links = row.find_all('a', href=lambda h: h and '.pdf' in h.lower())
            
            for pdf_link in pdf_links:
                href = pdf_link.get('href', '')
                
                # Build full URL if relative
                if href.startswith('http'):
                    chart_url = href
                else:
                    chart_url = urljoin(airport_url, href)
                
                if chart_url in seen_urls:
                    continue
                seen_urls.add(chart_url)
                
                # Get chart name from link text or title
                link_text = pdf_link.get_text(strip=True)
                
                # If multiple PDFs under same title, append link text to distinguish
                if len(pdf_links) > 1 and link_text:
                    # Extract meaningful part from filename like "RWY06" from "1590_EVLA_2_24_9_RWY06_A_20250710"
                    rwy_match = re.search(r'RWY\d+', link_text)
                    type_match = re.search(r'(ILS|VOR|RNP|LOC|NDB)_?[YZ]?', link_text)
                    
                    suffix_parts = []
                    if rwy_match:
                        suffix_parts.append(rwy_match.group())
                    if type_match:
                        suffix_parts.append(type_match.group().replace('_', ' '))
                    
                    if suffix_parts:
                        chart_name = f"{chart_title} - {' '.join(suffix_parts)}"
                    else:
                        chart_name = f"{chart_title} - {link_text}"
                else:
                    chart_name = chart_title
                
                charts.append({
                    'name': chart_name,
                    'url': chart_url,
                    'type': categorize_chart(chart_name)
                })
        
        return charts
        
    except Exception as e:
        print(f"Error scraping {icao_code}: {e}")
        import traceback
        traceback.print_exc()
        return charts


def main():
    if len(sys.argv) < 2:
        print("Usage: python latvia_scraper.py <ICAO>")
        print("Example: python latvia_scraper.py EVRA")
        sys.exit(1)
    
    icao = sys.argv[1].upper()
    print(f"Fetching charts for {icao}...")
    
    charts = get_aerodrome_charts(icao)
    
    if charts:
        print(f"\nFound {len(charts)} charts:")
        for c in charts:
            print(f"  [{c['type']}] {c['name']}")
            print(f"    {c['url']}")
    else:
        print("No charts found")


if __name__ == "__main__":
    main()

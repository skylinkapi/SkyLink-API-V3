#!/usr/bin/env python3
"""
Finland eAIP Scraper
Scrapes aerodrome charts from Finland AIP (ANS Finland)

Base URL: https://www.ais.fi/eaip/
ICAO prefix: EF* (EFHK - Helsinki-Vantaa, EFOU - Oulu, EFTP - Tampere-Pirkkala)

Structure:
1. Main page has table with effective issues - find one with green background (#ADFF2F)
2. AIRAC folder format: 001-2026_2026_01_22
3. Airport pages: {airac}/documents/eAIP/EF-AD-2.{ICAO}-en-GB.html
4. Charts in table with class containing "CHARTS_TABLE"
5. PDF links are absolute URLs
"""

import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote
import sys


BASE_URL = "https://www.ais.fi/eaip/"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
}


def get_current_airac_folder():
    """
    Get the current effective AIRAC folder from main page.
    Look for td with green background (background-color:#ADFF2F)
    
    Returns:
        str: AIRAC folder like '001-2026_2026_01_22'
    """
    try:
        response = requests.get(BASE_URL, headers=HEADERS, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find td with green background - indicates current effective issue
        # Style contains: background-color:#ADFF2F
        for td in soup.find_all('td'):
            style = td.get('style', '')
            if '#ADFF2F' in style.upper() or '#adff2f' in style.lower():
                # Find the link in this row or nearby
                parent_tr = td.find_parent('tr')
                if parent_tr:
                    link = parent_tr.find('a', href=True)
                    if link:
                        href = link['href']
                        # Extract folder from href like "001-2026_2026_01_22/..."
                        match = re.search(r'(\d{3}-\d{4}_\d{4}_\d{2}_\d{2})', href)
                        if match:
                            return match.group(1)
        
        # Fallback: find any AIRAC folder link
        for link in soup.find_all('a', href=True):
            href = link['href']
            match = re.search(r'(\d{3}-\d{4}_\d{4}_\d{2}_\d{2})', href)
            if match:
                return match.group(1)
        
        return None
        
    except Exception as e:
        print(f"Error getting AIRAC folder: {e}")
        return None


def get_airport_page_urls(icao_code, airac_folder):
    """
    Get all page URLs for an airport by scanning the menu.
    Finland splits airport info across multiple pages (1, 2, 3... 15, etc.)
    
    Returns:
        list: List of page URLs containing charts
    """
    menu_url = f"{BASE_URL}{airac_folder}/eAIP/menu.html"
    
    try:
        response = requests.get(menu_url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        
        # Find all English page links for this airport
        # Pattern: EF-AD 2 EFHK - HELSINKI-VANTAA 4-en-GB.html
        pattern = rf'href=[\'"]([^\'"]*{icao_code}[^\'"]*-en-GB\.html)'
        matches = re.findall(pattern, response.text)
        
        # Get unique URLs
        unique_pages = list(set(matches))
        
        # Build full URLs with proper encoding
        page_urls = []
        for page in unique_pages:
            # URL encode the page name (spaces become %20)
            encoded_page = quote(page, safe='/:')
            full_url = f"{BASE_URL}{airac_folder}/eAIP/{encoded_page}"
            page_urls.append(full_url)
        
        return page_urls
        
    except Exception as e:
        print(f"Error getting airport pages: {e}")
        return []


def categorize_chart(chart_name):
    """Categorize chart based on its name."""
    name_upper = chart_name.upper()
    
    # SID charts
    if any(kw in name_upper for kw in ['SID', 'SIDR', 'OMNIDIRECTIONAL DEPARTURE']):
        return 'SID'
    
    # STAR charts
    if 'STAR' in name_upper:
        return 'STAR'
    
    # Approach charts
    if any(kw in name_upper for kw in ['ILS', 'LOC', 'VOR', 'RNP', 'NDB', 'RNAV', 'GLS', 'COPTER ILS']):
        return 'Approach'
    
    # Visual approach
    if any(kw in name_upper for kw in ['VAC', 'VISUAL', 'VFR']):
        return 'Approach'
    
    # Airport diagrams
    if any(kw in name_upper for kw in ['ADC', 'APDC', 'AGMC', 'PARKING', 'DOCKING', 'MARK', 'TAXIWAY']):
        return 'Airport Diagram'
    
    # General charts
    if any(kw in name_upper for kw in ['AOC', 'PATC', 'ATC SMAC', 'OBSTACLE', 'TERRAIN', 'ARC', 'WPT', 'WAYPOINT', 'FAS DATA', 'FASDB']):
        return 'General'
    
    return 'General'


def get_aerodrome_charts(icao_code):
    """
    Fetch aerodrome charts for a given ICAO code from Finland eAIP.
    
    Args:
        icao_code: 4-letter ICAO code (e.g., 'EFHK')
        
    Returns:
        list: List of dicts with 'name', 'url', and 'type' keys
    """
    charts = []
    icao_code = icao_code.upper()
    
    try:
        # Get current AIRAC folder
        airac_folder = get_current_airac_folder()
        
        if not airac_folder:
            print("Could not determine current AIRAC folder")
            return charts
        
        print(f"Using AIRAC: {airac_folder}")
        
        # Get all airport page URLs
        page_urls = get_airport_page_urls(icao_code, airac_folder)
        
        if not page_urls:
            print(f"Airport {icao_code} not found in Finland eAIP")
            return charts
        
        print(f"Found {len(page_urls)} pages for {icao_code}")
        
        seen_urls = set()
        
        # Scrape each page for charts
        for page_url in page_urls:
            try:
                response = requests.get(page_url, headers=HEADERS, timeout=30)
                
                if response.status_code != 200:
                    continue
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Find chart tables - they have class containing "CHARTS_TABLE"
                chart_tables = soup.find_all('table', class_=lambda c: c and 'CHARTS_TABLE' in c)
                
                if not chart_tables:
                    # Fallback: find tables with PDF links
                    chart_tables = [t for t in soup.find_all('table') if t.find('a', href=lambda h: h and '.pdf' in h.lower())]
                
                for table in chart_tables:
                    # Process each row (skip header)
                    for row in table.find_all('tr'):
                        # Skip header rows
                        if row.find('th'):
                            continue
                        
                        cells = row.find_all('td')
                        if len(cells) < 2:
                            continue
                        
                        # First cell contains chart name (nested in spans)
                        name_cell = cells[0]
                        chart_name = name_cell.get_text(strip=True)
                        
                        if not chart_name:
                            continue
                        
                        # Second cell contains PDF link
                        link_cell = cells[1]
                        pdf_link = link_cell.find('a', href=lambda h: h and '.pdf' in h.lower())
                        
                        if not pdf_link:
                            continue
                        
                        href = pdf_link.get('href', '')
                        
                        # Build full URL if relative
                        if href.startswith('http'):
                            chart_url = href
                        else:
                            chart_url = urljoin(page_url, href)
                        
                        if chart_url in seen_urls:
                            continue
                        seen_urls.add(chart_url)
                        
                        charts.append({
                            'name': chart_name,
                            'url': chart_url,
                            'type': categorize_chart(chart_name)
                        })
            
            except Exception as e:
                print(f"Error scraping page {page_url}: {e}")
                continue
        
        return charts
        
    except Exception as e:
        print(f"Error scraping {icao_code}: {e}")
        import traceback
        traceback.print_exc()
        return charts


def main():
    if len(sys.argv) < 2:
        print("Usage: python finland_scraper.py <ICAO>")
        print("Example: python finland_scraper.py EFHK")
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

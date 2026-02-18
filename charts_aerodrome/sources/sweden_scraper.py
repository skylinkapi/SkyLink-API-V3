#!/usr/bin/env python3
"""
Sweden eAIP Scraper
Scrapes aerodrome charts from Swedish AIP (LFV)
https://aro.lfv.se/content/eaip/

ICAO prefix: ES* (ESSA, ESGG, ESSB, etc.)
"""

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote
import re
import sys


BASE_URL = "https://aro.lfv.se/content/eaip/"


def get_current_airac_folder():
    """
    Get the current effective AIRAC folder from the main page.
    Looks for the green highlighted (background-color:#ADFF2F) cell which marks current effective.
    """
    try:
        url = f"{BASE_URL}default_offline.html"
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'lxml')
        
        # Find the cell with green background (current effective issue)
        # Style contains "background-color:#ADFF2F"
        green_td = soup.find('td', style=lambda x: x and '#ADFF2F' in x)
        
        if green_td:
            link = green_td.find('a', href=True)
            if link:
                href = link['href']
                # Extract folder name: "AIRAC AIP AMDT 1-2026_2026_01_22\index-v2.html"
                # or similar pattern like "AIP AMDT 1-2025_2025_09_04\index-v2.html"
                match = re.match(r'([^\\]+)\\', href)
                if match:
                    return match.group(1)
                # Try forward slash
                match = re.match(r'([^/]+)/', href)
                if match:
                    return match.group(1)
        
        # Fallback: look for any AIRAC folder link pattern
        for link in soup.find_all('a', href=True):
            href = link['href']
            if ('AIRAC' in href or 'AIP AMDT' in href) and '_20' in href:
                match = re.match(r'([^\\\/]+)[\\\/]', href)
                if match:
                    return match.group(1)
        
        return None
        
    except Exception as e:
        print(f"Error getting AIRAC folder: {e}")
        return None


def get_airport_page_urls(icao_code, airac_folder):
    """
    Find all airport page URLs from the menu.
    Sweden uses pages like: "ES-AD 2 ESGG GÖTEBORG-LANDVETTER 1-en-GB.html"
    
    Returns list of page URLs (URL encoded).
    """
    menu_url = f"{BASE_URL}{quote(airac_folder, safe='')}/eAIP/menu.html"
    
    try:
        response = requests.get(menu_url, timeout=30)
        response.raise_for_status()
        
        # Force UTF-8 decoding (server incorrectly reports ISO-8859-1)
        text = response.content.decode('utf-8')
        
        # Find all pages matching the ICAO code
        # Pattern: ES-AD 2 {ICAO} {CITY} {N}-en-GB.html
        pattern = rf'ES-AD 2 {icao_code}[^\"\']+\.html'
        matches = re.findall(pattern, text)
        
        # Unique pages, prefer English (en-GB)
        pages = set()
        for match in matches:
            if 'en-GB' in match:
                pages.add(match)
        
        # If no English pages, use Swedish
        if not pages:
            pages = set(matches)
        
        # Sort by page number
        sorted_pages = sorted(pages)
        
        return sorted_pages
        
    except Exception as e:
        print(f"Error getting airport pages: {e}")
        return []


def get_airport_page_url(icao_code, airac_folder):
    """
    Construct the URL for an airport's eAIP page.
    This is a fallback - prefer using get_airport_page_urls.
    """
    # URL encode the AIRAC folder (it has spaces)
    encoded_folder = quote(airac_folder, safe='')
    
    # Airport page format - first page only
    # Need to find actual page name from menu
    return None


def categorize_chart(chart_name):
    """Categorize chart based on its name."""
    name_upper = chart_name.upper()
    
    # Ground movement / Airport diagrams - check first to avoid false positives
    if any(keyword in name_upper for keyword in ['AERODROME CHART', 'AD CHART', 'GROUND MOVEMENT', 
                                                   'PARKING', 'DOCKING', 'PD CHART']):
        return 'Airport Diagram'
    
    # SID charts
    if 'SID' in name_upper and 'STAR' not in name_upper:
        return 'SID'
    
    # STAR charts
    if 'STAR' in name_upper:
        return 'STAR'
    
    # Approach charts (IAC, ILS, LOC, RNP, RNAV, NDB, VOR)
    if any(keyword in name_upper for keyword in ['IAC', 'ILS', 'LOC', 'RNP', 'NDB', 'VOR', 'APPROACH']):
        # But not if it's just "RNAV AR GENERAL" info
        if 'GENERAL' not in name_upper or 'RNP' in name_upper or 'ILS' in name_upper:
            return 'Approach'
    
    # General / Other (AOC, PATC, SMAC, Area Chart, VAC)
    return 'General'


def get_aerodrome_charts(icao_code):
    """
    Get all aerodrome charts for a given ICAO code from Sweden eAIP.
    
    Args:
        icao_code: 4-letter ICAO code (e.g., 'ESGG', 'ESSA')
        
    Returns:
        List of dictionaries with 'name', 'url', and 'type' keys
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
        page_names = get_airport_page_urls(icao_code, airac_folder)
        
        if not page_names:
            print(f"Airport {icao_code} not found in Sweden eAIP")
            return charts
        
        print(f"Found {len(page_names)} pages for {icao_code}")
        
        seen_urls = set()
        base_eaip_url = f"{BASE_URL}{quote(airac_folder, safe='')}/eAIP/"
        
        # Scan each page for charts
        for page_name in page_names:
            page_url = base_eaip_url + quote(page_name, safe='')
            
            try:
                response = requests.get(page_url, timeout=30)
                if response.status_code != 200:
                    continue
                
                soup = BeautifulSoup(response.text, 'lxml')
                
                # Find charts table - class contains "CHARTS_TABLE"
                charts_tables = soup.find_all('table', class_=lambda x: x and 'CHARTS_TABLE' in x)
                
                for table in charts_tables:
                    # Find all rows in the table
                    rows = table.find_all('tr')
                    
                    for row in rows:
                        # Skip header rows
                        if row.find('th'):
                            continue
                        
                        # Get all tds
                        tds = row.find_all('td')
                        if len(tds) < 2:
                            continue
                        
                        # Skip deleted charts (class="deletedAIRAC")
                        if 'deletedAIRAC' in tds[0].get('class', []):
                            continue
                        
                        # Get chart name from first td
                        chart_name = ''
                        for span in tds[0].find_all('span'):
                            text = span.get_text(strip=True)
                            if text and text not in ['Charts', 'Pages']:
                                chart_name = text
                                break
                        
                        if not chart_name:
                            chart_name = tds[0].get_text(strip=True)
                        
                        if not chart_name:
                            continue
                        
                        # Get PDF link from second td
                        link = row.find('a', class_='ulink')
                        if not link:
                            link = row.find('a', href=lambda x: x and '.pdf' in x.lower())
                        
                        if not link:
                            continue
                        
                        href = link.get('href', '')
                        if not href or '.pdf' not in href.lower():
                            continue
                        
                        # Skip if already seen
                        if href in seen_urls:
                            continue
                        seen_urls.add(href)
                        
                        # URL may be relative, convert to absolute
                        if href.startswith('../'):
                            # Relative to eAIP folder, so go up one level
                            chart_url = f"{BASE_URL}{quote(airac_folder, safe='')}/{href[3:]}"
                        elif href.startswith('http'):
                            chart_url = href
                        else:
                            chart_url = urljoin(page_url, href)
                        
                        # Categorize
                        chart_type = categorize_chart(chart_name)
                        
                        charts.append({
                            'name': chart_name,
                            'url': chart_url,
                            'type': chart_type
                        })
            
            except Exception as e:
                print(f"Error processing page {page_name}: {e}")
                continue
        
        return charts
        
    except requests.exceptions.HTTPError as e:
        print(f"HTTP error fetching charts for {icao_code}: {e}")
        return charts
    except Exception as e:
        print(f"Error scraping {icao_code}: {e}")
        import traceback
        traceback.print_exc()
        return charts


def main():
    if len(sys.argv) < 2:
        print("Usage: python sweden_scraper.py <ICAO_CODE>")
        print("Example: python sweden_scraper.py ESGG")
        sys.exit(1)
    
    icao_code = sys.argv[1].upper()
    
    print(f"Fetching charts for {icao_code}...")
    charts = get_aerodrome_charts(icao_code)
    
    if charts:
        print(f"\nFound {len(charts)} charts:")
        
        # Group by type
        by_type = {}
        for chart in charts:
            t = chart['type']
            if t not in by_type:
                by_type[t] = []
            by_type[t].append(chart)
        
        for chart_type in ['Airport Diagram', 'General', 'SID', 'STAR', 'Approach']:
            if chart_type in by_type:
                print(f"\n  {chart_type}:")
                for chart in by_type[chart_type]:
                    print(f"    - {chart['name']}")
                    print(f"      {chart['url']}")
    else:
        print("No charts found")


if __name__ == "__main__":
    main()

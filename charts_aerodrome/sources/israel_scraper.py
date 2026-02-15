"""
Israel eAIP Scraper
Scrapes aerodrome charts from Israel Aviation Authority eAIP

Website: https://e-aip.azurefd.net/
Uses Eurocontrol-style eAIP structure.

ICAO prefix: LL*

Airports:
- LLBG - Ben Gurion International Airport (Tel Aviv)
- LLER - Ramon International Airport (Eilat)
- LLHA - Haifa Airport
"""

import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from typing import List, Dict, Optional


BASE_URL = "https://e-aip.azurefd.net/"


def get_current_airac() -> Optional[str]:
    """
    Get the current AIRAC folder from the front page.
    
    Returns:
        AIRAC folder name (e.g., '2025-10-02-AIRAC') or None
    """
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(BASE_URL, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find the AIRAC link
        for link in soup.find_all('a', href=True):
            href = link['href']
            if 'AIRAC' in href:
                # Extract folder name (e.g., "2025-10-02-AIRAC")
                folder = href.split('/')[0]
                return folder
        
        return None
        
    except Exception as e:
        print(f"Error getting current AIRAC: {e}")
        return None


def categorize_chart(chart_name: str) -> str:
    """Categorize chart based on filename."""
    name_upper = chart_name.upper()
    
    # SID charts
    if 'SID' in name_upper or 'DEP' in name_upper:
        return 'SID'
    
    # STAR charts
    if 'STAR' in name_upper or 'ARR' in name_upper:
        return 'STAR'
    
    # Approach charts
    if any(kw in name_upper for kw in ['IAC', 'ILS', 'VOR', 'RNP', 'RNAV', 'LOC', 'NDB', 'RNV', 'APCH']):
        return 'Approach'
    
    # Airport diagrams / Ground charts
    if any(kw in name_upper for kw in ['ADC', 'APDC', 'TAXI', 'PARKING', 'GMC', 'GROUND']):
        return 'Airport Diagram'
    
    # Obstacle charts
    if 'AOC' in name_upper or 'OBS' in name_upper:
        return 'General'
    
    # General
    return 'General'


def get_chart_name(pdf_filename: str, icao: str) -> str:
    """Extract readable chart name from PDF filename."""
    # Remove path and extension
    name = pdf_filename.split('/')[-1].replace('.pdf', '')
    
    # Remove prefix like LL_AD_2_LLBG_
    prefix = f"LL_AD_2_{icao}_"
    if name.startswith(prefix):
        name = name[len(prefix):]
    
    # Clean up underscores and version markers
    name = name.replace('_en', '').replace('_V1', ' V1').replace('_V2', ' V2')
    name = name.replace('_', ' ').strip()
    
    # Remove trailing version numbers if already in name
    name = re.sub(r'\s+V\d+$', '', name)
    
    return name if name else pdf_filename


def get_aerodrome_charts(icao_code: str) -> List[Dict[str, str]]:
    """
    Fetch aerodrome charts for a given ICAO code from Israel eAIP.
    
    Args:
        icao_code: 4-letter ICAO code (e.g., 'LLBG')
        
    Returns:
        List of dictionaries with 'name', 'url', and 'type' keys
    """
    icao_code = icao_code.upper().strip()
    charts = []
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        
        # Get current AIRAC
        airac_folder = get_current_airac()
        if not airac_folder:
            print("Failed to get current AIRAC folder")
            return []
        
        # Construct base URLs
        # HTML pages are at {base}/{airac}/html/eAIP/
        # PDFs are at {base}/{airac}/graphics/eAIP/
        html_base_url = f"{BASE_URL}{airac_folder}/html/"
        pdf_base_url = f"{BASE_URL}{airac_folder}/"
        
        # Construct airport page URL
        airport_page_url = f"{html_base_url}eAIP/LL-AD-2.{icao_code}-en-GB.html"
        
        # Fetch the airport page
        response = requests.get(airport_page_url, headers=headers, timeout=30)
        
        if response.status_code == 404:
            print(f"Airport {icao_code} not found in Israel eAIP")
            return []
            
        response.raise_for_status()
        
        # Find all PDF links
        pdf_pattern = re.compile(r'href=["\']([^"\']*\.pdf)["\']', re.I)
        pdf_matches = pdf_pattern.findall(response.text)
        
        # Process unique PDFs
        seen_urls = set()
        
        for pdf_href in pdf_matches:
            # Construct full URL
            if pdf_href.startswith('../../'):
                # Relative path ../../ from html/eAIP/ goes to AIRAC root
                # Then into graphics/eAIP/
                relative_path = pdf_href.replace('../../', '')
                full_url = pdf_base_url + relative_path
            elif pdf_href.startswith('http'):
                full_url = pdf_href
            else:
                full_url = urljoin(airport_page_url, pdf_href)
            
            # Skip duplicates
            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)
            
            # Get chart name
            chart_name = get_chart_name(pdf_href, icao_code)
            
            charts.append({
                'name': chart_name,
                'url': full_url,
                'type': categorize_chart(chart_name)
            })
        
        return charts
        
    except Exception as e:
        print(f"Error fetching charts for {icao_code}: {e}")
        return []


# For testing
if __name__ == "__main__":
    import sys
    
    icao = sys.argv[1] if len(sys.argv) > 1 else "LLBG"
    print(f"Fetching charts for {icao}...")
    
    charts = get_aerodrome_charts(icao)
    
    if charts:
        print(f"\nFound {len(charts)} chart(s):")
        for chart in charts:
            print(f"  [{chart.get('type', 'N/A')}] {chart['name']}")
            print(f"    URL: {chart['url']}")
    else:
        print("No charts found.")

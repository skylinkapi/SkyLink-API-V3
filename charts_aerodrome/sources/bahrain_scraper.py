"""
Bahrain eAIP Scraper
Scrapes aerodrome charts from Bahrain Civil Aviation Affairs AIP

Website: https://aim.mtt.gov.bh/eaip
Uses Eurocontrol eAIP structure with date-based AIRAC folders.

ICAO prefix: OB*
Example: OBBI (Bahrain International Airport)

Structure:
- Main page lists Current Publications with latest AIRAC link
- Date folder format: "2025-09-04-AIRAC"
- Airport pages: html/eAIP/OB-AD-2.{ICAO}-en-BH.html
- Charts in AD 2.24 section
- PDFs in graphics/eAIP/ folder
"""

import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote
from typing import List, Dict


BASE_URL = "https://aim.mtt.gov.bh/eAIP/"
INDEX_URL = "https://aim.mtt.gov.bh/eaip"


def get_latest_airac_folder() -> str:
    """
    Fetch the latest AIRAC date folder from the main eAIP page.
    
    Returns:
        str: AIRAC folder name like "2025-09-04-AIRAC"
    """
    try:
        response = requests.get(INDEX_URL, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Look for "Current Publications" link containing AIRAC
        for link in soup.find_all('a', href=True):
            href = link['href']
            if 'AIRAC' in href and '/html/' in href:
                # Extract date folder: e.g., "2025-09-04-AIRAC" from URL
                match = re.search(r'(\d{4}-\d{2}-\d{2}-AIRAC)', href)
                if match:
                    return match.group(1)
        
        raise Exception("Could not find AIRAC folder in main page")
        
    except Exception as e:
        raise Exception(f"Failed to fetch latest AIRAC folder: {e}")


def get_airport_page_url(icao_code: str) -> str:
    """
    Construct the URL for an airport's eAIP page.
    
    Args:
        icao_code: 4-letter ICAO code (e.g., 'OBBI')
        
    Returns:
        Full URL to airport page
    """
    airac_folder = get_latest_airac_folder()
    
    # Airport pages are in eAIP subfolder with format OB-AD-2.{ICAO}-en-BH.html
    airport_page = f"html/eAIP/OB-AD-2.{icao_code}-en-BH.html"
    
    return urljoin(BASE_URL, f"{airac_folder}/{airport_page}")


def categorize_chart(chart_name: str) -> str:
    """
    Categorize a chart based on its name.
    
    Args:
        chart_name: Name of the chart
        
    Returns:
        Chart category (SID/STAR/Approach/Airport Diagram/General)
    """
    name_upper = chart_name.upper()
    
    # SID charts
    if any(keyword in name_upper for keyword in ['DEPARTURE', 'SID', 'DEP ']):
        return 'SID'
    
    # STAR charts
    if any(keyword in name_upper for keyword in ['ARRIVAL', 'STAR', 'ARR ']):
        return 'STAR'
    
    # Approach charts
    if any(keyword in name_upper for keyword in ['APPROACH', 'ILS', 'VOR', 'RNP', 'RNAV', 'LOC', 'NDB', 'DME', 'IAC', 'VISUAL APP']):
        return 'Approach'
    
    # Airport diagrams / Ground charts
    if any(keyword in name_upper for keyword in ['AERODROME CHART', 'AIRPORT CHART', 'PARKING', 'DOCKING', 
                                                   'GROUND MOVEMENT', 'TAXI', 'ADC', 'GMC', 'APRON']):
        return 'Airport Diagram'
    
    # General
    return 'General'


def get_aerodrome_charts(icao_code: str) -> List[Dict[str, str]]:
    """
    Fetch aerodrome charts for a given ICAO code from Bahrain eAIP.
    
    Args:
        icao_code: 4-letter ICAO code (e.g., 'OBBI')
        
    Returns:
        List of dictionaries with 'name', 'url', and 'type' keys
    """
    icao_code = icao_code.upper().strip()
    charts = []
    
    try:
        # Get the airport page URL
        airport_url = get_airport_page_url(icao_code)
        airac_folder = get_latest_airac_folder()
        base_pdf_url = f"{BASE_URL}{airac_folder}/"
        
        # Fetch the airport page
        response = requests.get(airport_url, timeout=30)
        
        if response.status_code == 404:
            print(f"Airport {icao_code} not found in Bahrain AIP")
            return []
            
        response.raise_for_status()
        html = response.text
        
        # Parse with BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')
        
        # Find the AD 2.24 section - charts are in tables
        # Look for h4 headers containing "AD 2.24" 
        ad_224_section = None
        for h4 in soup.find_all('h4'):
            if 'AD 2.24' in h4.get_text() or 'Charts related' in h4.get_text().lower():
                ad_224_section = h4
                break
        
        if not ad_224_section:
            # Try alternative: look for any section with "AD 2.24"
            ad_224_section = soup.find(string=re.compile(r'AD\s*2\.24', re.IGNORECASE))
        
        # Find all table rows in AD 2.24 section
        # Structure: <tr><td><p>CHART NAME</p></td><td><a href="...pdf">AD 2-OBBI-XX</a></td></tr>
        for link in soup.find_all('a', href=True):
            href = link['href']
            
            if '.pdf' in href.lower() and 'graphics' in href:
                # Get the full URL
                if href.startswith('http'):
                    full_url = href
                else:
                    full_url = urljoin(airport_url, href)
                
                # Get chart name from the first <td> in the same row
                chart_name = None
                parent_tr = link.find_parent('tr')
                
                if parent_tr:
                    # Find all td elements in this row
                    cells = parent_tr.find_all('td')
                    if cells:
                        # First cell contains the chart name in a <p> tag
                        first_cell = cells[0]
                        p_tag = first_cell.find('p')
                        if p_tag:
                            chart_name = p_tag.get_text(strip=True)
                        else:
                            chart_name = first_cell.get_text(strip=True)
                
                # Fallback: Extract from filename
                if not chart_name:
                    filename = href.split('/')[-1]
                    filename = filename.replace('.pdf', '').replace('.PDF', '')
                    chart_name = filename
                
                # Clean up chart name
                chart_name = re.sub(r'\s+', ' ', chart_name).strip()
                # Fix encoding issues (Â character from UTF-8)
                chart_name = chart_name.replace('Â', '').strip()
                
                # Skip if it's just a generic link or too short
                if chart_name and len(chart_name) > 3:
                    # Avoid duplicates
                    if not any(c['url'] == full_url for c in charts):
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
    
    icao = sys.argv[1] if len(sys.argv) > 1 else "OBBI"
    print(f"Fetching charts for {icao}...")
    
    charts = get_aerodrome_charts(icao)
    
    if charts:
        print(f"\nFound {len(charts)} chart(s):")
        for chart in charts:
            print(f"  [{chart.get('type', 'N/A')}] {chart['name']}")
            print(f"    URL: {chart['url']}")
    else:
        print("No charts found.")

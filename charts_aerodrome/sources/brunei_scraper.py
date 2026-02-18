"""
Brunei AIP Scraper
Scrapes aerodrome charts from Brunei Department of Civil Aviation

Website: https://www.dca.gov.bn/Site%20Pages/Information%20TAB/AIP%20Amendment/{ICAO}%20Aerodrome.aspx

ICAO prefix: WB*

Examples: WBSB (Brunei International Airport)
"""

import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, unquote
from typing import List, Dict


BASE_URL = "https://www.dca.gov.bn/"


def categorize_chart(chart_name: str) -> str:
    """Categorize chart based on name."""
    name_upper = chart_name.upper()
    
    if 'DEPARTURE' in name_upper or 'SID' in name_upper:
        return 'SID'
    elif 'ARRIVAL' in name_upper or 'STAR' in name_upper:
        return 'STAR'
    elif 'APPROACH' in name_upper or 'IAC' in name_upper or 'ILS' in name_upper or 'VOR' in name_upper or 'RNAV' in name_upper:
        return 'Approach'
    elif 'PARKING' in name_upper or 'DOCKING' in name_upper or 'GROUND' in name_upper or 'TAXI' in name_upper:
        return 'Airport Diagram'
    elif 'AERODROME CHART' in name_upper and 'OBSTACLE' not in name_upper:
        return 'Airport Diagram'
    else:
        return 'General'


def get_aerodrome_charts(icao_code: str) -> List[Dict[str, str]]:
    """
    Get aerodrome charts for a Brunei airport.
    
    Args:
        icao_code: ICAO airport code (e.g., 'WBSB')
        
    Returns:
        List of chart dictionaries with 'name', 'url', and 'type' keys
    """
    icao_code = icao_code.upper().strip()
    charts = []
    
    # Construct page URL
    page_url = f"https://www.dca.gov.bn/Site%20Pages/Information%20TAB/AIP%20Amendment/{icao_code}%20Aerodrome.aspx"
    
    try:
        response = requests.get(page_url, timeout=30, verify=False)
        
        if response.status_code == 404:
            print(f"Airport {icao_code} not found in Brunei AIP")
            return []
            
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find all PDF links related to aerodrome (either has ICAO in URL or is in an aerodrome context)
        for link in soup.find_all('a', href=True):
            href = link['href']
            
            # Skip non-PDF links
            if '.pdf' not in href.lower():
                continue
                
            # Check if this is an aerodrome-related PDF
            href_lower = href.lower()
            is_aerodrome_pdf = (
                icao_code.lower() in href_lower or
                'aerodrome' in href_lower or
                'ad 2' in href_lower or
                'ad%202' in href_lower or
                '/ad/' in href_lower or
                'approach' in href_lower or
                'obstacle' in href_lower or
                'parking' in href_lower
            )
            
            if is_aerodrome_pdf:
                # Get the full URL
                if href.startswith('/'):
                    full_url = urljoin(BASE_URL, href)
                elif href.startswith('http'):
                    full_url = href
                else:
                    full_url = urljoin(BASE_URL, '/' + href)
                
                # Get chart name from link text or extract from URL
                link_text = link.get_text(strip=True)
                
                # Try to get descriptive name from parent row
                chart_name = None
                parent_tr = link.find_parent('tr')
                if parent_tr:
                    cells = parent_tr.find_all('td')
                    if len(cells) >= 2:
                        # Second cell often has the description
                        desc_cell = cells[1] if len(cells) > 1 else cells[0]
                        desc_text = desc_cell.get_text(strip=True)
                        if desc_text and len(desc_text) > 3:
                            chart_name = desc_text
                
                # Fallback: extract from filename
                if not chart_name:
                    # Decode URL and extract filename
                    decoded_url = unquote(href)
                    filename = decoded_url.split('/')[-1]
                    filename = filename.replace('.pdf', '').replace('.PDF', '')
                    filename = filename.replace('%20', ' ').replace('-', ' - ')
                    chart_name = filename
                
                # Clean up chart name
                chart_name = re.sub(r'\s+', ' ', chart_name).strip()
                
                if chart_name and len(chart_name) > 3:
                    # Avoid duplicates
                    if not any(c['url'] == full_url for c in charts):
                        charts.append({
                            'name': chart_name,
                            'url': full_url,
                            'type': categorize_chart(chart_name)
                        })
        
        return charts
        
    except requests.RequestException as e:
        print(f"Error fetching charts for {icao_code}: {e}")
        return []


# Suppress SSL warnings
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# For testing
if __name__ == "__main__":
    import sys
    
    icao = sys.argv[1] if len(sys.argv) > 1 else "WBSB"
    print(f"Fetching charts for {icao}...")
    
    charts = get_aerodrome_charts(icao)
    
    if charts:
        print(f"\nFound {len(charts)} chart(s):")
        for chart in charts:
            print(f"  [{chart.get('type', 'N/A')}] {chart['name']}")
            print(f"    URL: {chart['url']}")
    else:
        print("No charts found.")

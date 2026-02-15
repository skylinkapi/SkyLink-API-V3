"""
Hong Kong eAIP Scraper
Scrapes aerodrome charts from Hong Kong Civil Aviation Department AIS

Website: https://www.ais.gov.hk/
Uses Eurocontrol-style eAIP structure.

ICAO prefix: VH*

Example: VHHH (Hong Kong International Airport)
"""

import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from typing import List, Dict


BASE_URL = "https://www.ais.gov.hk/"
AIS_JSON_URL = "https://www.ais.gov.hk/ais.json"


def get_current_eaip_base() -> tuple:
    """
    Fetch the current eAIP base URL from ais.json.
    
    Returns:
        Tuple of (html_base_url, pdf_base_url) for current eAIP
        e.g., ('https://www.ais.gov.hk/eaip_20260122/2026-01-22-000000/html/',
               'https://www.ais.gov.hk/eaip_20260122/2026-01-22-000000/pdf/')
    """
    from datetime import datetime
    import json
    
    try:
        response = requests.get(AIS_JSON_URL, timeout=30)
        response.raise_for_status()
        
        # Handle BOM in JSON
        content = response.content.decode('utf-8-sig')
        data = json.loads(content)
        
        # Find the current amendment (most recent where effDate <= today)
        today = datetime.now().strftime('%Y-%m-%d')
        current_amdt = None
        
        if 'amdt' in data and len(data['amdt']) > 0:
            for amdt in data['amdt']:
                if amdt['effDate'] <= today:
                    current_amdt = amdt
                    break
        
        if not current_amdt:
            raise Exception("No current amendment found in ais.json")
        
        eff_date = current_amdt['effDate']
        eff_date_nodash = eff_date.replace('-', '')
        
        # URL structure: eaip_{effDate_no_dashes}/{effDate}-000000/
        base_folder = f"eaip_{eff_date_nodash}/{eff_date}-000000/"
        html_base = urljoin(BASE_URL, base_folder + "html/")
        pdf_base = urljoin(BASE_URL, base_folder + "pdf/")
        
        return html_base, pdf_base
        
    except Exception as e:
        raise Exception(f"Failed to get current eAIP URL: {e}")


def categorize_chart(chart_name: str) -> str:
    """Categorize chart based on name."""
    name_upper = chart_name.upper()
    
    # SID charts
    if 'DEPARTURE' in name_upper or 'SID' in name_upper:
        return 'SID'
    
    # STAR charts
    if 'ARRIVAL' in name_upper or 'STAR' in name_upper:
        return 'STAR'
    
    # Approach charts
    if any(kw in name_upper for kw in ['APPROACH', 'ILS', 'VOR', 'RNP', 'RNAV', 'LOC', 'NDB', 'DME', 'IAC']):
        return 'Approach'
    
    # Airport diagrams / Ground charts
    if any(kw in name_upper for kw in ['AERODROME CHART', 'PARKING', 'DOCKING', 'GROUND MOVEMENT', 
                                        'TAXI', 'ADC', 'LAYOUT', 'LIGHTING', 'MARKING', 'GMC']):
        return 'Airport Diagram'
    
    # General
    return 'General'


def get_aerodrome_charts(icao_code: str) -> List[Dict[str, str]]:
    """
    Fetch aerodrome charts for a given ICAO code from Hong Kong eAIP.
    
    Args:
        icao_code: 4-letter ICAO code (e.g., 'VHHH')
        
    Returns:
        List of dictionaries with 'name', 'url', and 'type' keys
    """
    icao_code = icao_code.upper().strip()
    charts = []
    
    try:
        # Get current eAIP base URLs
        html_base, pdf_base = get_current_eaip_base()
        
        # Construct airport page URL
        # Pattern: eAIP/VH-AD-2-{ICAO}-en-US.html
        airport_page_url = urljoin(html_base, f"eAIP/VH-AD-2-{icao_code}-en-US.html")
        
        # Fetch the airport page
        response = requests.get(airport_page_url, timeout=30)
        
        if response.status_code == 404:
            print(f"Airport {icao_code} not found in Hong Kong eAIP")
            return []
            
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find all PDF links in the charts table (AD 2.24 section)
        for link in soup.find_all('a', href=True):
            href = link['href']
            
            if '.pdf' in href.lower():
                # Extract PDF filename from href
                # PDFs are at ../../pdf/VH-AD-2-{ICAO}-xxx.pdf relative to eAIP folder
                pdf_filename = href.split('/')[-1]
                
                # Construct full URL using pdf_base
                full_url = urljoin(pdf_base, pdf_filename)
                
                # Get chart name from parent row
                chart_name = None
                parent_tr = link.find_parent('tr')
                
                if parent_tr:
                    cells = parent_tr.find_all('td')
                    if cells:
                        # First cell contains chart name
                        chart_name = cells[0].get_text(strip=True)
                
                # Fallback: extract from filename
                if not chart_name:
                    filename = href.split('/')[-1].replace('.pdf', '')
                    chart_name = filename
                
                # Clean up chart name
                chart_name = re.sub(r'\s+', ' ', chart_name).strip()
                # Fix encoding issues
                chart_name = chart_name.replace('â', '-').replace('Â', '').strip()
                
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
    
    icao = sys.argv[1] if len(sys.argv) > 1 else "VHHH"
    print(f"Fetching charts for {icao}...")
    
    charts = get_aerodrome_charts(icao)
    
    if charts:
        print(f"\nFound {len(charts)} chart(s):")
        for chart in charts:
            print(f"  [{chart.get('type', 'N/A')}] {chart['name']}")
            print(f"    URL: {chart['url']}")
    else:
        print("No charts found.")

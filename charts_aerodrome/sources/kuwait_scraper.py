"""
Kuwait DGCA AIP Scraper

Scrapes aerodrome charts from Kuwait's Directorate General of Civil Aviation AIP.
PDFs are hosted on Azure blob storage.
Note: PDFs are password protected but can still be linked.

Main airport: OKKK (Kuwait International Airport)

Source: https://dgca.gov.kw/AIP
"""

import requests
from bs4 import BeautifulSoup
from urllib.parse import unquote
import re


BASE_URL = "https://www.dgca.gov.kw/AIP"
BLOB_BASE = "https://dgcawebappstg.blob.core.windows.net/upload/AIPItemSub/live/"


def categorize_chart(name: str) -> str:
    """Categorize chart based on name."""
    name_upper = name.upper()
    
    # SID patterns
    if 'SID' in name_upper or 'DEPARTURE' in name_upper:
        if 'ARRIVAL' not in name_upper:
            return 'SID'
    
    # STAR patterns
    if 'STAR' in name_upper or 'ARRIVAL' in name_upper:
        if 'DEPARTURE' not in name_upper:
            return 'STAR'
    
    # SID and STAR combined
    if 'SID' in name_upper and 'STAR' in name_upper:
        return 'SID/STAR'
    
    # Approach patterns
    if any(x in name_upper for x in ['APPROACH', 'ILS', 'RNP', 'VOR', 'NDB', 'VISUAL APPROACH']):
        return 'APP'
    
    # Ground/Aerodrome patterns
    if any(x in name_upper for x in ['PARKING', 'TAXI', 'GROUND', 'ADC', 'AERODROME CHART']):
        return 'GND'
    
    # General patterns
    if any(x in name_upper for x in ['OBSTACLE', 'TERRAIN', 'AREA CHART', 'SURVEILLANCE', 'GEN', 'ENR']):
        return 'GEN'
    
    return 'GEN'


def get_aerodrome_charts(icao_code: str, verbose: bool = False) -> list:
    """
    Get aerodrome charts for a Kuwait airport.
    
    Args:
        icao_code: ICAO code (e.g., 'OKKK')
        verbose: Enable verbose output
        
    Returns:
        List of chart dictionaries with 'name', 'url', and 'type' keys
    """
    icao_code = icao_code.upper()
    
    if verbose:
        print(f"Fetching Kuwait AIP page...")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    try:
        response = requests.get(BASE_URL, headers=headers, timeout=30)
        response.raise_for_status()
    except requests.RequestException as e:
        if verbose:
            print(f"Error fetching AIP page: {e}")
        return []
    
    soup = BeautifulSoup(response.text, 'html.parser')
    charts = []
    
    # Find all PDF links from Azure blob storage
    for link in soup.find_all('a', href=True):
        href = link.get('href', '')
        
        # Only process Azure blob storage links
        if 'dgcawebappstg.blob.core.windows.net' not in href:
            continue
        
        if not href.endswith('.pdf'):
            continue
        
        # Extract filename from URL
        filename = href.split('/')[-1]
        # Decode URL encoding
        filename = unquote(filename)
        # Remove .pdf extension for display name
        name = filename.replace('.pdf', '')
        
        # Check if this chart is for the requested airport
        # Charts for OKKK contain "OKKK" in the filename
        if icao_code in filename.upper():
            chart_type = categorize_chart(name)
            charts.append({
                'name': name,
                'url': href,
                'type': chart_type
            })
            if verbose:
                print(f"  Found: {name} [{chart_type}]")
    
    if verbose:
        print(f"Total charts found for {icao_code}: {len(charts)}")
    
    # Sort charts by type then name
    type_order = {'GEN': 0, 'GND': 1, 'SID': 2, 'SID/STAR': 3, 'STAR': 4, 'APP': 5}
    charts.sort(key=lambda x: (type_order.get(x['type'], 99), x['name']))
    
    return charts


# For CLI compatibility
class KuwaitScraper:
    """Class wrapper for CLI compatibility."""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
    
    def get_charts(self, icao_code: str) -> list:
        return get_aerodrome_charts(icao_code, self.verbose)


if __name__ == "__main__":
    import sys
    icao = sys.argv[1] if len(sys.argv) > 1 else "OKKK"
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    
    print(f"Fetching charts for {icao}...")
    charts = get_aerodrome_charts(icao, verbose=verbose)
    
    if charts:
        print(f"\nFound {len(charts)} charts:")
        for chart in charts:
            print(f"  [{chart['type']}] {chart['name']}")
            print(f"       {chart['url']}")
    else:
        print("No charts found.")

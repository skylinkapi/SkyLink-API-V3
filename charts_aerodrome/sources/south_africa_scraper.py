"""
South Africa CAA Aerodrome Charts Scraper
Scrapes aerodrome charts from South African Civil Aviation Authority

Base URL: https://www.caa.co.za/industry-information/aeronautical-information-aeronautical-charts/
Structure:
- HTML table with all airports and charts
- Airport headers contain ICAO code (e.g., "O.R Tambo INTL- FAOR")
- Chart PDFs hosted on Azure blob storage
- ICAO prefix: FA*

Examples: FAOR (O.R. Tambo), FACT (Cape Town), FALE (King Shaka/Durban)
"""

import requests
from bs4 import BeautifulSoup
from urllib.parse import quote
import re
from typing import List, Dict


BASE_URL = "https://www.caa.co.za/industry-information/aeronautical-information-aeronautical-charts/"
BLOB_BASE = "https://caasanwebsitestorage.blob.core.windows.net/aeronautical-charts/"


def categorize_chart(chart_type: str, chart_name: str) -> str:
    """
    Categorize chart based on its type and name.
    
    Args:
        chart_type: The chart type from the table (e.g., "Instrument Approach Chart")
        chart_name: The chart name/description
        
    Returns:
        Category string (SID, STAR, Approach, Airport Diagram, General)
    """
    chart_type_upper = chart_type.upper()
    chart_name_upper = chart_name.upper()
    
    # SID - Standard Instrument Departure
    if 'SID' in chart_type_upper or 'DEPARTURE' in chart_type_upper:
        return 'SID'
    
    # STAR - Standard Terminal Arrival
    if 'STAR' in chart_type_upper or 'ARRIVAL' in chart_type_upper:
        return 'STAR'
    
    # Approach charts
    if any(keyword in chart_type_upper for keyword in [
        'APPROACH', 'ILS', 'VOR', 'RNAV', 'RNP', 'NDB', 'PRECISION APPROACH', 'INSTRUMENT APPROACH'
    ]):
        return 'Approach'
    
    # Airport diagrams and ground charts
    if any(keyword in chart_type_upper for keyword in [
        'AERODROME', 'HELIPORT', 'PARKING', 'DOCKING', 'GROUND MOVEMENT',
        'TAXI', 'HOTSPOT', 'HOT SPOT', 'RESTRICTED VISIBILITY', 'HELICOPTER'
    ]):
        return 'Airport Diagram'
    
    # General - obstacles, radar, terrain, etc.
    return 'General'


def get_aerodrome_charts(icao_code: str) -> List[Dict[str, str]]:
    """
    Get all aerodrome charts for a given ICAO code from South Africa CAA.
    
    Args:
        icao_code: 4-letter ICAO code (e.g., 'FAOR')
        
    Returns:
        List of dictionaries with 'name', 'url', and 'type' keys
    """
    icao_code = icao_code.upper()
    charts = []
    
    try:
        # Fetch the main page
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(BASE_URL, headers=headers, timeout=60)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'lxml')
        
        # Find all table rows
        rows = soup.find_all('tr')
        
        for row in rows:
            cells = row.find_all('td')
            if len(cells) < 8:
                continue
            
            # First cell contains airport name with ICAO code
            airport_cell = cells[0].get_text(strip=True)
            
            # Check if this row belongs to our airport
            # Format: "Airport Name - ICAO" or "Airport Name – ICAO" (different dash)
            if icao_code not in airport_cell:
                continue
            
            # Extract chart information
            chart_type = cells[1].get_text(strip=True)  # e.g., "Instrument Approach Chart"
            chart_name = cells[2].get_text(strip=True)  # e.g., "ILS Y RWY 03L"
            chart_code = cells[3].get_text(strip=True)  # e.g., "ILS_02"
            
            # Find download link
            link = row.find('a', href=True)
            if not link:
                continue
            
            chart_url = link['href']
            
            # Ensure full URL
            if not chart_url.startswith('http'):
                # Relative URL, build full path
                if chart_url.startswith('/'):
                    chart_url = BLOB_BASE + chart_url.split('/')[-1]
                else:
                    chart_url = BLOB_BASE + chart_url
            
            # URL encode spaces in filename
            if ' ' in chart_url:
                # Split URL and encode just the filename part
                parts = chart_url.rsplit('/', 1)
                if len(parts) == 2:
                    base, filename = parts
                    filename_encoded = quote(filename, safe='')
                    chart_url = f"{base}/{filename_encoded}"
            
            # Build chart name
            full_name = f"{icao_code} - {chart_name}"
            if chart_type and chart_type not in chart_name:
                # Add chart type if not redundant
                if 'Chart' not in chart_name:
                    full_name = f"{icao_code} - {chart_type}: {chart_name}"
            
            # Categorize
            category = categorize_chart(chart_type, chart_name)
            
            charts.append({
                'name': full_name,
                'url': chart_url,
                'type': category
            })
        
        return charts
        
    except Exception as e:
        print(f"Error fetching charts for {icao_code}: {e}")
        import traceback
        traceback.print_exc()
        return []


def main():
    """CLI entry point for testing."""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python south_africa_scraper.py <ICAO_CODE>")
        print("Example: python south_africa_scraper.py FAOR")
        print("\nCommon South African airports:")
        print("  FAOR - O.R. Tambo International (Johannesburg)")
        print("  FACT - Cape Town International")
        print("  FALE - King Shaka International (Durban)")
        print("  FALA - Lanseria International")
        print("  FABL - Bram Fischer International (Bloemfontein)")
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
        
        for chart_type, type_charts in sorted(by_type.items()):
            print(f"\n{chart_type} ({len(type_charts)}):")
            for chart in type_charts:
                print(f"  {chart['name']}")
                print(f"    {chart['url'][:80]}...")
    else:
        print("No charts found")


if __name__ == "__main__":
    main()

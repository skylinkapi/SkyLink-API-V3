#!/usr/bin/env python3
"""
Austria eAIP Scraper
Scrapes aerodrome charts from Austro Control AIP (eaip.austrocontrol.at)

Base URL: https://eaip.austrocontrol.at/
Structure:
- Main page has link to current version: ./lo/{YYMMDD}/index.htm
- AD 2 page: ad_2.htm - list of airports
- Charts page: ad_2_{icao}.htm - list of charts with PDF links
- PDFs: Charts/{ICAO}/LO_AD_2_{ICAO}_{map}_en.pdf

ICAO prefix: LO*
Examples: LOWW (Vienna), LOWI (Innsbruck), LOWS (Salzburg), LOWG (Graz), LOWK (Klagenfurt), LOWL (Linz)
"""

import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import sys


BASE_URL = "https://eaip.austrocontrol.at/"


def get_latest_aip_base_url():
    """
    Get the base URL for the latest (currently effective) Austria AIP.
    
    Returns:
        str: Base URL like 'https://eaip.austrocontrol.at/lo/260123/'
    """
    try:
        response = requests.get(BASE_URL, timeout=30)
        soup = BeautifulSoup(response.text, 'lxml')
        
        # Find the "aktuelle Ausgabe / current version" link
        for link in soup.find_all('a', href=True):
            href = link['href']
            text = link.get_text(strip=True)
            
            # Check for current version link
            if 'aktuelle' in text.lower() or 'current version' in text.lower():
                # href is like ./lo/260123/index.htm
                # Extract base path: ./lo/260123/
                if '/lo/' in href and '/index.htm' in href:
                    base_path = href.replace('index.htm', '')
                    return urljoin(BASE_URL, base_path)
        
        # Fallback: look for any lo/YYMMDD pattern
        for link in soup.find_all('a', href=True):
            href = link['href']
            match = re.search(r'\./lo/(\d{6})/index\.htm', href)
            if match:
                base_path = f"./lo/{match.group(1)}/"
                return urljoin(BASE_URL, base_path)
        
        return None
        
    except Exception as e:
        print(f"Error getting latest AIP URL: {e}")
        return None


def get_airport_charts_url(icao_code, base_url):
    """
    Construct the URL for an airport's charts page.
    
    Args:
        icao_code: 4-letter ICAO code (e.g., 'LOWW')
        base_url: Base AIP URL
        
    Returns:
        str: Full URL to airport charts page
    """
    # Charts page is: ad_2_{icao}.htm (lowercase)
    charts_page = f"ad_2_{icao_code.lower()}.htm"
    return urljoin(base_url, charts_page)


def categorize_chart(chart_name):
    """
    Categorize a chart based on its English description.
    
    Args:
        chart_name: Chart description/name
        
    Returns:
        str: Category (SID/STAR/Approach/Airport Diagram/General)
    """
    name_upper = chart_name.upper()
    
    # SID - Standard Instrument Departure
    if any(keyword in name_upper for keyword in ['SID', 'STANDARD DEPARTURE', 'DEPARTURE CHART']):
        return 'SID'
    
    # STAR - Standard Terminal Arrival
    if any(keyword in name_upper for keyword in ['STAR', 'STANDARD ARRIVAL', 'ARRIVAL CHART', 'RNAV ARRIVAL', 'TRANSITION TO RWY']):
        return 'STAR'
    
    # Approach charts
    if any(keyword in name_upper for keyword in [
        'APPROACH', 'ILS', 'LOC', 'VOR', 'NDB', 'RNAV', 'RNP', 'DME',
        'INSTRUMENT APPROACH', 'VISUAL APPROACH', 'CIRCLING'
    ]):
        return 'Approach'
    
    # Airport diagrams and ground charts
    if any(keyword in name_upper for keyword in [
        'AERODROME CHART', 'AIRPORT CHART', 'PARKING', 'DOCKING',
        'GROUND MOVEMENT', 'TAXI', 'FLUGPLATZKARTE'
    ]):
        return 'Airport Diagram'
    
    # General - everything else (obstacle charts, terrain charts, ATC surveillance, etc.)
    return 'General'


def get_aerodrome_charts(icao_code):
    """
    Get all aerodrome charts for a given ICAO code from Austria eAIP.
    
    Args:
        icao_code: 4-letter ICAO code (e.g., 'LOWW')
        
    Returns:
        List of dictionaries with 'name', 'url', and 'type' keys
    """
    charts = []
    icao_code = icao_code.upper()
    
    try:
        # Get the latest AIP base URL
        base_url = get_latest_aip_base_url()
        if not base_url:
            print("Could not determine current AIP version")
            return charts
        
        # Get the charts page URL for this airport
        charts_url = get_airport_charts_url(icao_code, base_url)
        
        print(f"Fetching {charts_url}")
        
        response = requests.get(charts_url, timeout=30)
        if response.status_code == 404:
            print(f"Airport {icao_code} not found in Austria AIP")
            return charts
        
        soup = BeautifulSoup(response.text, 'lxml')
        
        # Find all table rows with chart links
        # Structure: <TR><TD><A href="Charts/...">MAP code</A></TD><TD>German<BR/><I>English</I></TD></TR>
        for row in soup.find_all('tr'):
            cells = row.find_all('td')
            if len(cells) < 2:
                continue
            
            # First cell should contain the PDF link
            link = cells[0].find('a', href=True)
            if not link or '.pdf' not in link['href'].lower():
                continue
            
            pdf_href = link['href']
            map_code = link.get_text(strip=True)
            
            # Second cell contains the description
            # Try to get English description from <I> tag first
            desc_cell = cells[1]
            english_desc = desc_cell.find('i')
            
            if english_desc:
                chart_name = english_desc.get_text(strip=True)
            else:
                # Fallback to full text
                chart_name = desc_cell.get_text(strip=True)
            
            # Clean up the chart name
            chart_name = re.sub(r'\s+', ' ', chart_name).strip()
            
            # Build full chart name: "MAP code - Description"
            full_name = f"{map_code} - {chart_name}" if chart_name else map_code
            
            # Build full URL
            full_url = urljoin(charts_url, pdf_href)
            
            # Categorize the chart
            chart_type = categorize_chart(chart_name)
            
            charts.append({
                'name': full_name,
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
        print("Usage: python austria_scraper.py <ICAO_CODE>")
        print("Example: python austria_scraper.py LOWW")
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

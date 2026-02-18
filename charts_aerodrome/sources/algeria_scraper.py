"""
Algeria eAIP Scraper
Scrapes aerodrome charts from Algeria SIA-ENNA

Base URL: https://www.sia-enna.dz/
Structure:
- Main page lists all airports and their charts
- PDF pattern: PDF/AIP/AD/AD2/{ICAO}/{chartfile}.pdf
- Chart types: AD.pdf, SID#.pdf, IAC#.pdf, VAC#.pdf, AOC#.pdf, APDC#.pdf, etc.

ICAO prefix: DA*
Examples: DAAG (Algiers), DABB (Annaba), DAOO (Oran)

NOTE: The website requires User-Agent header or it will reject connections.
"""

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import sys


BASE_URL = "https://www.sia-enna.dz/"
AIP_PAGE = "aeronautical-information-publication.html"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


def categorize_chart(filename, chart_name):
    """
    Categorize a chart based on its filename and name.
    
    Algeria uses standard ICAO chart type codes:
    - AD.pdf = Aerodrome Chart
    - SID#.pdf = Standard Instrument Departure
    - STAR#.pdf = Standard Arrival (if any)
    - IAC#.pdf = Instrument Approach Chart
    - VAC#.pdf = Visual Approach Chart
    - AOC#.pdf = Aerodrome Obstacle Chart
    - APDC#.pdf = Aircraft Parking/Docking Chart
    - PATC.pdf = Precision Approach Terrain Chart
    - ATCSMAC#.pdf = ATC Surveillance Minimum Altitude Chart
    """
    filename_upper = filename.upper()
    name_upper = chart_name.upper()
    
    # SID charts
    if filename_upper.startswith("SID"):
        return "SID"
    
    # STAR charts
    if filename_upper.startswith("STAR"):
        return "STAR"
    
    # Approach charts (IAC = Instrument Approach Chart)
    if filename_upper.startswith("IAC") or "INSTRUMENT APPROACH" in name_upper:
        return "Approach"
    
    # Visual approach charts
    if filename_upper.startswith("VAC") or "VISUAL APPROACH" in name_upper:
        return "Approach"
    
    # Airport diagrams and parking
    if filename_upper.startswith("AD.") or filename_upper.startswith("APDC"):
        return "Airport Diagram"
    if "AERODROME" in name_upper and "CHART" in name_upper and "OBSTACLE" not in name_upper:
        return "Airport Diagram"
    if "PARKING" in name_upper or "DOCKING" in name_upper:
        return "Airport Diagram"
    
    # Obstacle charts and terrain charts (general info)
    if filename_upper.startswith("AOC") or filename_upper.startswith("PATC"):
        return "General"
    if "OBSTACLE" in name_upper or "TERRAIN" in name_upper:
        return "General"
    
    # ATC/surveillance charts
    if filename_upper.startswith("ATCSMAC"):
        return "General"
    
    # Text data (airport info)
    if filename_upper.endswith(".PDF") and len(filename_upper) == 8:
        # Likely ICAO.pdf (text data)
        return "General"
    
    return "General"


def get_aerodrome_charts(icao_code):
    """
    Get all aerodrome charts for a given ICAO code from Algeria eAIP.
    
    Args:
        icao_code: 4-letter ICAO code (e.g., 'DAAG' for Algiers)
        
    Returns:
        List of dictionaries with 'name', 'url', and 'type' keys
    """
    charts = []
    icao_code = icao_code.upper()
    
    # Validate ICAO code
    if not icao_code.startswith("DA"):
        print(f"Warning: {icao_code} may not be an Algeria airport code (should start with DA)")
    
    try:
        # Fetch the main AIP page
        url = urljoin(BASE_URL, AIP_PAGE)
        response = requests.get(url, headers=HEADERS, timeout=30)
        
        if response.status_code != 200:
            print(f"Error: Got status code {response.status_code}")
            return charts
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Find all links for the requested airport
        # Pattern: PDF/AIP/AD/AD2/{ICAO}/{filename}.pdf
        target_path = f"/AD/AD2/{icao_code}/"
        
        for link in soup.find_all("a", href=True):
            href = link["href"]
            
            if target_path not in href:
                continue
            
            if not href.lower().endswith(".pdf"):
                continue
            
            # Extract chart name and filename
            chart_name = link.get_text(strip=True)
            filename = href.split("/")[-1]
            
            # Skip the text data PDF (ICAO.pdf)
            if filename.upper() == f"{icao_code}.PDF":
                continue
            
            # Build full URL
            full_url = urljoin(BASE_URL, href)
            
            # Categorize the chart
            chart_type = categorize_chart(filename, chart_name)
            
            charts.append({
                "name": chart_name,
                "url": full_url,
                "type": chart_type
            })
        
        if not charts:
            print(f"Airport {icao_code} not found in Algeria AIP")
        
        return charts
        
    except requests.exceptions.ConnectionError as e:
        print(f"Connection error: {e}")
        print("Note: Algeria AIP website may require specific headers or be temporarily unavailable")
        return charts
    except Exception as e:
        print(f"Error scraping {icao_code}: {e}")
        import traceback
        traceback.print_exc()
        return charts


def list_airports():
    """
    List all available airports in Algeria AIP.
    
    Returns:
        List of ICAO codes
    """
    airports = set()
    
    try:
        url = urljoin(BASE_URL, AIP_PAGE)
        response = requests.get(url, headers=HEADERS, timeout=30)
        
        if response.status_code != 200:
            return []
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        for link in soup.find_all("a", href=True):
            href = link["href"]
            if "/AD/AD2/" in href and ".pdf" in href.lower():
                parts = href.split("/")
                for i, part in enumerate(parts):
                    if part == "AD2" and i + 1 < len(parts):
                        icao = parts[i + 1]
                        if len(icao) == 4 and icao.startswith("DA"):
                            airports.add(icao)
        
        return sorted(airports)
        
    except Exception as e:
        print(f"Error listing airports: {e}")
        return []


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python algeria_scraper.py <ICAO_CODE>")
        print("       python algeria_scraper.py --list")
        print()
        print("Examples:")
        print("  python algeria_scraper.py DAAG   # Algiers")
        print("  python algeria_scraper.py DABB   # Annaba")
        print("  python algeria_scraper.py --list # List all airports")
        sys.exit(1)
    
    if sys.argv[1] == "--list":
        print("Fetching list of Algeria airports...")
        airports = list_airports()
        if airports:
            print(f"\nFound {len(airports)} airports:")
            for ap in airports:
                print(f"  {ap}")
        else:
            print("No airports found")
        sys.exit(0)
    
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

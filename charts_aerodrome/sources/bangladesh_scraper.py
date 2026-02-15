"""
Bangladesh AIP Scraper
Scrapes aerodrome charts from Civil Aviation Authority of Bangladesh (CAAB)

Website: http://www.caab.gov.bd/aip/aerodromes/aerodromes.html

Structure:
- Each airport has a single PDF containing all aerodrome information and charts
- PDF URL pattern: http://www.caab.gov.bd/aip/aerodromes/{icao_lowercase}.pdf

ICAO prefix: VG*

Examples: VGHS (Dhaka), VGEG (Chittagong), VGSY (Sylhet), VGCB (Cox's Bazar)
"""

import requests
from bs4 import BeautifulSoup
from typing import List, Dict


BASE_URL = "http://www.caab.gov.bd/aip/aerodromes/"
INDEX_URL = "http://www.caab.gov.bd/aip/aerodromes/aerodromes.html"

# Known Bangladesh airports with their names
BANGLADESH_AIRPORTS = {
    "VGHS": "Hazrat Shahjalal International Airport (Dhaka)",
    "VGEG": "Shah Amanat International Airport (Chittagong)",
    "VGSY": "Osmani International Airport (Sylhet)",
    "VGBR": "Barisal Airport",
    "VGBG": "Bogra Airport",
    "VGCB": "Cox's Bazar Airport",
    "VGJR": "Jessore Airport",
    "VGRJ": "Shah Mokhdum Airport (Rajshahi)",
    "VGIS": "Ishurdi Airport",
    "VGSD": "Saidpur Airport",
    "VGTJ": "Tejgaon Airport",
    "VGSH": "Shamshernagar Stolport",
    "VGCM": "Comilla Stolport",
}


def get_available_airports() -> Dict[str, str]:
    """
    Fetch the list of available airports from the CAAB website.
    
    Returns:
        Dictionary mapping ICAO codes to airport names
    """
    airports = {}
    
    try:
        response = requests.get(INDEX_URL, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        for link in soup.find_all('a', href=True):
            href = link['href'].lower()
            text = link.get_text(strip=True)
            
            # Look for PDF links that match ICAO pattern (vgXX.pdf)
            if href.endswith('.pdf') and href.startswith('vg') and len(href) == 8:
                icao = href.replace('.pdf', '').upper()
                if text and len(text) > 3:
                    airports[icao] = text
                    
        return airports if airports else BANGLADESH_AIRPORTS
        
    except Exception as e:
        print(f"Warning: Could not fetch airport list: {e}")
        return BANGLADESH_AIRPORTS


def get_aerodrome_charts(icao_code: str) -> List[Dict[str, str]]:
    """
    Get aerodrome charts for a Bangladesh airport.
    
    Args:
        icao_code: ICAO airport code (e.g., 'VGHS')
        
    Returns:
        List of chart dictionaries with 'name', 'url', and 'type' keys
    """
    icao_code = icao_code.upper().strip()
    
    # Validate ICAO prefix
    if not icao_code.startswith('VG'):
        print(f"Invalid Bangladesh ICAO code: {icao_code} (should start with VG)")
        return []
    
    # Construct PDF URL
    pdf_url = f"{BASE_URL}{icao_code.lower()}.pdf"
    
    # Verify PDF exists
    try:
        response = requests.head(pdf_url, timeout=30, allow_redirects=True)
        
        if response.status_code == 404:
            print(f"Airport {icao_code} not found in Bangladesh AIP")
            # Show available airports
            airports = get_available_airports()
            if airports:
                print(f"Available airports: {', '.join(sorted(airports.keys()))}")
            return []
            
        if response.status_code != 200:
            print(f"Error accessing {icao_code} PDF: HTTP {response.status_code}")
            return []
            
    except requests.RequestException as e:
        print(f"Error checking PDF availability: {e}")
        return []
    
    # Get airport name
    airports = get_available_airports()
    airport_name = airports.get(icao_code, f"{icao_code} Airport")
    
    # Return single PDF containing all charts
    return [
        {
            'name': f'{icao_code} Aerodrome Charts - {airport_name}',
            'url': pdf_url,
            'type': 'General'
        }
    ]


# For testing
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        icao = sys.argv[1]
    else:
        # List available airports
        print("Available Bangladesh airports:")
        airports = get_available_airports()
        for icao, name in sorted(airports.items()):
            print(f"  {icao}: {name}")
        print("\nUsage: python bangladesh_scraper.py <ICAO>")
        print("Example: python bangladesh_scraper.py VGHS")
        sys.exit(0)
    
    print(f"Fetching charts for {icao}...")
    
    charts = get_aerodrome_charts(icao)
    
    if charts:
        print(f"\nFound {len(charts)} chart(s):")
        for chart in charts:
            print(f"  [{chart.get('type', 'N/A')}] {chart['name']}")
            print(f"    URL: {chart['url']}")
    else:
        print("No charts found.")

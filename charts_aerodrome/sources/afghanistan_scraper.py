"""
Afghanistan AIP Scraper
Scrapes aerodrome charts from Afghanistan Civil Aviation Authority (ACAA)

Website: https://www.afgais.com/

Structure:
- Currently only OAKB (Kabul International Airport) has charts available
- Single PDF containing all OAKB charts

ICAO prefix: OA*

Examples: OAKB (Kabul International Airport)
"""

from typing import List, Dict


# Direct link to OAKB charts PDF
OAKB_CHARTS_URL = "https://www.afgais.com/_files/ugd/a8bf88_f7fa4602373b486ea2129884f1bf9aac.pdf"

# Supported airports
SUPPORTED_AIRPORTS = {
    "OAKB": "Kabul International Airport (Hamid Karzai)"
}


def get_aerodrome_charts(icao_code: str) -> List[Dict[str, str]]:
    """
    Get aerodrome charts for an Afghanistan airport.
    
    Args:
        icao_code: ICAO airport code (e.g., 'OAKB')
        
    Returns:
        List of chart dictionaries with 'name', 'url', and 'type' keys
    """
    icao_code = icao_code.upper().strip()
    
    # Check if airport is supported
    if icao_code not in SUPPORTED_AIRPORTS:
        print(f"Airport {icao_code} not found in Afghanistan database.")
        print(f"Currently supported airports: {', '.join(SUPPORTED_AIRPORTS.keys())}")
        return []
    
    # Return OAKB charts
    if icao_code == "OAKB":
        return [
            {
                'name': 'OAKB Charts (All aerodrome charts)',
                'url': OAKB_CHARTS_URL,
                'type': 'General'
            }
        ]
    
    return []


# For testing
if __name__ == "__main__":
    import sys
    
    icao = sys.argv[1] if len(sys.argv) > 1 else "OAKB"
    print(f"Fetching charts for {icao}...")
    
    charts = get_aerodrome_charts(icao)
    
    if charts:
        print(f"\nFound {len(charts)} chart(s):")
        for chart in charts:
            print(f"  - {chart['name']}")
            print(f"    URL: {chart['url']}")
            print(f"    Type: {chart.get('type', 'N/A')}")
    else:
        print("No charts found.")

"""
Bhutan AIP Scraper
Returns link to Bhutan Department of Air Transport AIP

Website: https://www.doat.gov.bt/aip/

ICAO prefix: VQ*

Examples: VQPR (Paro International Airport)
"""

from typing import List, Dict


AIP_URL = "https://www.doat.gov.bt/aip/"

# Known Bhutan airports
BHUTAN_AIRPORTS = {
    "VQPR": "Paro International Airport",
    "VQBT": "Bathpalathang Airport (Bumthang)",
    "VQGP": "Gelephu Airport",
    "VQYW": "Yongphulla Airport",
}


def get_aerodrome_charts(icao_code: str) -> List[Dict[str, str]]:
    """
    Get aerodrome charts link for a Bhutan airport.
    
    Args:
        icao_code: ICAO airport code (e.g., 'VQPR')
        
    Returns:
        List of chart dictionaries with 'name', 'url', and 'type' keys
    """
    icao_code = icao_code.upper().strip()
    
    # Validate ICAO prefix
    if not icao_code.startswith('VQ'):
        print(f"Invalid Bhutan ICAO code: {icao_code} (should start with VQ)")
        return []
    
    # Get airport name
    airport_name = BHUTAN_AIRPORTS.get(icao_code, f"{icao_code} Airport")
    
    return [
        {
            'name': f'Bhutan AIP - {airport_name}',
            'url': AIP_URL,
            'type': 'General'
        }
    ]


# For testing
if __name__ == "__main__":
    import sys
    
    icao = sys.argv[1] if len(sys.argv) > 1 else "VQPR"
    print(f"Fetching charts for {icao}...")
    
    charts = get_aerodrome_charts(icao)
    
    if charts:
        print(f"\nFound {len(charts)} chart(s):")
        for chart in charts:
            print(f"  [{chart.get('type', 'N/A')}] {chart['name']}")
            print(f"    URL: {chart['url']}")
    else:
        print("No charts found.")

"""
Japan Aerodrome Chart Scraper
Source: nagodede.github.io - Single PDF per airport
"""

def get_aerodrome_charts(icao_code):
    """
    Get aerodrome charts for a Japanese airport.
    Japan uses RJ** ICAO codes (RJAA, RJTT, RJBB, etc.)

    Args:
        icao_code: ICAO code of the airport (e.g., 'RJAA', 'RJTT')

    Returns:
        List of chart dictionaries with 'name', 'url', and 'type' keys
    """
    icao_code = icao_code.upper()

    # Validate Japanese ICAO code (starts with RJ)
    if not icao_code.startswith('RJ'):
        return []

    # Single PDF containing all charts for the airport
    url = f"https://nagodede.github.io/aip/japan/documents/{icao_code}_chart.pdf"
    
    return [{
        'name': f'{icao_code} - Complete Aerodrome Charts',
        'url': url,
        'type': 'General'
    }]


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python japan_scraper.py <ICAO_CODE>")
        print("Example: python japan_scraper.py RJAA")
        sys.exit(1)
    
    icao_code = sys.argv[1].upper()
    
    charts = get_aerodrome_charts(icao_code)
    
    if charts:
        for chart in charts:
            print(f"\n{chart['type']}:")
            print(f"  {chart['name']}")
            print(f"    {chart['url']}")
    else:
        print(f"No charts found for {icao_code}")

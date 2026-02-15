"""
Djibouti AIP Scraper
Scrapes aerodrome charts from Djibouti Civil Aviation AIP PDF

Base URL: https://djibaviationcivile.com/aip
Structure:
- Single monolithic PDF containing all AIP information hosted on Firebase
- Charts section at AD 2.24 with page references
- ICAO prefix: HD*

Examples: HDAM (Djibouti-Ambouli International)

Chart extraction approach:
- Use direct Firebase PDF URL with page anchors for individual charts
- No caching or local PDF processing
"""

import sys
from typing import List, Dict
from urllib.parse import quote


# Firebase URL components for AIP PDF (direct link - no caching)
FIREBASE_BASE = "https://firebasestorage.googleapis.com/v0/b/aviation-57c71.appspot.com/o/"
FIREBASE_PATH = "AIP/Publications d'Information Aéronautique/AIP-DJIBOUTI.pdf"
FIREBASE_QUERY = "?alt=media&token=3183b89c-e2e5-4f08-a1dd-3632182c934d"


# Chart definitions from AD 2.24 with estimated page offsets
# Base page is 260 (first chart after the chart list on page 258-259)
HDAM_CHARTS = [
    {"code": "ADC 01", "name": "HDAM - Aerodrome Chart ICAO", "page_offset": 0, "type": "Airport Diagram"},
    {"code": "APDC 01", "name": "HDAM - Aircraft Parking/Docking Chart", "page_offset": 1, "type": "Airport Diagram"},
    {"code": "AOC 01", "name": "HDAM - Aerodrome Obstacles Chart ICAO Type A", "page_offset": 2, "type": "General"},
    {"code": "ARC", "name": "HDAM - Area Chart", "page_offset": 3, "type": "General"},
    {"code": "SID 1", "name": "HDAM - SID RWY 09", "page_offset": 4, "type": "SID"},
    {"code": "SID 1a", "name": "HDAM - SID RWY 09 Text E", "page_offset": 5, "type": "SID"},
    {"code": "SID 1b", "name": "HDAM - SID RWY 09 Text F", "page_offset": 6, "type": "SID"},
    {"code": "SID 2", "name": "HDAM - SID RWY 27", "page_offset": 7, "type": "SID"},
    {"code": "SID 2a", "name": "HDAM - SID RWY 27 Text", "page_offset": 8, "type": "SID"},
    {"code": "STAR 1", "name": "HDAM - STAR RWY 09", "page_offset": 9, "type": "STAR"},
    {"code": "STAR 2", "name": "HDAM - STAR RWY 27", "page_offset": 10, "type": "STAR"},
    {"code": "DATA 01", "name": "HDAM - Procedure Data", "page_offset": 11, "type": "General"},
    {"code": "IAC 01", "name": "HDAM - IAC VOR RWY 09", "page_offset": 12, "type": "Approach"},
    {"code": "IAC 02", "name": "HDAM - IAC RNAV GNSS Z RWY 09", "page_offset": 13, "type": "Approach"},
    {"code": "IAC D 02a", "name": "HDAM - Data/Coding GNSS Z RWY 09", "page_offset": 14, "type": "Approach"},
    {"code": "IAC 03", "name": "HDAM - IAC RNAV GNSS Y RWY 09", "page_offset": 15, "type": "Approach"},
    {"code": "IAC D 03a", "name": "HDAM - Data/Coding GNSS Y RWY 09", "page_offset": 16, "type": "Approach"},
    {"code": "IAC 04", "name": "HDAM - IAC ILS RWY 27", "page_offset": 17, "type": "Approach"},
    {"code": "IAC 05", "name": "HDAM - IAC VOR Z RWY 27", "page_offset": 18, "type": "Approach"},
    {"code": "IAC 06", "name": "HDAM - IAC VOR Y RWY 27", "page_offset": 19, "type": "Approach"},
    {"code": "IAC 07", "name": "HDAM - IAC RNAV GNSS Z RWY 27", "page_offset": 20, "type": "Approach"},
    {"code": "IAC D 07a", "name": "HDAM - Data/Coding GNSS Z RWY 27", "page_offset": 21, "type": "Approach"},
    {"code": "IAC 08", "name": "HDAM - IAC RNAV GNSS Y RWY 27", "page_offset": 22, "type": "Approach"},
    {"code": "IAC D 08a", "name": "HDAM - Data/Coding GNSS Y RWY 27", "page_offset": 23, "type": "Approach"},
    {"code": "IAC 09", "name": "HDAM - IAC VPT RWY 09", "page_offset": 24, "type": "Approach"},
    {"code": "IAC 10", "name": "HDAM - IAC VPT RWY 27", "page_offset": 25, "type": "Approach"},
    {"code": "APP 01", "name": "HDAM - Visual Approach Chart", "page_offset": 26, "type": "Approach"},
    {"code": "TXT 01", "name": "HDAM - Procedures Text", "page_offset": 27, "type": "General"},
    {"code": "ATT 01", "name": "HDAM - Visual Landing Chart", "page_offset": 28, "type": "Approach"},
]


def categorize_chart(chart_type: str) -> str:
    """
    Convert internal chart type to standard category.
    
    Args:
        chart_type: Internal type string
        
    Returns:
        str: Standard category (SID, STAR, APP, GND, GEN)
    """
    type_map = {
        "SID": "SID",
        "STAR": "STAR", 
        "Approach": "APP",
        "Airport Diagram": "GND",
        "General": "GEN"
    }
    return type_map.get(chart_type, "GEN")


def get_aerodrome_charts(icao_code: str, extract_pdfs: bool = False) -> List[Dict[str, str]]:
    """
    Get all aerodrome charts for a given ICAO code from Djibouti AIP.
    
    Args:
        icao_code: 4-letter ICAO code (currently only HDAM is supported)
        extract_pdfs: If True, extract individual chart PDFs. Default False (use page references).
        
    Returns:
        List of dictionaries with 'name', 'url', and 'type' keys
    """
    icao_code = icao_code.upper()
    
    # Djibouti only has one major airport
    if icao_code != "HDAM":
        print(f"Warning: {icao_code} is not a known Djibouti airport.")
        print("Djibouti only has HDAM (Djibouti-Ambouli International)")
        return []
    
    # Use the direct Firebase PDF URL (no caching)
    # Encode the path part to handle special characters like apostrophes
    encoded_path = quote(FIREBASE_PATH, safe='')
    pdf_url = FIREBASE_BASE + encoded_path + FIREBASE_QUERY
    
    charts = []
    
    # Base page for charts (0-indexed)
    charts_start = 259  # Page 260 in PDF (1-indexed)
    
    for chart_def in HDAM_CHARTS:
        page_num = charts_start + chart_def["page_offset"] + 1  # 1-indexed for PDF
        
        chart_name = chart_def["name"]
        chart_type = chart_def["type"]
        
        # Create URL with page anchor
        chart_url = f"{pdf_url}#page={page_num}"
        
        charts.append({
            'name': chart_name,
            'url': chart_url,
            'type': chart_type,
            'page': page_num
        })
    
    return charts


def main():
    """CLI entry point for testing."""
    if len(sys.argv) < 2:
        print("Usage: python djibouti_scraper.py <ICAO_CODE>")
        print("Example: python djibouti_scraper.py HDAM")
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
                print(f"  [{chart.get('page', '?')}] {chart['name']}")
                print(f"       {chart['url'][:80]}...")
    else:
        print("No charts found")


if __name__ == "__main__":
    main()

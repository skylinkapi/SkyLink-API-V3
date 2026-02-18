#!/usr/bin/env python3
"""
Netherlands eAIP Scraper
Scrapes aerodrome charts from Netherlands LVNL AIP (eaip.lvnl.nl)
Requires cloudscraper to bypass Cloudflare protection

ICAO prefix: EH*
Examples: EHAM (Amsterdam Schiphol), EHRD (Rotterdam), EHGG (Groningen), EHBK (Maastricht)
"""

import re
from urllib.parse import urljoin, quote

try:
    import cloudscraper
    CLOUDSCRAPER_AVAILABLE = True
except ImportError:
    CLOUDSCRAPER_AVAILABLE = False


BASE_URL = "https://eaip.lvnl.nl/web/eaip/"


def get_session():
    """Create a cloudscraper session to bypass Cloudflare protection"""
    if not CLOUDSCRAPER_AVAILABLE:
        raise ImportError(
            "cloudscraper is required for Netherlands scraper. Install with:\n"
            "pip install cloudscraper"
        )
    return cloudscraper.create_scraper()


def get_latest_airac_folder():
    """
    Get the latest AIRAC folder name from the default page.
    
    Returns:
        str: AIRAC folder name (e.g., 'AIRAC AMDT 01-2026_2026_01_22')
    """
    session = get_session()
    response = session.get(f"{BASE_URL}default.html", timeout=30)
    
    if response.status_code != 200:
        raise Exception(f"Failed to fetch default page: HTTP {response.status_code}")
    
    # Find the "Currently Effective Issue" link
    # Pattern: href="AIRAC AMDT XX-YYYY_YYYY_MM_DD\index.html"
    match = re.search(r'href="(AIRAC AMDT [^"\\]+)\\index\.html"', response.text)
    if match:
        return match.group(1)
    
    # Alternative pattern with forward slash
    match = re.search(r'href="(AIRAC AMDT [^"/]+)/index\.html"', response.text)
    if match:
        return match.group(1)
    
    raise Exception("Could not find current AIRAC folder in default page")


def get_airport_pages(icao_code, airac_folder):
    """
    Get all airport page URLs for an ICAO code.
    Netherlands splits airport data across multiple pages (1-14).
    
    Returns:
        list: List of valid page URLs
    """
    session = get_session()
    base_eaip = f"{BASE_URL}{quote(airac_folder)}/eAIP/"
    pages = []
    
    # Try pages 1-20 (most airports have fewer, but some like EHAM have 14)
    for page_num in range(1, 21):
        page_url = f"{base_eaip}EH-AD%202%20{icao_code}%20{page_num}-en-GB.html"
        try:
            response = session.head(page_url, timeout=10)
            if response.status_code == 200:
                pages.append(page_url)
            else:
                # Once we get a 404, stop checking
                break
        except:
            break
    
    return pages


def categorize_chart(chart_name):
    """Categorize chart based on its name/code"""
    chart_name_upper = chart_name.upper()
    
    # SID charts
    if 'SID' in chart_name_upper:
        return 'SID'
    
    # STAR charts
    if 'STAR' in chart_name_upper:
        return 'STAR'
    
    # Approach charts (IAC = Instrument Approach Chart)
    if any(x in chart_name_upper for x in ['IAC', 'ILS', 'LOC', 'RNP', 'VOR', 'NDB', 'RNAV']):
        return 'Approach'
    
    # Transition charts (treat as approach)
    if 'TRAN' in chart_name_upper:
        return 'Approach'
    
    # Ground charts - use 'airport_diagram' which the CLI maps to GND
    if any(x in chart_name_upper for x in ['ADC', 'GMC', 'APDC', 'PDC', 'AOC', 'PATC']):
        # ADC = Aerodrome Chart
        # GMC = Ground Movement Chart
        # APDC = Aircraft Parking/Docking Chart
        # PDC = Parking/Docking Chart
        # AOC = Aircraft Obstacle Chart
        # PATC = Precision Approach Terrain Chart
        return 'airport_diagram'
    
    return 'General'


def get_aerodrome_charts(icao_code):
    """
    Get all aerodrome charts for a given ICAO code from Netherlands eAIP.
    
    Args:
        icao_code: 4-letter ICAO code (e.g., 'EHAM')
        
    Returns:
        List of dictionaries with 'name', 'url', and 'type' keys
    """
    icao_code = icao_code.upper()
    charts = []
    seen_urls = set()
    
    try:
        # Get the current AIRAC folder
        airac_folder = get_latest_airac_folder()
        base_eaip = f"{BASE_URL}{quote(airac_folder)}/eAIP/"
        
        # Get all airport pages
        pages = get_airport_pages(icao_code, airac_folder)
        
        if not pages:
            print(f"No pages found for {icao_code}")
            return charts
        
        session = get_session()
        
        # Process each page
        for page_url in pages:
            try:
                response = session.get(page_url, timeout=30)
                if response.status_code != 200:
                    continue
                
                html = response.text
                
                # Find all PDF links with chart names
                # Pattern: <span...>CHART_NAME</span>...<a...href=".../{ICAO}-{CHART}.pdf"...>
                # The PDF URL contains the chart type code
                
                pdf_pattern = rf'href="([^"]*/{icao_code}-([^"/]+)\.pdf)"'
                matches = re.findall(pdf_pattern, html, re.IGNORECASE)
                
                for href, chart_code in matches:
                    if href in seen_urls:
                        continue
                    seen_urls.add(href)
                    
                    # Build full URL
                    # href is like ../documents/Root_WePub/Charts/AD/EHAM/EHAM-ADC.pdf
                    full_url = urljoin(page_url, href)
                    
                    # Use chart code as the name
                    chart_name = f"{icao_code} {chart_code}"
                    chart_type = categorize_chart(chart_code)
                    
                    charts.append({
                        'name': chart_name,
                        'url': full_url,
                        'type': chart_type
                    })
                    
            except Exception as e:
                print(f"Error processing {page_url}: {e}")
                continue
        
        return charts
        
    except Exception as e:
        print(f"Error scraping {icao_code}: {e}")
        import traceback
        traceback.print_exc()
        return charts


def main():
    """Main function for standalone testing"""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python netherlands_scraper.py <ICAO_CODE>")
        print("Example: python netherlands_scraper.py EHAM")
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
        
        for chart_type in ['General', 'Airport Diagram', 'SID', 'STAR', 'Approach']:
            if chart_type in by_type:
                print(f"\n{chart_type}: {len(by_type[chart_type])} charts")
                for chart in by_type[chart_type]:
                    print(f"  [{chart['type']}] {chart['name']}")
                    print(f"    {chart['url']}")
    else:
        print("No charts found")


if __name__ == "__main__":
    main()

"""
Venezuela INAC (Instituto Nacional de Aeronáutica Civil) eAIP Scraper
Fetches aerodrome charts from Venezuela's electronic AIP.

URL: https://www.inac.gob.ve/eaip/history-en-GB.html

ICAO Prefix: SV (e.g., SVMI - Maiquetía/Caracas, SVMC - Maracaibo)

Structure:
- History page lists AIRAC versions
- Each version has a frameset with menu
- Menu links to airport pages (SV-AD2.1{ICAO}-en-GB.html)
- Airport pages have BChart iframe with PDF links
- AD 2.24 section has chart names mapped to references
"""

import re
import requests
import urllib3
from typing import List, Dict, Optional
from urllib.parse import urljoin, quote
from bs4 import BeautifulSoup

# Disable SSL warnings for Venezuela site (has certificate issues)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


BASE_URL = "https://www.inac.gob.ve/eaip"

# Known Venezuela airports (SV prefix)
# This list is populated dynamically from the menu
VENEZUELA_AIRPORTS = {}


def get_latest_airac_date(verbose: bool = False) -> Optional[str]:
    """
    Get the latest AIRAC date folder from history page.
    
    Returns:
        Date string like "2023-12-28" or None if not found
    """
    try:
        url = f"{BASE_URL}/history-body-en-GB.html"
        if verbose:
            print(f"[DEBUG] Fetching AIRAC history from {url}")
        
        r = requests.get(url, timeout=30, verify=False)
        r.raise_for_status()
        
        soup = BeautifulSoup(r.content, 'html.parser')
        
        # Find all AIRAC links and get the most recent date
        links = soup.find_all('a', href=True)
        dates = []
        
        for link in links:
            href = link.get('href', '')
            match = re.search(r'(\d{4}-\d{2}-\d{2})', href)
            if match:
                dates.append(match.group(1))
        
        if dates:
            # Sort and get most recent
            dates.sort(reverse=True)
            if verbose:
                print(f"[DEBUG] Found AIRAC dates: {dates[:3]}")
            return dates[0]
        
        return None
        
    except Exception as e:
        if verbose:
            print(f"[DEBUG] Error getting AIRAC date: {e}")
        return None


def get_airport_list(airac_date: str, verbose: bool = False) -> Dict[str, str]:
    """
    Get list of airports from the menu page.
    
    Args:
        airac_date: AIRAC date folder
        verbose: Print debug info
        
    Returns:
        Dictionary mapping ICAO code to airport page URL
    """
    try:
        url = f"{BASE_URL}/{airac_date}/html/eAIP/Menu-en-GB.html"
        if verbose:
            print(f"[DEBUG] Fetching menu from {url}")
        
        r = requests.get(url, timeout=30, verify=False)
        r.raise_for_status()
        
        soup = BeautifulSoup(r.content, 'html.parser')
        
        airports = {}
        links = soup.find_all('a', href=True)
        
        for link in links:
            href = link.get('href', '')
            text = link.get_text(strip=True)
            
            # Look for airport links like "SV-AD2.1SVMI-en-GB.html"
            if 'AD2.1' in href and text.startswith('SV') and len(text) == 4:
                icao = text
                airports[icao] = href
        
        if verbose:
            print(f"[DEBUG] Found {len(airports)} airports")
        
        return airports
        
    except Exception as e:
        if verbose:
            print(f"[DEBUG] Error getting airport list: {e}")
        return {}


def get_pdf_links_from_bchart(airac_date: str, icao_code: str, verbose: bool = False) -> List[str]:
    """
    Get PDF links from the BChart iframe.
    
    Args:
        airac_date: AIRAC date folder
        icao_code: Airport ICAO code
        verbose: Print debug info
        
    Returns:
        List of PDF filenames
    """
    try:
        url = f"{BASE_URL}/{airac_date}/html/eAIP/AD2.1{icao_code}_BChart.html"
        if verbose:
            print(f"[DEBUG] Fetching BChart from {url}")
        
        r = requests.get(url, timeout=30, verify=False)
        
        if r.status_code != 200:
            if verbose:
                print(f"[DEBUG] BChart not found (status {r.status_code})")
            return []
        
        soup = BeautifulSoup(r.content, 'html.parser')
        
        pdf_refs = []
        links = soup.find_all('a', href=True)
        
        for link in links:
            href = link.get('href', '')
            if '.pdf' in href.lower():
                pdf_refs.append(href)
        
        if verbose:
            print(f"[DEBUG] Found {len(pdf_refs)} PDF links")
        
        return pdf_refs
        
    except Exception as e:
        if verbose:
            print(f"[DEBUG] Error getting BChart: {e}")
        return []


def get_chart_names_from_page(airac_date: str, icao_code: str, verbose: bool = False) -> Dict[str, str]:
    """
    Get chart names from the airport page AD 2.24 section.
    
    Args:
        airac_date: AIRAC date folder
        icao_code: Airport ICAO code
        verbose: Print debug info
        
    Returns:
        Dictionary mapping PDF reference (e.g., "AD 2.SVMI-21") to chart name
    """
    try:
        url = f"{BASE_URL}/{airac_date}/html/eAIP/SV-AD2.1{icao_code}-en-GB.html"
        if verbose:
            print(f"[DEBUG] Fetching airport page from {url}")
        
        r = requests.get(url, timeout=30, verify=False)
        r.raise_for_status()
        
        soup = BeautifulSoup(r.content, 'html.parser')
        
        chart_names = {}
        tables = soup.find_all('table')
        
        for table in tables:
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 2:
                    cell_texts = [c.get_text(strip=True) for c in cells]
                    
                    # Look for reference pattern like "AD 2.SVMI-21"
                    for i, text in enumerate(cell_texts):
                        ref_match = re.search(r'AD 2\.' + icao_code + r'-(\d+)', text)
                        if ref_match:
                            ref = ref_match.group(0)  # e.g., "AD 2.SVMI-21"
                            
                            # Get chart name from previous cell
                            name = cell_texts[i-1] if i > 0 else ''
                            
                            if name and len(name) > 3:
                                # Clean up name
                                name = re.sub(r'\s+', ' ', name)
                                chart_names[ref] = name
        
        if verbose:
            print(f"[DEBUG] Found {len(chart_names)} chart names")
        
        return chart_names
        
    except Exception as e:
        if verbose:
            print(f"[DEBUG] Error getting chart names: {e}")
        return {}


def categorize_chart(chart_name: str) -> str:
    """Categorize a chart based on its name."""
    name_upper = chart_name.upper()
    
    # Spanish/English keywords
    if any(x in name_upper for x in ['SID', 'SALIDA', 'DEPARTURE']):
        return 'SID'
    elif any(x in name_upper for x in ['STAR', 'LLEGADA', 'ARRIVAL']):
        return 'STAR'
    elif any(x in name_upper for x in ['ILS', 'LOC', 'VOR', 'NDB', 'RNAV', 'RNP', 'IAC', 'APROXIMACIÓN', 'APROXIMACION', 'APPROACH', 'GNSS']):
        return 'APP'
    elif any(x in name_upper for x in ['VAC', 'VISUAL']):
        return 'APP'
    elif any(x in name_upper for x in ['ADC', 'PLANO DE AERÓDROMO', 'PLANO DE AERODROMO', 'AERODROME CHART', 'APDC', 'PARKING', 'TAXI', 'GROUND']):
        return 'GND'
    elif any(x in name_upper for x in ['OBSTACLE', 'OBSTÁCULO', 'OBSTACULO', 'AOC']):
        return 'GEN'
    else:
        return 'GEN'


def get_aerodrome_charts(icao_code: str, verbose: bool = False) -> List[Dict[str, str]]:
    """
    Get all aerodrome charts for a given ICAO code from Venezuela eAIP.
    
    Args:
        icao_code: 4-letter ICAO code (e.g., SVMI, SVMC)
        verbose: Print debug information
        
    Returns:
        List of dictionaries with 'name', 'url', and 'type' keys
    """
    icao_code = icao_code.upper()
    
    if not icao_code.startswith('SV'):
        print(f"Warning: {icao_code} does not appear to be a Venezuela airport (should start with SV)")
        return []
    
    # Get latest AIRAC date
    print(f"Getting latest AIRAC version...")
    airac_date = get_latest_airac_date(verbose)
    
    if not airac_date:
        print("Could not determine AIRAC date")
        return []
    
    if verbose:
        print(f"[DEBUG] Using AIRAC date: {airac_date}")
    
    # Get PDF links from BChart
    pdf_links = get_pdf_links_from_bchart(airac_date, icao_code, verbose)
    
    if not pdf_links:
        print(f"No chart PDFs found for {icao_code}")
        return []
    
    # Get chart names from airport page
    chart_names = get_chart_names_from_page(airac_date, icao_code, verbose)
    
    # Build result
    charts = []
    base_pdf_url = f"{BASE_URL}/{airac_date}/html/eAIP/"
    
    for pdf_filename in pdf_links:
        # Extract reference from filename (e.g., "AD 2.SVMI-21.pdf" -> "AD 2.SVMI-21")
        ref = pdf_filename.replace('.pdf', '')
        
        # Get chart name if available
        chart_name = chart_names.get(ref, ref)
        
        # Build full URL (encode spaces)
        encoded_filename = quote(pdf_filename, safe='')
        full_url = base_pdf_url + encoded_filename
        
        # Categorize
        chart_type = categorize_chart(chart_name)
        
        charts.append({
            'name': chart_name,
            'url': full_url,
            'type': chart_type
        })
    
    return charts


def main():
    """CLI entry point for testing."""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python venezuela_scraper.py <ICAO_CODE> [-v]")
        print("Example: python venezuela_scraper.py SVMI")
        print("  -v  Verbose output")
        print()
        print("Sample Venezuela airports:")
        print("  SVMI - Simón Bolívar (Maiquetía/Caracas)")
        print("  SVMC - La Chinita (Maracaibo)")
        print("  SVVA - Arturo Michelena (Valencia)")
        print("  SVBC - José Antonio Anzoátegui (Barcelona)")
        print("  SVMG - Alberto Carnevalli (Mérida)")
        sys.exit(1)
    
    icao_code = sys.argv[1].upper()
    verbose = '-v' in sys.argv
    
    print(f"Fetching charts for {icao_code}...")
    
    charts = get_aerodrome_charts(icao_code, verbose=verbose)
    
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
                print(f"  {chart['name'][:60]}")
                print(f"    -> {chart['url']}")
    else:
        print("No charts found")


if __name__ == "__main__":
    main()

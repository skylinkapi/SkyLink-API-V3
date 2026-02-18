"""
Maldives MACL AIP Scraper

Scrapes aerodrome charts from Maldives Airports Company Limited (MACL) AIP.
Each airport has a combined AD 2 document - we extract individual charts by 
parsing the PDF structure.

Main airports: VRMM (Velana/Male), VRMG (Gan), VRMH (Hanimaadhoo)

Source: https://www.macl.aero/corporate/services/operational/ans/aip
"""

import requests
from bs4 import BeautifulSoup
import io
import re

try:
    import PyPDF2
    HAS_PYPDF2 = True
except ImportError:
    HAS_PYPDF2 = False


BASE_URL = "https://www.macl.aero"
AIP_URL = "https://www.macl.aero/corporate/services/operational/ans/aip"
AJAX_URL = "https://www.macl.aero/corporate/services/operational/ans/fillaip"


def categorize_from_text(text: str) -> tuple:
    """
    Categorize chart based on page text content.
    Returns (type, name) tuple.
    """
    text_upper = text[:800].upper()
    first_200 = text[:200].upper()
    
    # Check for AD 2-XX chart numbers in the text
    ad_match = re.search(r'AD\s*2[\s\-\.]+(\d+)', text_upper[:300])
    chart_num = ad_match.group(1) if ad_match else None
    
    # ILS approach
    if 'ILS' in text_upper and ('APPROACH' in text_upper or 'RWY' in text_upper or chart_num):
        match = re.search(r'ILS[^A-Z]*(RWY\s*\d+[LRC]?)', text_upper)
        if match:
            return ('APP', f'ILS {match.group(1)}')
        return ('APP', f'ILS Approach' + (f' (AD 2-{chart_num})' if chart_num else ''))
    
    # VOR approach
    if 'VOR' in text_upper and ('APPROACH' in text_upper or 'DME' in text_upper or chart_num):
        match = re.search(r'VOR[^A-Z]*(RWY\s*\d+[LRC]?)', text_upper)
        if match:
            return ('APP', f'VOR {match.group(1)}')
        return ('APP', f'VOR Approach' + (f' (AD 2-{chart_num})' if chart_num else ''))
    
    # RNP/RNAV approach
    if 'RNP' in text_upper or ('RNAV' in text_upper and 'APPROACH' in text_upper):
        match = re.search(r'RN[AP]V?[^A-Z]*(RWY\s*\d+[LRC]?)', text_upper)
        if match:
            return ('APP', f'RNP {match.group(1)}')
        return ('APP', f'RNP Approach' + (f' (AD 2-{chart_num})' if chart_num else ''))
    
    # NDB approach
    if 'NDB' in text_upper and 'APPROACH' in text_upper:
        return ('APP', 'NDB Approach')
    
    # Visual approach
    if 'VISUAL' in text_upper and 'APPROACH' in text_upper:
        return ('APP', 'Visual Approach')
    
    # SID detection - look for chart numbers in SID range (37-59 typically)
    # or waypoint patterns common in SIDs
    if 'SID' in text_upper or ('STANDARD' in text_upper and 'DEPARTURE' in text_upper):
        match = re.search(r'SID[S]?\s*(RWY\s*\d+[LRC]?)?', text_upper)
        if match and match.group(1):
            return ('SID', f'SID {match.group(1)}')
        return ('SID', f'Standard Departure' + (f' (AD 2-{chart_num})' if chart_num else ''))
    
    # STAR detection
    if 'STAR' in text_upper or ('STANDARD' in text_upper and 'ARRIVAL' in text_upper):
        match = re.search(r'STAR[S]?\s*(RWY\s*\d+[LRC]?)?', text_upper)
        if match and match.group(1):
            return ('STAR', f'STAR {match.group(1)}')
        return ('STAR', f'Standard Arrival' + (f' (AD 2-{chart_num})' if chart_num else ''))
    
    # Detect SID/STAR by chart number range and waypoint patterns
    # SIDs are typically AD 2-37 to AD 2-59, STARs are AD 2-45 to AD 2-55
    waypoint_pattern = re.search(r'\d{2}°\s*\d{2}[\'\"]?\s*\d+["\']?\s*[NS]', text_upper)
    if waypoint_pattern and chart_num:
        num = int(chart_num)
        if 37 <= num <= 44 or 57 <= num <= 59:
            return ('SID', f'SID Chart (AD 2-{chart_num})')
        elif 45 <= num <= 56:
            return ('STAR', f'STAR Chart (AD 2-{chart_num})')
    
    # Aerodrome/Ground charts
    if 'AERODROME CHART' in text_upper or 'AIRPORT CHART' in text_upper:
        return ('GND', 'Aerodrome Chart')
    
    if 'PARKING' in text_upper or 'DOCKING' in text_upper:
        return ('GND', 'Parking/Docking Chart')
    
    if 'TAXI' in text_upper or 'GROUND MOVEMENT' in text_upper:
        return ('GND', 'Ground Movement Chart')
    
    if 'MARKING' in text_upper and ('LIGHTING' in text_upper or 'AIDS' in text_upper):
        return ('GND', 'Marking/Lighting Chart')
    
    # AD chart with coordinates but no specific type - likely aerodrome overview
    if 'AERODROME' in first_200 or ('AD CHART' in text_upper and chart_num):
        return ('GND', f'Aerodrome Chart' + (f' (AD 2-{chart_num})' if chart_num else ''))
    
    # General info pages (AD 2.X sections with text content)
    if 'MALDIVES' in first_200 and 'AD 2' in first_200:
        if chart_num:
            return ('GEN', f'Airport Information (AD 2-{chart_num})')
        return ('GEN', 'Airport Information')
    
    return (None, None)


def extract_charts_from_pdf(pdf_content: bytes, base_url: str, icao_code: str, verbose: bool = False) -> list:
    """
    Extract individual charts from PDF by scanning page content.
    """
    if not HAS_PYPDF2:
        if verbose:
            print("PyPDF2 not installed - returning single PDF link")
        return None
    
    try:
        pdf = PyPDF2.PdfReader(io.BytesIO(pdf_content))
    except Exception as e:
        if verbose:
            print(f"Error reading PDF: {e}")
        return None
    
    charts = []
    seen_names = set()
    
    for i, page in enumerate(pdf.pages):
        try:
            text = page.extract_text()
            if not text:
                continue
            
            chart_type, chart_name = categorize_from_text(text)
            
            if chart_type:
                # Make name unique by adding page number if duplicate
                display_name = f"{icao_code} {chart_name}"
                if display_name in seen_names:
                    display_name = f"{display_name} (Page {i+1})"
                seen_names.add(display_name)
                
                charts.append({
                    'name': display_name,
                    'url': f"{base_url}#page={i+1}",
                    'type': chart_type
                })
                
                if verbose:
                    print(f"  Page {i+1}: {display_name} [{chart_type}]")
        except Exception as e:
            if verbose:
                print(f"  Page {i+1}: Error extracting text - {e}")
    
    return charts if charts else None


def get_aerodrome_charts(icao_code: str, verbose: bool = False) -> list:
    """
    Get aerodrome charts for a Maldives airport.
    
    Args:
        icao_code: ICAO code (e.g., 'VRMM')
        verbose: Enable verbose output
        
    Returns:
        List of chart dictionaries with 'name', 'url', and 'type' keys
    """
    icao_code = icao_code.upper()
    
    if verbose:
        print("Fetching Maldives AIP page...")
    
    session = requests.Session()
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    try:
        response = session.get(AIP_URL, headers=headers, timeout=30)
        response.raise_for_status()
    except requests.RequestException as e:
        if verbose:
            print(f"Error fetching AIP page: {e}")
        return []
    
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Get CSRF token
    csrf_meta = soup.find('meta', {'name': 'csrf-token'})
    if not csrf_meta:
        if verbose:
            print("Could not find CSRF token")
        return []
    csrf_token = csrf_meta.get('content')
    
    # Find the airport in the dataloadlist
    airport_id = None
    airport_name = None
    
    for elem in soup.find_all(class_='dataloadlist'):
        text = elem.get_text(strip=True)
        data_id = elem.get('data-id', '')
        
        # Match by ICAO code at start
        if text.upper().startswith(icao_code) and 'AD 2' in text:
            airport_id = data_id
            airport_name = text
            break
    
    if not airport_id:
        if verbose:
            print(f"Airport {icao_code} not found in Maldives AIP")
        return []
    
    if verbose:
        print(f"Found: {airport_name} (ID: {airport_id})")
    
    # Make AJAX request to get PDF path
    try:
        ajax_response = session.post(
            AJAX_URL,
            data={'_token': csrf_token, 'id': airport_id},
            headers={
                'X-Requested-With': 'XMLHttpRequest',
                'Content-Type': 'application/x-www-form-urlencoded',
                'Referer': AIP_URL,
                **headers
            },
            timeout=30
        )
        ajax_response.raise_for_status()
    except requests.RequestException as e:
        if verbose:
            print(f"Error fetching PDF info: {e}")
        return []
    
    try:
        data = ajax_response.json()
    except ValueError:
        if verbose:
            print("Invalid JSON response")
        return []
    
    file_path = data.get('file_path')
    title = data.get('title', airport_name)
    
    if not file_path:
        if verbose:
            print("No PDF file found for this airport")
        return []
    
    # Construct full URL
    pdf_url = f"{BASE_URL}/{file_path}"
    
    if verbose:
        print(f"PDF URL: {pdf_url}")
    
    # Return single combined AD 2 document
    return [{
        'name': title,
        'url': pdf_url,
        'type': 'GEN'  # Full AD 2 document containing all charts
    }]


def get_all_airports(verbose: bool = False) -> dict:
    """
    Get a dictionary of all available airports.
    
    Returns:
        Dictionary mapping ICAO codes to airport info
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    try:
        response = requests.get(AIP_URL, headers=headers, timeout=30)
        response.raise_for_status()
    except requests.RequestException as e:
        if verbose:
            print(f"Error fetching AIP page: {e}")
        return {}
    
    soup = BeautifulSoup(response.text, 'html.parser')
    airports = {}
    
    for elem in soup.find_all(class_='dataloadlist'):
        text = elem.get_text(strip=True)
        data_id = elem.get('data-id', '')
        
        if text.startswith('VR') and 'AD 2' in text:
            icao = text[:4]
            airports[icao] = {
                'id': data_id,
                'name': text
            }
    
    return airports


# For CLI compatibility
class MaldivesScraper:
    """Class wrapper for CLI compatibility."""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
    
    def get_charts(self, icao_code: str) -> list:
        return get_aerodrome_charts(icao_code, self.verbose)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        icao = sys.argv[1]
        verbose = "--verbose" in sys.argv or "-v" in sys.argv
        
        print(f"Fetching charts for {icao}...")
        charts = get_aerodrome_charts(icao, verbose=verbose)
        
        if charts:
            print(f"\nFound {len(charts)} document:")
            for chart in charts:
                print(f"  [{chart['type']}] {chart['name']}")
                print(f"       {chart['url']}")
        else:
            print("No charts found.")
    else:
        # List all airports
        print("Maldives Airports:")
        airports = get_all_airports(verbose=True)
        for icao, info in sorted(airports.items()):
            print(f"  {icao}: {info['name']}")

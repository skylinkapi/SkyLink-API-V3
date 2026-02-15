"""
Uruguay DINACIA (Dirección Nacional de Aviación Civil e Infraestructura Aeronáutica) Scraper
Fetches aerodrome charts from Uruguay's AIP system.

The Uruguay AIP is accessed via a web-based filter system:
1. The main page has a dropdown with all AIP sections
2. Selecting an aerodrome loads its full AIP PDF
3. We parse the PDF to extract individual chart page references

URL: https://www.dinacia.gub.uy/ais/aip-uruguay

ICAO Prefix: SU (e.g., SUMU - Montevideo/Carrasco, SUAA - Montevideo/Adami)
"""

import os
import sys
import re
import tempfile
import requests
from typing import List, Dict, Optional, Tuple
from urllib.parse import urljoin
from bs4 import BeautifulSoup

# PyMuPDF for PDF parsing
try:
    import fitz  # PyMuPDF
    FITZ_AVAILABLE = True
except ImportError:
    FITZ_AVAILABLE = False


# Uruguay airport database with web filter IDs (English versions)
# ID is the value used in field_indice_aip_target_id parameter
URUGUAY_AIRPORTS = {
    'SUAG': {'id': '769', 'name': 'Artigas International'},
    'SUCM': {'id': '770', 'name': 'Carmelo International'},
    'SUCA': {'id': '771', 'name': 'Colonia/Laguna de los Patos International'},
    'SUDU': {'id': '772', 'name': 'Durazno/Santa Bernardina International'},
    'SULS': {'id': '773', 'name': 'Maldonado/Laguna del Sauce - Punta del Este'},
    'SUMO': {'id': '774', 'name': 'Melo/Cerro Largo International'},
    'SUME': {'id': '775', 'name': 'Mercedes/Ricardo Detomasi'},
    'SUAA': {'id': '776', 'name': 'Montevideo/Ángel S. Adami International'},
    'SUMU': {'id': '777', 'name': 'Montevideo/Carrasco Gral. Cesáreo L. Berisso'},
    'SUPU': {'id': '778', 'name': 'Paysandú/Tydeo Larre Borges International'},
    'SUPE': {'id': '779', 'name': 'Punta del Este/El Jaguel'},
    'SURB': {'id': '780', 'name': 'Río Branco'},
    'SURV': {'id': '781', 'name': 'Rivera/Oscar D. Gestido International'},
    'SUSO': {'id': '782', 'name': 'Salto/Nueva Hespérides International'},
    'SUTB': {'id': '783', 'name': 'Tacuarembó'},
    'SUTR': {'id': '784', 'name': 'Treinta y Tres'},
    'SUVO': {'id': '785', 'name': 'Vichadero'},
}


def get_pdf_url(icao_code: str, verbose: bool = False) -> Optional[str]:
    """
    Get the PDF URL for an airport by making a web request with the filter parameter.
    
    Args:
        icao_code: ICAO code of the airport
        verbose: Print debug info
        
    Returns:
        Full PDF URL or None if not found
    """
    icao_code = icao_code.upper()
    
    if icao_code not in URUGUAY_AIRPORTS:
        if verbose:
            print(f"[DEBUG] {icao_code} not in known Uruguay airports")
        return None
    
    filter_id = URUGUAY_AIRPORTS[icao_code]['id']
    base_url = 'https://www.dinacia.gub.uy'
    page_url = f'{base_url}/ais/aip-uruguay'
    
    if verbose:
        print(f"[DEBUG] Fetching page with filter_id={filter_id}")
    
    try:
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml',
            'Accept-Language': 'en-US,en;q=0.9',
        })
        
        response = session.get(page_url, params={'field_indice_aip_target_id': filter_id}, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find PDF links
        for link in soup.find_all('a', href=True):
            href = link.get('href', '')
            if '.pdf' in href.lower():
                pdf_url = urljoin(base_url, href)
                if verbose:
                    print(f"[DEBUG] Found PDF URL: {pdf_url}")
                return pdf_url
        
        if verbose:
            print("[DEBUG] No PDF link found on page")
        return None
        
    except Exception as e:
        if verbose:
            print(f"[DEBUG] Error getting PDF URL: {e}")
        return None


def download_pdf(pdf_url: str, cache_file: str, verbose: bool = False) -> bool:
    """
    Download a PDF file to a local cache.
    
    Args:
        pdf_url: URL of the PDF
        cache_file: Local path to save the PDF
        verbose: Print debug info
        
    Returns:
        True if download successful, False otherwise
    """
    try:
        os.makedirs(os.path.dirname(cache_file), exist_ok=True)
        
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        })
        
        if verbose:
            print(f"[DEBUG] Downloading from {pdf_url}")
        
        response = session.get(pdf_url, timeout=120, stream=True)
        response.raise_for_status()
        
        # Check content type
        content_type = response.headers.get('Content-Type', '')
        if 'pdf' not in content_type.lower():
            if verbose:
                print(f"[DEBUG] Unexpected content type: {content_type}")
            # Continue anyway, might still be a PDF
        
        # Stream download
        total_size = 0
        with open(cache_file, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    total_size += len(chunk)
        
        if verbose:
            print(f"[DEBUG] Downloaded {total_size / 1024 / 1024:.1f} MB")
        
        # Verify it's a valid PDF
        with open(cache_file, 'rb') as f:
            header = f.read(8)
            if not header.startswith(b'%PDF'):
                if verbose:
                    print(f"[DEBUG] File doesn't start with PDF header: {header[:20]}")
                os.remove(cache_file)
                return False
        
        return True
        
    except Exception as e:
        if verbose:
            print(f"[DEBUG] Download error: {e}")
        if os.path.exists(cache_file):
            os.remove(cache_file)
        return False


def find_chart_list_page(doc, icao_code: str, verbose: bool = False) -> Optional[int]:
    """
    Find the page number containing the chart list (AD 2.24 - Charts related to an aerodrome).
    
    Args:
        doc: PyMuPDF document object
        icao_code: ICAO code to look for
        verbose: Print debug info
        
    Returns:
        0-indexed page number or None if not found
    """
    # Look for "CHARTS RELATED TO AN AERODROME" text
    for page_num in range(min(len(doc), 40)):  # Charts list is usually in first 40 pages
        page = doc[page_num]
        text = page.get_text()
        
        # Look for chart list section header
        if 'CHARTS RELATED TO AN AERODROME' in text.upper() or 'AD 2.24' in text:
            # Verify it mentions the airport
            if icao_code in text:
                if verbose:
                    print(f"[DEBUG] Found chart list on page {page_num + 1}")
                return page_num
    
    return None


def parse_chart_list_from_page(doc, chart_list_page: int, icao_code: str, verbose: bool = False) -> List[Dict]:
    """
    Parse the chart list from the AD 2.24 section.
    
    Uruguay AIP format: "Chart Name .... AD 2.X-NN" where NN is the page number.
    
    Args:
        doc: PyMuPDF document object
        chart_list_page: Page number containing the chart list
        icao_code: ICAO code
        verbose: Print debug info
        
    Returns:
        List of chart dictionaries with name, page, and type
    """
    charts = []
    page = doc[chart_list_page]
    text = page.get_text()
    
    if verbose:
        print(f"[DEBUG] Parsing chart list from page {chart_list_page + 1}")
    
    lines = text.split('\n')
    
    # Pattern to match chart entries like:
    # "Aerodrome/Heliport Chart – ICAO RWY 01/19 ... AD 2.9-27" or "... AD 2.9.59"
    # The page reference is "AD 2.X-NN" or "AD 2.X.NN" where NN is the actual PDF page
    chart_pattern = re.compile(r'(.+?)\s*\.{2,}\s*AD\s*2\.\d+[-.](\d+)', re.IGNORECASE)
    
    for line in lines:
        line = line.strip()
        if not line or len(line) < 10:
            continue
        
        # Skip headers and footers
        if 'AIRAC' in line or 'AIS URUGUAY' in line or 'AIP' == line:
            continue
        
        match = chart_pattern.search(line)
        if match:
            chart_name = match.group(1).strip()
            page_ref = int(match.group(2))
            
            # Clean up chart name - remove problematic unicode and normalize
            chart_name = re.sub(r'\s+', ' ', chart_name)  # Normalize whitespace
            chart_name = chart_name.replace('–', '-').replace('—', '-')  # Normalize dashes
            chart_name = ''.join(c for c in chart_name if ord(c) < 65536 and c.isprintable() or c == ' ')  # Remove non-printable
            chart_name = chart_name.strip()
            
            if not chart_name or len(chart_name) < 5:
                continue
            
            chart_type = categorize_chart(chart_name)
            
            charts.append({
                'name': chart_name,
                'page': page_ref,  # This is the actual PDF page number
                'type': chart_type
            })
            
            if verbose:
                try:
                    print(f"[DEBUG] Found: {chart_name} -> Page {page_ref} ({chart_type})")
                except UnicodeEncodeError:
                    print(f"[DEBUG] Found: {chart_name.encode('ascii', 'ignore').decode()} -> Page {page_ref} ({chart_type})")
    
    return charts


def categorize_chart(chart_name: str) -> str:
    """Categorize a chart based on its name."""
    name_upper = chart_name.upper()
    
    if any(x in name_upper for x in ['SID', 'DEPARTURE', 'SALIDA']):
        return 'SID'
    elif any(x in name_upper for x in ['STAR', 'ARRIVAL', 'LLEGADA']):
        return 'STAR'
    elif any(x in name_upper for x in ['ILS', 'LOC', 'VOR', 'NDB', 'RNAV', 'RNP', 'IAC', 'APPROACH', 'APROXIMACION', 'INSTRUMENT APPROACH']):
        return 'APP'
    elif any(x in name_upper for x in ['ADC', 'APDC', 'PARKING', 'DOCKING', 'TAXI', 'GROUND MOVEMENT', 'AERODROME/HELIPORT', 'HELIPORT CHART']):
        return 'GND'
    elif any(x in name_upper for x in ['AOC', 'OBSTACLE']):
        return 'GEN'
    else:
        return 'GEN'


def find_chart_pages_in_pdf(doc, icao_code: str, verbose: bool = False) -> List[Dict]:
    """
    Scan through the PDF to find actual chart pages.
    
    This searches for pages containing chart graphics for the specified airport.
    
    Args:
        doc: PyMuPDF document object
        icao_code: ICAO code
        verbose: Print debug info
        
    Returns:
        List of chart dictionaries with name, page number, and type
    """
    charts = []
    seen_names = set()
    
    # Chart type indicators that appear on chart pages
    chart_indicators = [
        ('ADC', 'Aerodrome Chart', 'GND'),
        ('APDC', 'Aircraft Parking/Docking Chart', 'GND'),
        ('AOC', 'Aerodrome Obstacle Chart', 'GND'),
        ('GMC', 'Ground Movement Chart', 'GND'),
        ('SID', 'Standard Instrument Departure', 'SID'),
        ('STAR', 'Standard Arrival', 'STAR'),
        ('IAC', 'Instrument Approach Chart', 'APP'),
        ('ILS', 'ILS Approach', 'APP'),
        ('LOC', 'LOC Approach', 'APP'),
        ('VOR', 'VOR Approach', 'APP'),
        ('NDB', 'NDB Approach', 'APP'),
        ('RNAV', 'RNAV Approach', 'APP'),
        ('RNP', 'RNP Approach', 'APP'),
        ('VAC', 'Visual Approach Chart', 'APP'),
        ('TAA', 'Terminal Arrival Altitude', 'APP'),
    ]
    
    if verbose:
        print(f"[DEBUG] Scanning {len(doc)} pages for charts...")
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text()
        
        # Skip if page doesn't mention the airport
        if icao_code not in text:
            continue
        
        # Look for chart type indicators
        for short_name, long_name, chart_type in chart_indicators:
            # Check if this is a chart page (contains the indicator prominently)
            # Chart pages usually have the type name in a header
            lines = text.split('\n')[:15]  # Check first 15 lines
            header_text = ' '.join(lines)
            
            if short_name in header_text or long_name.upper() in header_text.upper():
                # Extract a meaningful chart name
                chart_name = None
                
                # Try to find the full chart title
                for line in lines:
                    line = line.strip()
                    if icao_code in line and len(line) > 10:
                        # Clean up the line
                        if any(x in line for x in [short_name, long_name]):
                            chart_name = line
                            break
                
                if not chart_name:
                    # Construct a name from what we found
                    chart_name = f"{icao_code} {short_name}"
                    # Try to find runway or additional info
                    for line in lines:
                        if 'RWY' in line.upper() or 'RUNWAY' in line.upper():
                            rwy_match = re.search(r'RWY?\s*(\d{2}[LRC]?)', line, re.IGNORECASE)
                            if rwy_match:
                                chart_name = f"{icao_code} {short_name} RWY {rwy_match.group(1)}"
                                break
                
                # Avoid duplicates
                if chart_name not in seen_names:
                    seen_names.add(chart_name)
                    charts.append({
                        'name': chart_name,
                        'page': page_num + 1,  # 1-indexed
                        'type': chart_type
                    })
                    if verbose:
                        print(f"[DEBUG] Found chart on page {page_num + 1}: {chart_name}")
                break
    
    return charts


def get_aerodrome_charts(icao_code: str, extract_pdfs: bool = False, verbose: bool = False) -> List[Dict[str, str]]:
    """
    Get all aerodrome charts for a given ICAO code from Uruguay AIP.
    
    Args:
        icao_code: 4-letter ICAO code (e.g., SUMU, SUAA)
        extract_pdfs: If True, extract individual chart PDFs locally.
                     If False, return online URL with page references.
        verbose: Print debug information
        
    Returns:
        List of dictionaries with 'name', 'url', and 'type' keys
    """
    icao_code = icao_code.upper()
    
    if not icao_code.startswith('SU'):
        print(f"Warning: {icao_code} does not appear to be a Uruguay airport (should start with SU)")
        return []
    
    if icao_code not in URUGUAY_AIRPORTS:
        print(f"Error: {icao_code} is not in the known Uruguay airport list.")
        print("Known airports:", ', '.join(sorted(URUGUAY_AIRPORTS.keys())))
        return []
    
    if not FITZ_AVAILABLE:
        raise ImportError("PyMuPDF is required for Uruguay charts. Install with: pip install pymupdf")
    
    # Get the PDF URL
    print(f"Getting PDF URL for {icao_code}...")
    pdf_url = get_pdf_url(icao_code, verbose)
    
    if not pdf_url:
        print(f"Could not find PDF URL for {icao_code}")
        return []
    
    # Set up cache path
    cache_dir = os.path.join(tempfile.gettempdir(), "uruguay_aip")
    cache_file = os.path.join(cache_dir, f"{icao_code}.pdf")
    url_cache_file = os.path.join(cache_dir, f"{icao_code}_url.txt")
    
    # Check if we need to download
    need_download = True
    if os.path.exists(cache_file) and os.path.exists(url_cache_file):
        try:
            from datetime import datetime
            file_age = (datetime.now().timestamp() - os.path.getmtime(cache_file)) / 3600 / 24
            
            # Check if URL has changed
            with open(url_cache_file, 'r') as f:
                cached_url = f.read().strip()
            
            with open(cache_file, 'rb') as f:
                if f.read(4) == b'%PDF' and file_age < 7 and cached_url == pdf_url:
                    need_download = False
                    if verbose:
                        print(f"[DEBUG] Using cached PDF (age: {file_age:.1f} days)")
        except:
            need_download = True
    
    if need_download:
        print(f"Downloading Uruguay AIP PDF for {icao_code}...")
        
        if not download_pdf(pdf_url, cache_file, verbose):
            print(f"Failed to download PDF for {icao_code}")
            return []
        
        # Cache the URL
        os.makedirs(cache_dir, exist_ok=True)
        with open(url_cache_file, 'w') as f:
            f.write(pdf_url)
    
    # Open and process the PDF
    try:
        doc = fitz.open(cache_file)
        if verbose:
            print(f"[DEBUG] PDF has {len(doc)} pages")
        
        # Find the chart list page
        chart_list_page = find_chart_list_page(doc, icao_code, verbose)
        
        if chart_list_page is None:
            if verbose:
                print("[DEBUG] Could not find chart list page, falling back to page scanning")
            charts_info = find_chart_pages_in_pdf(doc, icao_code, verbose)
        else:
            # Parse chart list from the dedicated page
            charts_info = parse_chart_list_from_page(doc, chart_list_page, icao_code, verbose)
        
        if not charts_info:
            print(f"No charts found in PDF for {icao_code}")
            doc.close()
            return []
        
        if verbose:
            print(f"[DEBUG] Found {len(charts_info)} charts")
        
        # Build result
        charts = []
        output_dir = os.path.join(os.getcwd(), "output", "uruguay", icao_code)
        
        for chart_info in charts_info:
            chart_name = chart_info['name']
            chart_type = chart_info['type']
            pdf_page = chart_info['page']
            
            if extract_pdfs:
                try:
                    # Extract single page as PDF
                    os.makedirs(output_dir, exist_ok=True)
                    safe_name = re.sub(r'[<>:"/\\|?*]', '_', chart_name)
                    output_path = os.path.join(output_dir, f"{safe_name}.pdf")
                    
                    new_doc = fitz.open()
                    new_doc.insert_pdf(doc, from_page=pdf_page - 1, to_page=pdf_page - 1)
                    new_doc.save(output_path)
                    new_doc.close()
                    
                    chart_url = f"file:///{os.path.abspath(output_path).replace(os.sep, '/')}"
                except Exception as e:
                    if verbose:
                        print(f"[DEBUG] Failed to extract {chart_name}: {e}")
                    chart_url = f"{pdf_url}#page={pdf_page}"
            else:
                # Use online PDF URL with page reference
                chart_url = f"{pdf_url}#page={pdf_page}"
            
            charts.append({
                'name': chart_name,
                'url': chart_url,
                'type': chart_type,
                'page': pdf_page
            })
        
        doc.close()
        return charts
        
    except Exception as e:
        print(f"Error processing PDF: {e}")
        if verbose:
            import traceback
            traceback.print_exc()
        return []


def main():
    """CLI entry point for testing."""
    if len(sys.argv) < 2:
        print("Usage: python uruguay_scraper.py <ICAO_CODE> [-e] [-v]")
        print("Example: python uruguay_scraper.py SUMU")
        print("  -e  Extract individual PDFs locally (default: page references)")
        print("  -v  Verbose output")
        print()
        print("Known Uruguay airports:")
        for icao, info in sorted(URUGUAY_AIRPORTS.items()):
            print(f"  {icao}: {info['name']}")
        sys.exit(1)
    
    icao_code = sys.argv[1].upper()
    extract_pdfs = '-e' in sys.argv
    verbose = '-v' in sys.argv
    
    print(f"Fetching charts for {icao_code}...")
    if icao_code in URUGUAY_AIRPORTS:
        print(f"Airport: {URUGUAY_AIRPORTS[icao_code]['name']}")
    
    charts = get_aerodrome_charts(icao_code, extract_pdfs=extract_pdfs, verbose=verbose)
    
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
                page = chart.get('page', '?')
                print(f"  [Page {page}] {chart['name']}")
    else:
        print("No charts found")


if __name__ == "__main__":
    main()

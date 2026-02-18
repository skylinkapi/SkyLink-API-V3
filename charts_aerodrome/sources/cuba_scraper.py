"""
Cuba AIP Scraper
Scrapes aerodrome charts from Cuba Civil Aviation AIP PDF

URL Patterns (try in order):
1. https://aismet.avianet.cu/assets/data/pdf/AIP/{ICAO}AD_2.pdf
2. https://aismet.avianet.cu/assets/data/pdf/AIP/{ICAO}_AD_2.pdf
3. https://aismet.avianet.cu/assets/data/pdf/AIP/{ICAO}.pdf

Structure:
- Single PDF per airport containing all aerodrome data and charts
- Chart list in AD 2.24 section with format "AD 2 {ICAO} X - Y" 
- ICAO prefix: MU*

Examples: MUHA (José Martí, Havana), MUCU (Antonio Maceo, Santiago)

Chart extraction approach (similar to Canada/Djibouti):
1. Download the airport's AIP PDF
2. Parse AD 2.24 section to get chart list
3. Map section references to actual PDF page numbers
4. Either return page references or extract individual pages as separate PDFs
"""

import os
import re
import sys
import tempfile
from typing import List, Dict, Optional, Tuple
from urllib.parse import quote

try:
    import fitz  # PyMuPDF
    FITZ_AVAILABLE = True
except ImportError:
    FITZ_AVAILABLE = False

import requests


# URL patterns to try (in order)
URL_PATTERNS = [
    "https://aismet.avianet.cu/assets/data/pdf/AIP/{icao}AD_2.pdf",
    "https://aismet.avianet.cu/assets/data/pdf/AIP/{icao}_AD_2.pdf",
    "https://aismet.avianet.cu/assets/data/pdf/AIP/{icao}.pdf",
]

# Known Cuba airports
CUBA_AIRPORTS = {
    "MUHA": "José Martí International Airport (Havana)",
    "MUCU": "Antonio Maceo International Airport (Santiago de Cuba)",
    "MUVR": "Juan Gualberto Gómez Airport (Varadero)",
    "MUCC": "Jardines del Rey Airport (Cayo Coco)",
    "MUCF": "Jaime González Airport (Cienfuegos)",
    "MUCM": "Ignacio Agramonte Airport (Camagüey)",
    "MUSC": "Abel Santamaría Airport (Santa Clara)",
    "MUHG": "Frank País Airport (Holguín)",
    "MUNG": "Sierra Maestra Airport (Manzanillo)",
    "MUCA": "Máximo Gómez Airport (Ciego de Ávila)",
    "MUSS": "Sancti Spíritus Airport",
    "MUBR": "Baracoa Airport",
    "MUGM": "Mariana Grajales Airport (Guantánamo)",
    "MUMO": "Orestes Acosta Airport (Moa)",
    "MULM": "La Coloma Airport",
    "MUNC": "Nicaro Airport",
    "MUVT": "Hermanos Ameijeiras Airport (Las Tunas)",
    "MUPB": "Pinar del Río Airport",
    "MUBY": "Carlos Manuel de Céspedes Airport (Bayamo)",
    "MUNB": "Nueva Gerona Airport (Isla de la Juventud)",
}


def download_pdf(icao_code: str, cache_path: str, verbose: bool = False) -> Optional[str]:
    """
    Download the AIP PDF trying different URL patterns.
    
    Args:
        icao_code: ICAO airport code
        cache_path: Local path to save the PDF
        verbose: Print debug info
        
    Returns:
        str: The working URL if download successful, None otherwise
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/pdf,*/*',
    }
    
    # Suppress SSL warnings
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    for pattern in URL_PATTERNS:
        url = pattern.format(icao=icao_code)
        if verbose:
            print(f"[DEBUG] Trying: {url}")
        
        try:
            # Stream download to handle large files
            response = requests.get(url, headers=headers, timeout=180, verify=False, stream=True)
            
            if response.status_code != 200:
                continue
            
            # Check content type or first bytes
            content_type = response.headers.get('Content-Type', '')
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(cache_path), exist_ok=True)
            
            # Stream to file
            total_size = 0
            with open(cache_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        total_size += len(chunk)
            
            # Verify it's a PDF
            with open(cache_path, 'rb') as f:
                header = f.read(4)
                if header != b'%PDF':
                    if verbose:
                        print(f"[DEBUG] Not a PDF (got HTML redirect)")
                    os.remove(cache_path)
                    continue
            
            if verbose:
                print(f"[DEBUG] Downloaded {total_size/1024/1024:.1f} MB from {url}")
            
            # Return the working URL
            return url
            
        except requests.exceptions.Timeout:
            if verbose:
                print(f"[DEBUG] Timeout for {url}")
            continue
        except Exception as e:
            if verbose:
                print(f"[DEBUG] Error with {url}: {e}")
            continue
    
    return None


def find_chart_list_page(doc, icao_code: str) -> Optional[int]:
    """
    Find the page containing the AD 2.24 chart list.
    
    Returns:
        0-indexed page number or None
    """
    for i in range(min(30, len(doc))):  # Charts list is usually in first 30 pages
        text = doc[i].get_text()
        # Look for chart list - has "Charts" header and .pdf entries
        if 'Charts' in text and '.pdf' in text and icao_code in text:
            return i
    return None


def parse_chart_list(doc, chart_list_page: int, icao_code: str, verbose: bool = False) -> List[Dict]:
    """
    Parse the chart list from AD 2.24 section.
    
    Returns:
        List of dicts with chart info: name, section_ref, type
    """
    charts = []
    text = doc[chart_list_page].get_text()
    
    # Pattern: "AD 2 MUHA ADC.pdf" followed by "AD 2 MUHA 2 - 1"
    # Chart name is like "ADC", "APDC 1", "SID CCO RWY06", etc.
    lines = text.split('\n')
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # Look for .pdf entries
        if '.pdf' in line.lower() and icao_code in line:
            # Extract chart name from filename
            # e.g., "AD 2 MUHA ADC.pdf" -> "ADC"
            # e.g., "AD 2 MUHA SID CCO RWY06.pdf" -> "SID CCO RWY06"
            match = re.search(rf'AD\s*2\s*{icao_code}\s+(.+?)\.pdf', line, re.IGNORECASE)
            if match:
                chart_name = match.group(1).strip()
                
                # Next line should have the page reference
                if i + 1 < len(lines):
                    ref_line = lines[i + 1].strip()
                    # e.g., "AD 2 MUHA 2 - 1" means section 2, page 1
                    ref_match = re.search(rf'AD\s*2\s*{icao_code}\s+(\d+)\s*-\s*(\d+)', ref_line, re.IGNORECASE)
                    if ref_match:
                        section = int(ref_match.group(1))
                        page_in_section = int(ref_match.group(2))
                        
                        chart_type = categorize_chart(chart_name)
                        
                        charts.append({
                            'name': f"{icao_code} {chart_name}",
                            'section': section,
                            'page_in_section': page_in_section,
                            'section_ref': f"AD 2 {icao_code} {section} - {page_in_section}",
                            'type': chart_type
                        })
                        
                        if verbose:
                            print(f"[DEBUG] Found chart: {chart_name} -> Section {section}, Page {page_in_section}")
        i += 1
    
    return charts


def map_section_to_pdf_page(doc, icao_code: str, section: int, page_in_section: int, chart_list_page: int) -> Optional[int]:
    """
    Map a section reference like "AD 2 MUHA 5 - 3" to actual PDF page number.
    
    Searches for the page containing that section header, skipping the chart list page.
    
    Returns:
        0-indexed PDF page number or None
    """
    target_pattern = rf'AD\s*2\s*{icao_code}\s+{section}\s*-\s*{page_in_section}'
    
    for i in range(len(doc)):
        # Skip the chart list page (it contains all references)
        if i == chart_list_page:
            continue
        
        text = doc[i].get_text()
        if re.search(target_pattern, text, re.IGNORECASE):
            return i
    
    return None


def categorize_chart(chart_name: str) -> str:
    """
    Categorize chart based on its name.
    """
    name_upper = chart_name.upper()
    
    # SID
    if 'SID' in name_upper:
        return 'SID'
    
    # STAR
    if 'STAR' in name_upper:
        return 'STAR'
    
    # Approach charts
    if any(kw in name_upper for kw in ['ILS', 'LOC', 'RNP', 'VOR', 'NDB', 'RNAV', 'IAC']):
        return 'Approach'
    
    # Visual approach
    if 'VAC' in name_upper or 'VISUAL' in name_upper:
        return 'Approach'
    
    # Airport diagrams - ADC (Aerodrome Chart), APDC (Aircraft Parking/Docking Chart), GMC
    if any(kw in name_upper for kw in ['ADC', 'APDC', 'PARKING', 'GMC', 'DOCKING']):
        return 'Airport Diagram'
    
    # Area/obstacle charts - General category
    if any(kw in name_upper for kw in ['AOC', 'ARC', 'TMA', 'RMAC', 'BIRD', 'AVES', 'CONCENT']):
        return 'General'
    
    return 'General'


def extract_chart_page(doc, page_num: int, icao_code: str, chart_name: str, output_dir: str) -> str:
    """
    Extract a single page as a separate PDF.
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # Sanitize filename
    safe_name = re.sub(r'[<>:"/\\|?*\s]+', '_', chart_name)
    safe_name = safe_name[:60]
    pdf_filename = f"{safe_name}.pdf"
    pdf_path = os.path.join(output_dir, pdf_filename)
    
    # Create new PDF with single page
    new_doc = fitz.open()
    new_doc.insert_pdf(doc, from_page=page_num, to_page=page_num)
    new_doc.save(pdf_path)
    new_doc.close()
    
    return pdf_path


def get_aerodrome_charts(icao_code: str, extract_pdfs: bool = False, verbose: bool = False) -> List[Dict[str, str]]:
    """
    Get all aerodrome charts for a given ICAO code from Cuba AIP.
    
    Args:
        icao_code: 4-letter ICAO code (e.g., MUHA, MUCU)
        extract_pdfs: If True, extract individual chart PDFs locally.
                     If False, return online URL with page references.
        verbose: Print debug information
        
    Returns:
        List of dictionaries with 'name', 'url', and 'type' keys
    """
    icao_code = icao_code.upper()
    
    if not icao_code.startswith('MU'):
        print(f"Warning: {icao_code} does not appear to be a Cuba airport (should start with MU)")
        return []
    
    if not FITZ_AVAILABLE:
        raise ImportError("PyMuPDF is required for Cuba charts. Install with: pip install pymupdf")
    
    # Set up cache path
    cache_dir = os.path.join(tempfile.gettempdir(), "cuba_aip")
    cache_file = os.path.join(cache_dir, f"{icao_code}_AD_2.pdf")
    url_cache_file = os.path.join(cache_dir, f"{icao_code}_url.txt")
    
    # Track the working online URL
    online_pdf_url = None
    
    # Check if we need to download
    need_download = True
    if os.path.exists(cache_file) and os.path.exists(url_cache_file):
        try:
            from datetime import datetime
            file_age = (datetime.now().timestamp() - os.path.getmtime(cache_file)) / 3600 / 24
            
            with open(cache_file, 'rb') as f:
                if f.read(4) == b'%PDF' and file_age < 7:
                    # Read cached URL
                    with open(url_cache_file, 'r') as uf:
                        online_pdf_url = uf.read().strip()
                    need_download = False
                    if verbose:
                        print(f"[DEBUG] Using cached PDF (age: {file_age:.1f} days)")
        except:
            need_download = True
    
    if need_download:
        print(f"Downloading Cuba AIP PDF for {icao_code}...")
        
        online_pdf_url = download_pdf(icao_code, cache_file, verbose)
        if not online_pdf_url:
            print(f"Failed to download PDF for {icao_code}")
            print("The airport may not have an available AIP document.")
            return []
        
        # Cache the working URL
        os.makedirs(cache_dir, exist_ok=True)
        with open(url_cache_file, 'w') as f:
            f.write(online_pdf_url)
    
    # Open and process the PDF
    try:
        doc = fitz.open(cache_file)
        if verbose:
            print(f"[DEBUG] PDF has {len(doc)} pages")
        
        # Find chart list page
        chart_list_page = find_chart_list_page(doc, icao_code)
        
        if chart_list_page is None:
            if verbose:
                print("[DEBUG] Could not find chart list page")
            doc.close()
            return []
        
        if verbose:
            print(f"[DEBUG] Chart list found on page {chart_list_page + 1}")
        
        # Parse chart list
        charts_info = parse_chart_list(doc, chart_list_page, icao_code, verbose)
        
        if not charts_info:
            print(f"No charts found in PDF for {icao_code}")
            doc.close()
            return []
        
        if verbose:
            print(f"[DEBUG] Found {len(charts_info)} charts in list")
        
        # Map section references to actual PDF pages and build result
        charts = []
        output_dir = os.path.join(os.getcwd(), "output", "cuba", icao_code)
        
        for chart_def in charts_info:
            # Find the actual PDF page for this chart
            pdf_page = map_section_to_pdf_page(
                doc, icao_code, 
                chart_def['section'], 
                chart_def['page_in_section'],
                chart_list_page
            )
            
            if pdf_page is None:
                if verbose:
                    print(f"[DEBUG] Could not find page for {chart_def['name']}")
                continue
            
            chart_name = chart_def['name']
            chart_type = chart_def['type']
            
            if extract_pdfs:
                try:
                    pdf_path = extract_chart_page(doc, pdf_page, icao_code, chart_name, output_dir)
                    chart_url = f"file:///{os.path.abspath(pdf_path).replace(os.sep, '/')}"
                except Exception as e:
                    if verbose:
                        print(f"[DEBUG] Failed to extract {chart_name}: {e}")
                    chart_url = f"file:///{os.path.abspath(cache_file).replace(os.sep, '/')}#page={pdf_page + 1}"
            else:
                # Use online PDF URL with page reference
                chart_url = f"{online_pdf_url}#page={pdf_page + 1}"
            
            charts.append({
                'name': chart_name,
                'url': chart_url,
                'type': chart_type,
                'page': pdf_page + 1
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
        print("Usage: python cuba_scraper.py <ICAO_CODE> [-e] [-v]")
        print("Example: python cuba_scraper.py MUHA")
        print("  -e  Extract individual PDFs locally (default: page references)")
        print("  -v  Verbose output")
        print()
        print("Known Cuba airports:")
        for icao, name in sorted(CUBA_AIRPORTS.items()):
            print(f"  {icao}: {name}")
        sys.exit(1)
    
    icao_code = sys.argv[1].upper()
    extract_pdfs = '-e' in sys.argv
    verbose = '-v' in sys.argv
    
    print(f"Fetching charts for {icao_code}...")
    if icao_code in CUBA_AIRPORTS:
        print(f"Airport: {CUBA_AIRPORTS[icao_code]}")
    
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

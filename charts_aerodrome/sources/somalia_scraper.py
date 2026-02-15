"""
Somalia AIP Scraper
Scrapes aerodrome charts from ICAO FISS Somalia AIP PDF

Source: https://www2023.icao.int/ESAF/FISS/Pages/Aeronautical-Information-Publication.aspx
Structure:
- Single PDF containing all aerodromes (Part 3 - Aerodromes)
- Each airport section contains AD 2 data followed by charts
- ICAO prefix: HC*

Airports in Somalia AIP:
- HCGR: Galcaio
- HCMF: Bosaso  
- HCMH: Hargeisa/Egal International
- HCMI: Berbera
- HCMK: Kismayo
- HCMM: Mogadishu/Aden Adde International
- HCMV: Baidoa

Chart extraction approach (similar to Canada/Djibouti):
1. Download the Aerodromes PDF from ICAO FISS
2. Parse TOC to find airport sections
3. Identify chart pages within each airport section
4. Extract individual pages as separate PDFs
"""

import os
import re
import sys
import tempfile
from typing import List, Dict, Optional
from urllib.parse import urljoin

try:
    import fitz  # PyMuPDF
    FITZ_AVAILABLE = True
except ImportError:
    FITZ_AVAILABLE = False

try:
    import urllib.request
    import ssl
except ImportError:
    pass


# Base URLs
AIP_PAGE_URL = "https://www2023.icao.int/ESAF/FISS/Pages/Aeronautical-Information-Publication.aspx"
PDF_URL = "https://www2023.icao.int/ESAF/FISS/Documents/Docs%2016.04.2019/AIP%20SOMALIA%20PART%203%20AERODROMES.pdf"


# Airport information from TOC (page numbers are 1-indexed)
AIRPORTS = {
    'HCGR': {'name': 'Galcaio', 'start_page': 14, 'end_page': 15},
    'HCMF': {'name': 'Bosaso', 'start_page': 16, 'end_page': 21},
    'HCMH': {'name': 'Hargeisa/Egal International', 'start_page': 22, 'end_page': 34},
    'HCMI': {'name': 'Berbera', 'start_page': 35, 'end_page': 38},
    'HCMK': {'name': 'Kismayo', 'start_page': 39, 'end_page': 40},
    'HCMM': {'name': 'Mogadishu/Aden Adde International', 'start_page': 41, 'end_page': 65},
    'HCMV': {'name': 'Baidoa', 'start_page': 66, 'end_page': 67},
}


def download_pdf(cache_path: str) -> bool:
    """
    Download the Somalia AIP Aerodromes PDF.
    
    Args:
        cache_path: Local path to save the PDF
        
    Returns:
        bool: True if download successful
    """
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        req = urllib.request.Request(PDF_URL, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        with urllib.request.urlopen(req, context=ctx, timeout=120) as response:
            pdf_data = response.read()
            
            os.makedirs(os.path.dirname(cache_path), exist_ok=True)
            
            with open(cache_path, 'wb') as f:
                f.write(pdf_data)
            
            return True
            
    except Exception as e:
        print(f"Error downloading PDF: {e}")
        return False


def categorize_chart(chart_name: str) -> str:
    """
    Categorize chart based on its name.
    
    Args:
        chart_name: Name/description of the chart
        
    Returns:
        Category string
    """
    name_upper = chart_name.upper()
    
    # SID
    if 'SID' in name_upper or 'DEPARTURE' in name_upper:
        return 'SID'
    
    # STAR
    if 'STAR' in name_upper or 'ARRIVAL' in name_upper:
        return 'STAR'
    
    # Approach charts
    if any(keyword in name_upper for keyword in [
        'APPROACH', 'IAC', 'RNAV', 'RNP', 'ILS', 'VOR', 'NDB'
    ]):
        # But not if it's specifically a departure
        if 'DEPARTURE' not in name_upper and 'SID' not in name_upper:
            return 'Approach'
    
    # Ground/Airport diagrams
    if any(keyword in name_upper for keyword in [
        'AERODROME CHART', 'AIRPORT CHART', 'PARKING', 'DOCKING', 'GROUND'
    ]):
        return 'Airport Diagram'
    
    return 'General'


def identify_charts_in_section(doc, start_page: int, end_page: int, icao_code: str) -> List[Dict]:
    """
    Identify chart pages within an airport section.
    
    Args:
        doc: PyMuPDF document
        start_page: Start page (1-indexed)
        end_page: End page (1-indexed)
        icao_code: ICAO code
        
    Returns:
        List of chart dictionaries with page numbers and names
    """
    charts = []
    
    for page_idx in range(start_page - 1, min(end_page, len(doc))):
        page = doc[page_idx]
        text = page.get_text()
        page_num = page_idx + 1
        
        chart_name = None
        chart_type = None
        
        # Check for specific chart types
        text_upper = text.upper()
        
        # Skip intentionally blank pages
        if 'INTENTIONALLY LEFT BLANK' in text_upper:
            continue
        
        # Skip pages that are just data tables without actual charts
        if 'AERONAUTICAL DATA CALCULATION' in text_upper and 'AD 2-' not in text_upper:
            continue
        
        # Aerodrome Chart - graphical chart
        if 'AERODROME CHART' in text_upper and ('ICAO' in text_upper or 'NOT TO SCALE' in text_upper or 'SCALE' in text_upper):
            chart_name = f"{icao_code} - Aerodrome Chart ICAO"
            chart_type = 'Airport Diagram'
        
        # Parking Chart
        elif 'PARKING' in text_upper and 'CHART' in text_upper:
            if 'TO BE DEVELOPED' not in text_upper:
                chart_name = f"{icao_code} - Aircraft Parking Chart"
                chart_type = 'Airport Diagram'
        
        # SID - Check for the graphical SID chart (page with AD 2-15 identifier)
        elif ('DEPARTURE' in text_upper and 'RNAV' in text_upper) or ('SID' in text_upper and 'RWY' in text_upper):
            # Check if this is a graphical chart page (has AD 2-xx reference for charts)
            ad_ref = re.search(r'AD\s*2-(\d+)', text)
            if ad_ref:
                rwy_match = re.search(r'RWY\s*(\d+)', text_upper)
                rwy = rwy_match.group(1) if rwy_match else '23'
                chart_name = f"{icao_code} - SID RNAV (GNSS) RWY {rwy}"
                chart_type = 'SID'
        
        # STAR - Standard Terminal Arrival
        elif 'ARRIVAL' in text_upper and 'RNAV' in text_upper and 'STAR' not in text_upper:
            ad_ref = re.search(r'AD\s*2-(\d+)', text)
            if ad_ref:
                rwy_match = re.search(r'RWY\s*(\d+)', text_upper)
                rwy = rwy_match.group(1) if rwy_match else '05'
                chart_name = f"{icao_code} - STAR RNAV (GNSS) RWY {rwy}"
                chart_type = 'STAR'
        
        # RNAV/RNP Approach - look for specific approach indicators
        elif ('APPROACH' in text_upper and ('RNAV' in text_upper or 'RNP' in text_upper)):
            if 'DEPARTURE' not in text_upper and 'ARRIVAL' not in text_upper:
                ad_ref = re.search(r'AD\s*2-(\d+)', text)
                if ad_ref:
                    rwy_match = re.search(r'RWY\s*(\d+)', text_upper)
                    rwy = rwy_match.group(1) if rwy_match else '05'
                    
                    # Check if RNP or GNSS and get variant (Y or Z)
                    if 'RNP' in text_upper and 'Z' in text_upper:
                        chart_name = f"{icao_code} - RNAV (RNP) Z RWY {rwy}"
                    elif 'RNP' in text_upper:
                        variant = 'Y' if 'Y' in text else ''
                        chart_name = f"{icao_code} - RNAV (RNP) {variant} RWY {rwy}"
                    elif 'GNSS' in text_upper:
                        variant = 'Z' if 'Z' in text else 'Y' if 'Y' in text else ''
                        chart_name = f"{icao_code} - RNAV (GNSS) {variant} RWY {rwy}"
                    else:
                        variant = 'Z' if 'Z' in text else 'Y' if 'Y' in text else ''
                        chart_name = f"{icao_code} - RNAV {variant} RWY {rwy}"
                    chart_type = 'Approach'
        
        # Check if it's a graphical chart page (has coordinates/scale and AD reference)
        elif any(x in text for x in ['Scale 1:', 'SCALE 1:', 'NOT TO SCALE']) and icao_code in text:
            # Only add if not already added and has AD reference
            ad_ref = re.search(r'AD\s*2-(\d+)', text)
            if ad_ref:
                if 'AERODROME' in text_upper:
                    chart_name = f"{icao_code} - Aerodrome Chart"
                    chart_type = 'Airport Diagram'
        
        if chart_name:
            # Check for duplicates by name (not exact match, but similar)
            is_duplicate = False
            for c in charts:
                # Simple duplicate check - same base name
                if chart_name.split(' RWY')[0] == c['name'].split(' RWY')[0]:
                    # Check if same runway
                    if 'RWY' in chart_name and 'RWY' in c['name']:
                        if chart_name.split('RWY ')[-1] == c['name'].split('RWY ')[-1]:
                            is_duplicate = True
                            break
                    elif chart_name == c['name']:
                        is_duplicate = True
                        break
            
            if not is_duplicate:
                charts.append({
                    'name': chart_name,
                    'page': page_num,
                    'type': chart_type
                })
    
    return charts


def extract_chart_page(doc, page_num: int, icao_code: str, chart_name: str, output_dir: str) -> str:
    """
    Extract a single page as a separate PDF.
    
    Args:
        doc: PyMuPDF document
        page_num: Page number (1-indexed)
        icao_code: ICAO code
        chart_name: Chart name for filename
        output_dir: Output directory
        
    Returns:
        str: Path to the created PDF
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # Sanitize filename
    safe_name = re.sub(r'[<>:"/\\|?*\s]+', '_', chart_name)
    safe_name = safe_name[:50]  # Limit length
    pdf_filename = f"{safe_name}.pdf"
    pdf_path = os.path.join(output_dir, pdf_filename)
    
    # Create new PDF with single page
    new_doc = fitz.open()
    new_doc.insert_pdf(doc, from_page=page_num - 1, to_page=page_num - 1)
    new_doc.save(pdf_path)
    new_doc.close()
    
    return pdf_path


def get_aerodrome_charts(icao_code: str, extract_pdfs: bool = False) -> List[Dict[str, str]]:
    """
    Get all aerodrome charts for a given ICAO code from Somalia AIP.
    
    Args:
        icao_code: 4-letter ICAO code (e.g., 'HCMM')
        extract_pdfs: If True, extract individual chart PDFs. Default False (use page references).
        
    Returns:
        List of dictionaries with 'name', 'url', and 'type' keys
    """
    icao_code = icao_code.upper()
    
    # Check if airport is in our list
    if icao_code not in AIRPORTS:
        print(f"Airport {icao_code} not found in Somalia AIP")
        print(f"Available airports: {', '.join(AIRPORTS.keys())}")
        return []
    
    if not FITZ_AVAILABLE:
        raise ImportError("PyMuPDF is required for Somalia charts. Install with: pip install pymupdf")
    
    airport_info = AIRPORTS[icao_code]
    
    # Set up cache path
    cache_dir = os.path.join(tempfile.gettempdir(), "somalia_aip")
    cache_file = os.path.join(cache_dir, "AIP_SOMALIA_PART3_AERODROMES.pdf")
    
    # Check if we need to download PDF
    need_download = True
    if os.path.exists(cache_file):
        from datetime import datetime
        file_age = (datetime.now().timestamp() - os.path.getmtime(cache_file)) / 3600 / 24
        if file_age < 30:  # Cache for 30 days (Somalia AIP doesn't update frequently)
            need_download = False
            print(f"Using cached PDF (age: {file_age:.1f} days)")
    
    if need_download:
        print("Downloading Somalia AIP Aerodromes PDF...")
        if not download_pdf(cache_file):
            print("Failed to download PDF")
            return []
        print(f"PDF cached to {cache_file}")
    
    # Open and process the PDF
    try:
        doc = fitz.open(cache_file)
        print(f"PDF has {len(doc)} pages")
        print(f"Processing {icao_code} - {airport_info['name']} (pages {airport_info['start_page']}-{airport_info['end_page']})")
        
        # Identify charts in this airport's section
        chart_defs = identify_charts_in_section(
            doc,
            airport_info['start_page'],
            airport_info['end_page'],
            icao_code
        )
        
        if not chart_defs:
            print(f"No charts found for {icao_code}")
            # Return at least a reference to the airport section
            chart_defs = [{
                'name': f"{icao_code} - {airport_info['name']} AD 2",
                'page': airport_info['start_page'],
                'type': 'General'
            }]
        
        charts = []
        output_dir = os.path.join(os.getcwd(), "output", "somalia", icao_code)
        
        for chart_def in chart_defs:
            chart_name = chart_def['name']
            page_num = chart_def['page']
            chart_type = chart_def['type']
            
            if extract_pdfs:
                try:
                    pdf_path = extract_chart_page(doc, page_num, icao_code, chart_name, output_dir)
                    chart_url = f"file:///{os.path.abspath(pdf_path).replace(os.sep, '/')}"
                except Exception as e:
                    print(f"Warning: Failed to extract page {page_num}: {e}")
                    chart_url = f"file:///{os.path.abspath(cache_file).replace(os.sep, '/')}#page={page_num}"
            else:
                chart_url = f"file:///{os.path.abspath(cache_file).replace(os.sep, '/')}#page={page_num}"
            
            charts.append({
                'name': chart_name,
                'url': chart_url,
                'type': chart_type,
                'page': page_num
            })
        
        doc.close()
        return charts
        
    except Exception as e:
        print(f"Error processing PDF: {e}")
        import traceback
        traceback.print_exc()
        return []


def main():
    """CLI entry point for testing."""
    if len(sys.argv) < 2:
        print("Usage: python somalia_scraper.py <ICAO_CODE>")
        print("Example: python somalia_scraper.py HCMM")
        print(f"\nAvailable airports: {', '.join(AIRPORTS.keys())}")
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
                print(f"  [Page {chart.get('page', '?')}] {chart['name']}")
                print(f"       {chart['url'][:80]}...")
    else:
        print("No charts found")


if __name__ == "__main__":
    main()

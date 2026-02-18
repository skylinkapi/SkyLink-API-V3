"""
UAE GCAA Scraper
Fetches aerodrome charts from UAE's eAIP (Eurocontrol style).
Base: https://www.gcaa.gov.ae/en/ais/AIPHtmlFiles/AIP/Current/AIP.aspx
Pattern: https://www.gcaa.gov.ae/en/ais/AIPHtmlFiles/AIP/Current/AIRACs/{AIRAC}/html/eAIP/OM-AD-2.{ICAO}-en-GB.html
"""

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from typing import List, Dict
import re


def get_aerodrome_charts(icao_code: str, verbose: bool = False) -> List[Dict[str, str]]:
    """
    Fetch aerodrome charts for a UAE airport (Eurocontrol eAIP).
    Args:
        icao_code: ICAO code (OMAA, OMDB, etc.)
        verbose: Print debug info
    Returns:
        List of chart dicts: {'name', 'url', 'type'}
    """
    icao_code = icao_code.upper()
    base_url = "https://www.gcaa.gov.ae/en/ais/AIPHtmlFiles/AIP/Current/UAE_AIP.html"
    airac_root = "https://www.gcaa.gov.ae/en/ais/AIPHtmlFiles/AIP/Current/AIRACs/"
    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0'})

    # Step 1: Get current AIRAC folder
    aip_html = session.get(base_url, timeout=30).text
    soup = BeautifulSoup(aip_html, 'html.parser')
    pub_link = None
    for a in soup.find_all('a', href=True):
        if 'AIRACs/' in a['href'] and 'index-en-GB.html' in a['href']:
            pub_link = urljoin(base_url, a['href'])
            break
    if not pub_link:
        if verbose:
            print("Could not find AIRAC publication link.")
        return []
    # Extract AIRAC folder
    m = re.search(r'AIRACs/([^/]+)/html/index-en-GB.html', pub_link)
    if not m:
        if verbose:
            print("Could not parse AIRAC folder.")
        return []
    airac_folder = m.group(1)
    airac_base = f"{airac_root}{airac_folder}/html/eAIP/"

    # Step 2: Construct airport page URL
    airport_url = f"{airac_base}AD-2.{icao_code}-en-GB.html"
    if verbose:
        print(f"Airport page: {airport_url}")
    try:
        resp = session.get(airport_url, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        if verbose:
            print(f"Error fetching airport page: {e}")
        return []
    soup = BeautifulSoup(resp.text, 'html.parser')

    # Step 3: Find AD 2.24 charts section
    charts = []
    ad24_section = soup.find(id=f'{icao_code}-AD-2.24')
    if not ad24_section:
        if verbose:
            print("No AD 2.24 section found.")
        return []
    
    # Group charts by title and find the most recent version
    chart_dict = {}
    
    figures = ad24_section.find_all('div', class_='Figure')
    for figure in figures:
        title_span = figure.find('span', class_='Figure-title')
        if not title_span:
            continue
        
        chart_name = title_span.get_text().strip()
        
        # Find all PDF links in this figure
        pdf_links = figure.find_all('a', href=lambda h: h and h.endswith('.pdf'))
        
        if pdf_links:
            # Find the most recent link (highest date in filename)
            latest_link = None
            latest_date = ''
            
            for link in pdf_links:
                href = link.get('href')
                if not href:
                    continue
                    
                # Extract date from filename (format: _YYYY-MM.pdf)
                if '_20' in href:
                    date_part = href.split('_20')[-1].replace('.pdf', '')
                    if date_part > latest_date:
                        latest_date = date_part
                        latest_link = link
            
            if latest_link:
                chart_dict[chart_name] = latest_link.get('href')
    
    # Convert to list format
    for chart_name, href in chart_dict.items():
        chart_url = urljoin(airport_url, href)
        charts.append({'name': chart_name, 'url': chart_url, 'type': 'General'})
        if verbose:
            print(f"  Chart: {chart_name} -> {chart_url}")
    
    return charts


def get_charts(icao_code: str, verbose: bool = False) -> List[Dict[str, str]]:
    return get_aerodrome_charts(icao_code, verbose)

if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        icao = sys.argv[1].upper()
        verbose = '--verbose' in sys.argv or '-v' in sys.argv
        charts = get_aerodrome_charts(icao, verbose=verbose)
        print(f"Found {len(charts)} charts:")
        for chart in charts:
            print(f"  {chart['name']}")
            print(f"    {chart['url']}")
    else:
        print("UAE GCAA AIP Scraper")
        print("Usage: python uae_scraper.py <ICAO> [--verbose]")
        print("Example: python uae_scraper.py OMDB")

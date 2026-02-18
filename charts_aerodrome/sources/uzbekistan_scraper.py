#!/usr/bin/env python3
"""
Uzbekistan eAIP Scraper
Scrapes aerodrome charts from Uzbekistan AIP
"""

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote
import re
import sys


BASE_URL = "https://uzaeronavigation.com"


def get_aerodrome_charts(icao_code):
    """
    Get all aerodrome charts for a given ICAO code from Uzbekistan eAIP

    Args:
        icao_code: 4-letter ICAO code (e.g., 'UTTT')

    Returns:
        List of dictionaries with 'name', 'url', and 'type' keys
    """
    print("DEBUG: Using updated Uzbekistan scraper with English names")  # Debug print
    charts = []

    try:
        # Get the main AIS page
        response = requests.get(f"{BASE_URL}/ais/", timeout=30)
        if response.status_code != 200:
            print(f"Error: Got status code {response.status_code}")
            return charts

        soup = BeautifulSoup(response.text, 'html.parser')

        # Find all airports under AD 2. АЭРОДРОМЫ
        # Look for airport sections that start with ICAO codes
        airport_sections = []

        # Find all list items that contain airport names starting with ICAO codes
        for li in soup.find_all('li'):
            a_tag = li.find('a')
            if a_tag and a_tag.get_text().strip():
                text = a_tag.get_text().strip()
                # Check if it starts with 4-letter ICAO code followed by dash
                if re.match(r'^[A-Z]{4}-', text):
                    airport_icao = text[:4]
                    airport_sections.append((airport_icao, li))

        # Find the section for our ICAO code
        target_section = None
        for airport_icao, li in airport_sections:
            if airport_icao == icao_code:
                target_section = li
                break

        if not target_section:
            print(f"Airport {icao_code} not found in Uzbekistan AIP")
            return charts

        # Within the airport section, find all chart PDFs (AD 2.24 section)
        # Look for all PDF links that are chart-related
        chart_links = []

        # Find all links with FileView onclick within this airport section
        for a_tag in target_section.find_all('a', onclick=True):
            onclick = a_tag.get('onclick', '')
            # Extract PDF path from FileView('/media/file/filename.pdf')
            match = re.search(r"FileView\('(/media/file/[^']+\.pdf)'\)", onclick)
            if match:
                pdf_path = match.group(1)
                chart_name = a_tag.get_text().strip()

                # Only include actual chart links (not section headers)
                # Charts typically have numbering like (2.24-1.0) or (2.24-4.X)
                # Also include DATA, TEXTS, TABLES entries
                if re.search(r'\(2\.24-[0-9A-Z. ]+', chart_name) or ('DATA' in chart_name.upper() and 'TEXT' in chart_name.upper() and 'TABLE' in chart_name.upper()):
                    chart_links.append((chart_name, pdf_path))

        if not chart_links:
            print(f"No chart links found for {icao_code}")
            return charts

        # Process each chart link
        for chart_name, pdf_path in chart_links:
            # Build full URL
            full_url = urljoin(BASE_URL, pdf_path)

            # URL encode the PDF filename (spaces and special characters)
            url_parts = full_url.rsplit('/', 1)
            if len(url_parts) == 2:
                base_url, filename = url_parts
                encoded_filename = quote(filename, safe='')
                full_url = f"{base_url}/{encoded_filename}"

            # Categorize the chart
            chart_type = categorize_chart(chart_name)

            charts.append({
                'name': chart_name,
                'url': full_url,
                'type': chart_type
            })

        return charts

    except Exception as e:
        print(f"Error scraping {icao_code}: {e}")
        import traceback
        traceback.print_exc()
        return charts


def categorize_chart(chart_name):
    """Categorize chart based on its name"""
    chart_name_upper = chart_name.upper()

    # SID - Standard Instrument Departure
    if any(keyword in chart_name_upper for keyword in [
        'СТАНДАРТНОГО ВЫЛЕТА', 'SID', 'DEPARTURE', 'ВЫЛЕТА ПО ПРИБОРАМ'
    ]):
        return 'SID'

    # STAR - Standard Terminal Arrival
    if any(keyword in chart_name_upper for keyword in [
        'СТАНДАРТНОГО ПРИБЫТИЯ', 'STAR', 'ARRIVAL', 'ПРИБЫТИЯ ПО ПРИБОРАМ'
    ]):
        return 'STAR'

    # APP - Approach procedures
    if any(keyword in chart_name_upper for keyword in [
        'ЗАХОДА НА ПОСАДКУ', 'APPROACH', 'ILS', 'LOC', 'RNP', 'NDB', 'VOR',
        'ВИЗУАЛЬНОГО ЗАХОДА', 'VISUAL APPROACH'
    ]):
        return 'APP'

    # GND - Ground movement charts
    if any(keyword in chart_name_upper for keyword in [
        'СТОЯНОК', 'НАЗЕМНОГО ДВИЖЕНИЯ', 'PARKING', 'DOCKING', 'GROUND MOVEMENT',
        'РУЛЕНИЯ', 'TAXI', 'СТОЯНКАХ', 'STANDS'
    ]):
        return 'GND'

    # GEN - General aerodrome charts and other
    if any(keyword in chart_name_upper for keyword in [
        'АЭРОДРОМА', 'AERODROME CHART', 'АЭРОДРОМ', 'РАЙОНА АЭРОДРОМА',
        'КООРДИНАТЫ', 'МИНИМУМЫ', 'MINIMUMS', 'AREA'
    ]):
        return 'GEN'

    # Default to GEN for unknown types
    return 'GEN'


def main():
    if len(sys.argv) < 2:
        print("Usage: python uzbekistan_scraper.py <ICAO_CODE>")
        print("Example: python uzbekistan_scraper.py UTTT")
        sys.exit(1)

    icao_code = sys.argv[1].upper()

    print(f"Fetching charts for {icao_code}...")
    charts = get_aerodrome_charts(icao_code)

    if charts:
        print(f"\nFound {len(charts)} charts:")
        for chart in charts:
            print(f"  [{chart['type']}] {chart['name']}")
            print(f"    {chart['url']}")
    else:
        print("No charts found")


if __name__ == "__main__":
    main()

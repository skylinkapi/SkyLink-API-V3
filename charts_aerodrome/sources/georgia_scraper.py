#!/usr/bin/env python3
"""
Georgia eAIP Scraper
Scrapes aerodrome charts from Georgia AIP following Eurocontrol structure
"""

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote
import re
import sys


BASE_URL = "https://airnav.ge/eaip/"


def get_latest_eaip_date():
    """Get the date string of the latest Georgia eAIP from history page"""
    try:
        history_url = "https://airnav.ge/eaip/UG-history-en-GB.html"
        response = requests.get(history_url, timeout=30)
        soup = BeautifulSoup(response.text, 'lxml')

        # Find the table with AIRAC history
        table = soup.find('table')
        if not table:
            return None

        rows = table.find_all('tr')
        if len(rows) < 2:
            return None

        # The first data row (index 1) contains the current effective issue
        # Format: cells[4] = "25 DEC 2025", cells[5] = "13 NOV 2025", cells[6] = "AIRAC AIP AMDT 09/25"
        first_row = rows[1]
        cells = first_row.find_all(['td', 'th'])
        if len(cells) >= 5:
            effective_date = cells[4].get_text(strip=True)
            # Convert "25 DEC 2025" to "2025-12-25-000000"
            if effective_date:
                # Parse the date
                match = re.match(r'(\d{1,2})\s+(\w{3})\s+(\d{4})', effective_date)
                if match:
                    day, month, year = match.groups()
                    # Convert month abbreviation to number
                    months = {
                        'JAN': '01', 'FEB': '02', 'MAR': '03', 'APR': '04',
                        'MAY': '05', 'JUN': '06', 'JUL': '07', 'AUG': '08',
                        'SEP': '09', 'OCT': '10', 'NOV': '11', 'DEC': '12'
                    }
                    month_num = months.get(month.upper(), '01')
                    day_padded = day.zfill(2)
                    date_str = f"{year}-{month_num}-{day_padded}-000000"
                    return date_str

        return None

    except Exception as e:
        print(f"Error getting latest eAIP date: {e}")
        return None


def get_airport_page_url(icao_code, eaip_date=None):
    """Get the URL for a specific airport's AD 2 page"""
    if eaip_date is None:
        eaip_date = get_latest_eaip_date()

    if not eaip_date:
        return None

    # Format: UG-AD-2-ICAO-en-GB.html
    airport_page = f"UG-AD-2-{icao_code}-en-GB.html"
    full_url = f"{BASE_URL}{eaip_date}/html/eAIP/{airport_page}"
    return full_url


def categorize_chart(chart_name):
    """Categorize chart based on its name"""
    chart_name_upper = chart_name.upper()

    if 'SID' in chart_name_upper or 'DEPARTURE' in chart_name_upper:
        return 'SID'
    elif 'STAR' in chart_name_upper or 'ARRIVAL' in chart_name_upper:
        return 'STAR'
    elif 'APPROACH' in chart_name_upper or 'ILS' in chart_name_upper or 'LOC' in chart_name_upper \
            or 'NDB' in chart_name_upper or 'RNP' in chart_name_upper or 'GLS' in chart_name_upper \
            or 'VOR' in chart_name_upper:
        return 'APP'
    elif 'AERODROME CHART' in chart_name_upper or 'GROUND MOVEMENT' in chart_name_upper \
            or 'PARKING' in chart_name_upper or 'VISUAL APPROACH' in chart_name_upper:
        return 'GND'
    else:
        return 'GEN'


def get_aerodrome_charts(icao_code):
    """
    Get all aerodrome charts for a given ICAO code from Georgia eAIP

    Args:
        icao_code: 4-letter ICAO code (e.g., 'UGTB')

    Returns:
        List of dictionaries with 'name', 'url', and 'type' keys
    """
    charts = []

    try:
        # Get airport page URL
        airport_url = get_airport_page_url(icao_code)
        if not airport_url:
            print(f"Could not determine airport page URL for {icao_code}")
            return charts

        print(f"Fetching {airport_url}")

        # Get the airport page
        response = requests.get(airport_url, timeout=30)
        if response.status_code != 200:
            print(f"Error: Got status code {response.status_code}")
            return charts

        soup = BeautifulSoup(response.text, 'lxml')

        # Find the charts section (AD 2.24)
        charts_section = None
        for header in soup.find_all(['h1', 'h2', 'h3', 'h4']):
            header_text = header.get_text().strip()
            if '2.24' in header_text and 'chart' in header_text.lower():
                charts_section = header
                break

        if not charts_section:
            print("Could not find charts section")
            return charts

        # Find the table in the charts section
        parent = charts_section.parent
        while parent and parent.name != 'div':
            parent = parent.parent

        if parent:
            table = parent.find('table')
            if table:
                rows = table.find_all('tr')
                # Skip header row
                for row in rows[1:]:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 2:
                        chart_name = cells[0].get_text(strip=True)
                        page_cell = cells[1]

                        # Find PDF link in the page cell
                        pdf_link = page_cell.find('a', href=lambda x: x and x.endswith('.pdf'))
                        if pdf_link:
                            href = pdf_link['href']

                            # Build full URL - href is like ../../pdf/filename.pdf
                            full_url = urljoin(airport_url, href)

                            # URL encode the PDF filename
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


def main():
    if len(sys.argv) < 2:
        print("Usage: python georgia_scraper.py <ICAO_CODE>")
        print("Example: python georgia_scraper.py UGTB")
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
"""
Cape Verde eAIP Scraper
Scrapes aerodrome charts from ASA eAIP (eaip.asa.cv)

Base URL: https://eaip.asa.cv/
Structure:
- Main page has link to current version
- AD 2 page: html/eAIP/GV-AD-2.{icao}-en-GB.html
- PDFs: graphics/ directory

ICAO prefix: GV*
Examples: GVNP (Sal), GVAC (Sal International)
"""

import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote
import sys


BASE_URL = "https://eaip.asa.cv/"


def get_latest_aip_base_url():
    """
    Get the base URL for the latest Cape Verde AIP.

    Returns:
        str: Base URL like 'https://eaip.asa.cv/2024-04-18-AIRAC/'
    """
    try:
        response = requests.get(BASE_URL, timeout=30)
        soup = BeautifulSoup(response.text, "html.parser")

        # Find link to current version - typically has date pattern
        for link in soup.find_all("a", href=True):
            href = link["href"]
            # Look for AIRAC date pattern
            match = re.search(r"(\d{4}-\d{2}-\d{2}-AIRAC)", href)
            if match:
                # Return just the base URL (without html/index-en-GB.html)
                airac_folder = match.group(1)
                return f"{BASE_URL}{airac_folder}/"

        return None

    except Exception as e:
        print(f"Error getting latest AIP URL: {e}")
        return None


def get_airport_page_url(icao_code, base_url):
    """
    Construct the URL for an airport's AD 2 page.
    """
    # Airport pages: html/eAIP/GV-AD-2.{icao}-en-GB.html
    return f"{base_url}html/eAIP/GV-AD-2.{icao_code.upper()}-en-GB.html"


def categorize_chart(chart_name):
    """Categorize a chart based on its name."""
    name_upper = chart_name.upper()

    if any(keyword in name_upper for keyword in ["SID", "DEPARTURE", "TAKEOFF"]):
        return "SID"

    if any(keyword in name_upper for keyword in ["STAR", "ARRIVAL"]):
        return "STAR"

    if any(
        keyword in name_upper
        for keyword in [
            "APPROACH",
            "ILS",
            "LOC",
            "VOR",
            "NDB",
            "RNAV",
            "RNP",
            "DME",
            "INSTRUMENT APPROACH",
            "VISUAL APPROACH",
            "CIRCLING",
        ]
    ):
        return "APP"

    if any(
        keyword in name_upper
        for keyword in [
            "AERODROME CHART",
            "AIRPORT CHART",
            "PARKING",
            "DOCKING",
            "GROUND MOVEMENT",
            "TAXI",
            "OBSTACLE",
        ]
    ):
        return "GND"

    return "GEN"


def get_aerodrome_charts(icao_code):
    """
    Get all aerodrome charts for a given ICAO code from Cape Verde eAIP.
    """
    charts = []
    icao_code = icao_code.upper()

    try:
        base_url = get_latest_aip_base_url()
        if not base_url:
            print("Could not determine current AIP version")
            return charts

        airport_url = get_airport_page_url(icao_code, base_url)
        print(f"Fetching {airport_url}")

        response = requests.get(airport_url, timeout=30)
        if response.status_code == 404:
            print(f"Airport {icao_code} not found in Cape Verde AIP")
            return charts

        soup = BeautifulSoup(response.text, "html.parser")

        # Find AD 2.24 section with charts - look for div containing charts
        # or process all PDF links on the page
        pdf_links = soup.find_all("a", href=True)
        
        # Find AD 2.24 section with charts - look for div containing charts
        # or process all PDF links on the page
        pdf_links = soup.find_all("a", href=True)
        
        # Use a set to track unique (name, url) pairs
        unique_charts = set()
        
        for link in pdf_links:
            href = link["href"]
            if not (href.lower().endswith(".pdf") or href.startswith("../../graphics/")):
                continue

            # Get chart name - look for text in parent elements
            chart_name = link.get_text(strip=True)
            
            # Always try to get the full name from the previous table cell
            parent_td = link.find_parent("td")
            if parent_td:
                prev_td = parent_td.find_previous_sibling("td")
                if prev_td:
                    full_name = prev_td.get_text(strip=True)
                    if full_name and len(full_name) > len(chart_name):
                        chart_name = full_name
            
            # If still no name, try figcaption
            if not chart_name:
                figure = link.find_parent("figure")
                if figure:
                    caption = figure.find("figcaption")
                    if caption:
                        chart_name = caption.get_text(strip=True)
            
            # Default to filename if no name found
            if not chart_name:
                chart_name = href.split("/")[-1].replace(".pdf", "")

            # Build full URL
            if href.startswith("../../graphics/"):
                filename = href.split("/")[-1]
                # Remove .pdf extension if present (though graphics links don't have it)
                if filename.lower().endswith('.pdf'):
                    filename = filename[:-4]
                full_url = f"{base_url}graphics/{quote(filename)}"
            else:
                full_url = urljoin(airport_url, href)

            chart_type = categorize_chart(chart_name)

            # Create unique key
            chart_key = (chart_name, full_url)
            if chart_key not in unique_charts:
                unique_charts.add(chart_key)
                chart_type = categorize_chart(chart_name)
                charts.append({"name": chart_name, "url": full_url, "type": chart_type})

        return charts

    except Exception as e:
        print(f"Error scraping {icao_code}: {e}")
        import traceback

        traceback.print_exc()
        return charts


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python cape_verde_scraper.py <ICAO_CODE>")
        print("Example: python cape_verde_scraper.py GVNP")
        sys.exit(1)

    icao_code = sys.argv[1].upper()
    charts = get_aerodrome_charts(icao_code)

    if charts:
        print(f"\nFound {len(charts)} charts:")
        for chart in charts:
            print(f"  [{chart['type']}] {chart['name']}")
            print(f"    {chart['url']}")
    else:
        print("No charts found")

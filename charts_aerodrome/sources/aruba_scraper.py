"""
Aruba/Dutch Caribbean eAIP Scraper
Scrapes aerodrome charts from Dutch Caribbean eAIP

Base URL: https://dc-ansp.org/eAIS/eAIP/
Structure:
- Shared eAIP for Dutch Caribbean (Aruba, Curaçao, Sint Maarten, Bonaire, Sint Eustatius, Saba)
- ICAO prefix: TN* (TNCA, TNCC, TNCM, TNCB, TNCS, TNCE)

Examples:
- TNCA (Queen Beatrix International, Aruba)
- TNCC (Curaçao International) 
- TNCM (Princess Juliana International, Sint Maarten)
- TNCB (Flamingo International, Bonaire)
- TNCS (Juancho E. Yrausquin, Saba)
- TNCE (F.D. Roosevelt, Sint Eustatius)
"""

import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote
import sys


BASE_URL = "https://dc-ansp.org/eAIS/eAIP/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5"
}

# Map ICAO codes to their airport names in URL
AIRPORT_NAMES = {
    "TNCA": "ARUBA",
    "TNCC": "CURAÇAO",  # Note: actual URL uses "CURAÃO" due to encoding
    "TNCM": "SINT MAARTEN",
    "TNCB": "BONAIRE",
    "TNCS": "SABA",
    "TNCE": "SINT EUSTATIUS"
}


def get_latest_aip_base_url():
    """Get the base URL for the latest Dutch Caribbean AIP AIRAC folder."""
    try:
        index_url = f"{BASE_URL}default.html"
        response = requests.get(index_url, headers=HEADERS, timeout=30)
        soup = BeautifulSoup(response.text, "lxml")

        # Find the "Currently Effective Issue" link
        # Format: href="AIRAC AMDT 05-25_2025_11_27\index.html" 
        for link in soup.find_all("a", href=True):
            href = link["href"]
            # Look for AIRAC AMDT pattern
            if "AIRAC AMDT" in href and "index.html" in href:
                # Extract the folder name and URL encode it
                folder = href.replace("\\", "/").rsplit("/", 1)[0]
                folder_encoded = quote(folder, safe='')
                return f"{BASE_URL}{folder_encoded}/"
        
        return None

    except Exception as e:
        print(f"Error getting latest AIP URL: {e}")
        return None


def find_airport_page(icao_code, base_url):
    """Find the airport page URL by searching the menu."""
    try:
        # Get the menu page which lists all airports
        menu_url = f"{base_url}eAIP/menu.html"
        response = requests.get(menu_url, headers=HEADERS, timeout=30)
        # Force UTF-8 encoding
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, "lxml")
        
        # Find link containing our ICAO code
        for link in soup.find_all("a", href=True):
            href = link["href"]
            # Links are like "AD 2 TNCA - ARUBA 1-en-US.html#AD-2-TNCA---ARUBA-1"
            if f"AD 2 {icao_code}" in href:
                # Extract just the HTML filename (before the #)
                page_name = href.split("#")[0]
                # Properly encode the filename for URL - encode as UTF-8 bytes first
                encoded_page = quote(page_name.encode('utf-8'), safe='')
                return f"{base_url}eAIP/{encoded_page}"
        
        return None
        
    except Exception as e:
        print(f"Error finding airport page: {e}")
        return None


def categorize_chart(chart_name):
    """Categorize a chart based on its name."""
    name_upper = chart_name.upper()

    if any(keyword in name_upper for keyword in ["SID", "DEPARTURE"]):
        return "SID"

    if any(keyword in name_upper for keyword in ["STAR", "ARRIVAL"]):
        return "STAR"

    if any(
        keyword in name_upper
        for keyword in ["APPROACH", "ILS", "LOC", "VOR", "NDB", "RNAV", "RNP", "DME"]
    ):
        return "Approach"

    if any(
        keyword in name_upper
        for keyword in ["AERODROME CHART", "AIRPORT CHART", "PARKING", "GROUND", "TAXI", "ICAO"]
    ):
        return "Airport Diagram"

    return "General"


def get_aerodrome_charts(icao_code):
    """Get all aerodrome charts for a given ICAO code from Dutch Caribbean eAIP."""
    charts = []
    icao_code = icao_code.upper()

    try:
        base_url = get_latest_aip_base_url()
        if not base_url:
            print("Could not determine current AIP version")
            return charts

        airport_url = find_airport_page(icao_code, base_url)
        if not airport_url:
            print(f"Airport {icao_code} not found in Dutch Caribbean AIP")
            return charts
            
        print(f"Fetching {airport_url}")

        response = requests.get(airport_url, headers=HEADERS, timeout=30)
        if response.status_code == 404:
            print(f"Airport {icao_code} page not found")
            return charts

        soup = BeautifulSoup(response.text, "lxml")

        # Find all PDF links in the page
        seen_urls = set()
        for link in soup.find_all("a", href=True):
            href = link["href"]
            if not href.lower().endswith(".pdf"):
                continue

            # Get chart name from link text
            chart_name = link.get_text(strip=True)
            if not chart_name:
                # Use filename as fallback
                chart_name = href.rsplit("/", 1)[-1].replace(".pdf", "").replace("%20", " ")

            # Build full URL - PDFs are usually in ../graphics/eAIP/ folder
            if "../graphics/" in href:
                # Relative path like ../graphics/eAIP/filename.pdf
                filename = href.split("/")[-1]
                full_url = f"{base_url}graphics/eAIP/{quote(filename, safe='')}"
            else:
                full_url = urljoin(airport_url, href)

            # Avoid duplicates
            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)

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
        print("Usage: python aruba_scraper.py <ICAO_CODE>")
        print("Example: python aruba_scraper.py TNCA")
        print("Supported airports: TNCA, TNCC, TNCM, TNCB, TNCS, TNCE")
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

#!/usr/bin/env python3
"""
Lithuania eAIP Scraper
Scrapes aerodrome charts from Lithuania AIP (ANS)

Base URL: https://www.ans.lt/a1/aip/
ICAO prefix: EY* (EYVI - Vilnius, EYKA - Kaunas, EYPA - Palanga, EYSA - Šiauliai)

Approach:
1. Get directory listing from https://www.ans.lt/a1/aip/
2. Find latest AIRAC folder (e.g., 004_25Dec_2025)
3. Navigate to {folder}/{date}/html/eAIP/
4. Find airport page EY-AD-2-{ICAO}-en-US.html
5. Extract charts from AD 2.24 section

Note: Site uses Cloudflare - requires Selenium
"""

import re
import time
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote
import sys

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager
    HAS_SELENIUM = True
except ImportError:
    HAS_SELENIUM = False


BASE_URL = "https://www.ans.lt/a1/aip/"


def create_driver():
    """Create Chrome WebDriver for Cloudflare bypass."""
    if not HAS_SELENIUM:
        raise ImportError(
            "Selenium required for Lithuania. Install:\n"
            "pip install selenium webdriver-manager"
        )
    
    opts = Options()
    opts.add_argument("--headless")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option('useAutomationExtension', False)
    opts.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=opts)
    driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
        'source': "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    })
    
    return driver


def categorize_chart(name):
    """Categorize chart by name."""
    n = name.upper()
    if any(k in n for k in ['SID', 'DEPARTURE']):
        return 'SID'
    if any(k in n for k in ['STAR', 'ARRIVAL']):
        return 'STAR'
    if any(k in n for k in ['APPROACH', 'ILS', 'VOR', 'RNP', 'RNAV', 'LOC', 'NDB', 'DME', 'IAC']):
        return 'Approach'
    if any(k in n for k in ['AERODROME', 'PARKING', 'GROUND', 'TAXI', 'ADC']):
        return 'Airport Diagram'
    return 'General'


def get_aerodrome_charts(icao_code):
    """
    Fetch charts for an ICAO code from Lithuania eAIP.
    
    Args:
        icao_code: 4-letter ICAO (e.g., 'EYVI')
        
    Returns:
        list of dicts: {'name', 'url', 'type'}
    """
    charts = []
    icao_code = icao_code.upper()
    driver = None
    
    try:
        driver = create_driver()
        
        # Step 1: Get directory listing to find latest AIRAC folder
        print(f"Fetching directory listing from {BASE_URL}")
        driver.get(BASE_URL)
        time.sleep(12)  # Wait longer for Cloudflare
        
        html = driver.page_source
        
        # Find AIRAC folders like "004_25Dec_2025/"
        airac_folders = re.findall(r'href="(\d{3}_\d{1,2}[A-Za-z]{3}_\d{4})/?">',  html)
        
        if not airac_folders:
            # Try alternate pattern
            airac_folders = re.findall(r'>(\d{3}_\d{1,2}[A-Za-z]{3}_\d{4})/?<', html)
        
        if not airac_folders:
            print("Could not find AIRAC folders in directory")
            return charts
        
        # Get latest (sort descending)
        airac_folders = list(set(airac_folders))
        airac_folders.sort(reverse=True)
        airac_folder = airac_folders[0]
        print(f"Found latest AIRAC: {airac_folder}")
        
        # Step 2: Navigate to AIRAC folder to find date folder
        airac_url = f"{BASE_URL}{airac_folder}/"
        print(f"Navigating to {airac_url}")
        driver.get(airac_url)
        time.sleep(5)
        
        html = driver.page_source
        
        # Find date folder like "2025-12-25-000000"
        date_folders = re.findall(r'href="(\d{4}-\d{2}-\d{2}-\d+)/?"', html)
        
        if not date_folders:
            print("Could not find date folder")
            return charts
        
        date_folder = date_folders[0]
        print(f"Found date folder: {date_folder}")
        
        # Step 3: Go to eAIP folder and find airport page
        eaip_url = f"{BASE_URL}{airac_folder}/{date_folder}/html/eAIP/"
        airport_page = f"EY-AD-2-{icao_code}-en-US.html"
        airport_url = eaip_url + airport_page
        
        print(f"Fetching airport page: {airport_url}")
        driver.get(airport_url)
        time.sleep(8)
        
        html = driver.page_source
        
        if 'chartTable' not in html and 'AD 2.24' not in html:
            print(f"Airport {icao_code} not found or page blocked")
            return charts
        
        soup = BeautifulSoup(html, 'lxml')
        
        # Find chart tables
        tables = soup.find_all('table', class_='chartTable')
        if not tables:
            for t in soup.find_all('table'):
                if t.find('a', href=lambda h: h and '.pdf' in h.lower()):
                    tables.append(t)
        
        if not tables:
            print(f"No charts found for {icao_code}")
            return charts
        
        seen = set()
        
        for table in tables:
            for row in table.find_all('tr'):
                cells = row.find_all('td')
                if len(cells) < 2:
                    continue
                
                name = cells[0].get_text(strip=True)
                if not name:
                    continue
                
                # Find PDF link (skip deleted ones)
                pdf_link = None
                for link in cells[1].find_all('a', href=lambda h: h and '.pdf' in h.lower()):
                    if not link.find_parent('div', class_='AmdtDeletedAIRAC'):
                        pdf_link = link
                        break
                
                if not pdf_link:
                    continue
                
                href = pdf_link.get('href', '')
                chart_url = href if href.startswith('http') else urljoin(airport_url, href)
                
                # Encode spaces
                if ' ' in chart_url:
                    parts = chart_url.rsplit('/', 1)
                    if len(parts) == 2:
                        chart_url = parts[0] + '/' + quote(parts[1], safe='')
                
                if chart_url in seen:
                    continue
                seen.add(chart_url)
                
                charts.append({
                    'name': name,
                    'url': chart_url,
                    'type': categorize_chart(name)
                })
        
        return charts
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return charts
    finally:
        if driver:
            driver.quit()


def main():
    if len(sys.argv) < 2:
        print("Usage: python lithuania_scraper.py <ICAO>")
        print("Example: python lithuania_scraper.py EYVI")
        sys.exit(1)
    
    icao = sys.argv[1].upper()
    print(f"Fetching charts for {icao}...")
    
    charts = get_aerodrome_charts(icao)
    
    if charts:
        print(f"\nFound {len(charts)} charts:")
        for c in charts:
            print(f"  [{c['type']}] {c['name']}")
            print(f"    {c['url']}")
    else:
        print("No charts found")


if __name__ == "__main__":
    main()

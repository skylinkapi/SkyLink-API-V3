# Aerodrome Charts Scraping Patterns Guide

**Purpose:** Comprehensive guide for LLMs to analyze AIP websites and implement scrapers automatically.

**Last Updated:** January 24, 2026

---

## Table of Contents

1. [Quick Decision Tree](#quick-decision-tree)
2. [Pattern 1: Eurocontrol eAIP Standard](#pattern-1-eurocontrol-eaip-standard)
3. [Pattern 2: Fragment-Based Navigation](#pattern-2-fragment-based-navigation)
4. [Pattern 3: Static HTML Parsing](#pattern-3-static-html-parsing)
5. [Pattern 4: JSON API](#pattern-4-json-api)
6. [Pattern 5: JavaScript SPA (Selenium Required)](#pattern-5-javascript-spa-selenium-required)
7. [Pattern 6: Pre-scraped JSON Database](#pattern-6-pre-scraped-json-database)
8. [Common Chart Categorization Logic](#common-chart-categorization-logic)
9. [Testing and Validation](#testing-and-validation)
10. [Integration Checklist](#integration-checklist)

---

## Quick Decision Tree

When given an AIP website URL, follow this decision tree:

```
1. Open the URL in a browser
   └─> Does the URL contain "eAIP" or follow Eurocontrol structure?
       ├─> YES → Pattern 1: Eurocontrol eAIP Standard
       └─> NO → Continue to step 2

2. Search for an airport ICAO code (or click AD section)
   └─> Does content appear without page reload (JavaScript)?
       ├─> YES → Check if URL changes with # (fragment)
       │   ├─> YES → Pattern 2: Fragment-Based Navigation
       │   └─> NO → Pattern 5: JavaScript SPA (Selenium)
       └─> NO → Continue to step 3

3. View page source (Ctrl+U)
   └─> Can you find chart PDF links in the HTML source?
       ├─> YES → Pattern 3: Static HTML Parsing
       └─> NO → Continue to step 4

4. Open browser DevTools → Network tab → Refresh
   └─> Do you see JSON API calls with chart data?
       ├─> YES → Pattern 4: JSON API
       └─> NO → Pattern 5: JavaScript SPA (Selenium)
```

---

## Pattern 1: Eurocontrol eAIP Standard

**Countries:** Belarus, Romania, Serbia, Bosnia, Armenia, Slovenia, Hungary, Czech Republic, Albania, Portugal

**Characteristics:**
- URL contains `/eAIP/` or follows Eurocontrol structure
- Date-based AIRAC folders (e.g., `2025-11-27-AIRAC`)
- Airport pages: `{PREFIX}-AD-2.{ICAO}-en-GB.html`
- Charts in AD 2.24 section
- PDFs in `graphics/eAIP/` directory

### Implementation Steps

#### Step 1: Find the Latest AIRAC Date Folder

**Method A: Index page with links to date folders**
```python
def get_latest_eaip_url():
    response = requests.get(f"{BASE_URL}/html/index.html", timeout=30)
    soup = BeautifulSoup(response.text, 'lxml')
    
    # Find all date folder links
    date_links = []
    for link in soup.find_all('a', href=True):
        href = link['href']
        # Pattern: ./27-Nov-2025-A/2025-11-27-AIRAC/html/index.html
        if 'AIRAC' in href and 'html/index' in href:
            match = re.search(r'\./([^/]+/[^/]+AIRAC)', href)
            if match:
                date_links.append(match.group(1))
    
    # Return the latest (usually first or last)
    return f"{BASE_URL}/{date_links[0]}/html/eAIP/"
```

**Method B: Direct "Current version" link in table**
```python
def get_latest_eaip_url():
    response = requests.get(f"{BASE_URL}/aip/", timeout=30)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Find table with "Current version" text
    for row in soup.find_all('tr'):
        text = row.get_text()
        if 'current version' in text.lower():
            link = row.find('a', href=True)
            if link:
                return urljoin(BASE_URL, link['href'])
```

**Method C: Static path (no date folder)**
```python
def get_latest_eaip_url():
    # Some countries use a static path like /eAIP_Current/
    return f"{BASE_URL}/eAIP_Current/html/en/"
```

#### Step 2: Construct Airport Page URL

```python
def get_airport_page_url(icao_code):
    base_eaip = get_latest_eaip_url()
    # Format: {PREFIX}-AD-2.{ICAO}-en-GB.html
    # PREFIX is the ICAO country prefix (e.g., UM for Belarus, LR for Romania)
    airport_page = f"{PREFIX}-AD-2.{icao_code}-en-GB.html"
    return urljoin(base_eaip, airport_page)
```

#### Step 3: Extract Charts from AD 2.24 Section

```python
def get_aerodrome_charts(icao_code):
    charts = []
    airport_url = get_airport_page_url(icao_code)
    
    response = requests.get(airport_url, timeout=30)
    soup = BeautifulSoup(response.text, 'lxml')
    
    # Method A: Find all PDF links
    for link in soup.find_all('a', href=True):
        href = link['href']
        if '.pdf' not in href.lower():
            continue
        
        # Get chart name from previous sibling row or same row
        td_parent = link.find_parent('td')
        if not td_parent:
            continue
        
        tr_parent = td_parent.find_parent('tr')
        prev_row = tr_parent.find_previous_sibling('tr')
        
        if prev_row:
            name_td = prev_row.find('td')
            if name_td:
                chart_name = name_td.get_text(strip=True)
                
                # Build full URL (resolve relative paths)
                full_url = urljoin(airport_url, href)
                
                # URL encode filename only (preserve path)
                url_parts = full_url.rsplit('/', 1)
                if len(url_parts) == 2:
                    base_url, filename = url_parts
                    encoded_filename = quote(filename, safe='')
                    full_url = f"{base_url}/{encoded_filename}"
                
                charts.append({
                    'name': chart_name,
                    'url': full_url,
                    'type': categorize_chart(chart_name)
                })
    
    return charts
```

### Common Variations

**Variation 1: Menu in iframe**
- Some sites have menus in iframes: append `/LA-menu-en-GB.html`
- Adjust base URL path accordingly

**Variation 2: Chart names in different cells**
```python
# Chart name might be in same row, different column
name_cell = tr_parent.find('td', class_='chart-name')
# Or in a specific column position
name_cell = tr_parent.find_all('td')[0]
```

**Variation 3: Multiple PDF links per chart**
```python
# Use set to track seen URLs
seen_urls = set()
if full_url not in seen_urls:
    seen_urls.add(full_url)
    charts.append(...)
```

### Example Countries

**Belarus** (`sources/belarus_scraper.py`):
- Base: `https://www.ban.by`
- AIRAC folders: Extract from amendment page
- Prefix: `UM`

**Romania** (`sources/romania_scraper.py`):
- Base: `https://aisro.ro/aip/`
- TOC-based: Parse full AD table of contents
- Prefix: `LR`

**Albania** (`sources/albania_scraper.py`):
- Base: `https://www.albcontrol.al/aip/`
- Current version: Find link with `color: blue` style
- Prefix: `LA`

**Portugal** (`sources/portugal_scraper.py`):
- Base: `https://www.nav.pt/`
- Static path: `/eAIP_Current/html/en/`
- Prefix: `LP`

---

## Pattern 2: Fragment-Based Navigation

**Countries:** Spain

**Characteristics:**
- URL uses fragments: `aip-en.html#{ICAO}`
- No page reload when navigating
- All content loaded in single page
- Requires filtering by ICAO code

### Implementation Steps

#### Step 1: Construct Fragment URL

```python
def get_airport_fragment_url(icao_code):
    base_url = "https://aip.enaire.es/aip/aip-en.html"
    return f"{base_url}#{icao_code}"
```

#### Step 2: Fetch and Parse (All Airports Loaded)

```python
def get_aerodrome_charts(icao_code):
    # Fetch the main page (contains all airports)
    base_url = "https://aip.enaire.es/aip/aip-en.html"
    response = requests.get(base_url, timeout=30)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    charts = []
    
    # Find all links with PDF icon class
    for icon in soup.find_all('i', class_='far fa-file-pdf'):
        link = icon.find_parent('a')
        if not link or 'href' not in link.attrs:
            continue
        
        href = link['href']
        
        # CRITICAL: Filter by ICAO code
        # Chart URLs contain ICAO: contenido_AIP/AD/AD2/{ICAO}/...pdf
        if icao_code not in href:
            continue
        
        # Get chart name from link text or parent
        chart_name = link.get_text(strip=True)
        if not chart_name:
            # Try parent td or span
            parent = link.find_parent('td')
            if parent:
                chart_name = parent.get_text(strip=True)
        
        full_url = urljoin(base_url, href)
        
        charts.append({
            'name': chart_name,
            'url': full_url,
            'type': categorize_chart(chart_name)
        })
    
    return charts
```

### Key Points

1. **ICAO Filtering is Critical:** The page loads all airports, so you MUST filter by ICAO code
2. **PDF Icon Class:** Look for specific icon classes like `far fa-file-pdf` or `fa-file-pdf-o`
3. **Chart Names:** May be in link text, parent `<td>`, or sibling elements
4. **URL Pattern:** Chart URLs typically contain the ICAO code in the path

### Example Country

**Spain** (`sources/spain_scraper.py`):
- Base: `https://aip.enaire.es/aip/aip-en.html`
- Icon class: `far fa-file-pdf`
- URL pattern: `contenido_AIP/AD/AD2/{ICAO}/LE_AD_2_{ICAO}_...pdf`
- Prefixes: `LE*`, `GC*`, `GE*`, `GS*`

---

## Pattern 3: Static HTML Parsing

**Countries:** FAA (USA), Canada, Brazil

**Characteristics:**
- No JavaScript required
- Chart links visible in HTML source
- Direct PDF URLs in `<a>` tags
- May have search forms or dropdowns

### Implementation Steps

#### Step 1: Construct Search URL

```python
class CountryScraper:
    def __init__(self, verbose=False):
        self.verbose = verbose
        self.base_url = "https://example.com/charts"
    
    def get_charts(self, icao_code):
        # Method A: Direct URL pattern
        search_url = f"{self.base_url}/search?airport={icao_code}"
        
        # Method B: POST form submission
        data = {'airport_code': icao_code, 'search': 'Search'}
        response = requests.post(self.base_url, data=data)
        
        # Method C: Direct airport page
        airport_url = f"{self.base_url}/airport/{icao_code}"
        response = requests.get(airport_url)
```

#### Step 2: Parse Chart Links

```python
def get_charts(self, icao_code):
    charts = []
    response = requests.get(search_url, timeout=30)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Find chart sections or tables
    chart_sections = soup.find_all('div', class_='chart-section')
    
    for section in chart_sections:
        # Extract section type (SID, STAR, etc.)
        section_type = section.find('h3').text.strip()
        
        # Find all PDF links in this section
        for link in section.find_all('a', href=True):
            href = link['href']
            if '.pdf' in href.lower():
                chart_name = link.get_text(strip=True)
                full_url = urljoin(self.base_url, href)
                
                charts.append({
                    'name': chart_name,
                    'url': full_url,
                    'type': self._categorize_chart(chart_name, section_type)
                })
    
    return charts
```

### Common Variations

**Variation 1: Charts in tables**
```python
table = soup.find('table', id='charts-table')
for row in table.find_all('tr')[1:]:  # Skip header
    cells = row.find_all('td')
    chart_name = cells[0].text.strip()
    pdf_link = cells[1].find('a')['href']
```

**Variation 2: Charts in lists**
```python
chart_list = soup.find('ul', class_='chart-list')
for item in chart_list.find_all('li'):
    link = item.find('a', href=True)
    chart_name = link.text.strip()
    chart_url = link['href']
```

**Variation 3: Multiple chart types on one page**
```python
# Look for section headings
sections = soup.find_all('h2', class_='chart-type')
for section in sections:
    chart_type = section.text.strip()
    # Find all links until next h2
    current = section.next_sibling
    while current and current.name != 'h2':
        if current.name == 'a' and '.pdf' in current.get('href', ''):
            # Process link
            pass
        current = current.next_sibling
```

### Example Countries

**FAA (USA)** (`sources/faa_scraper.py`):
- Base: `https://www.faa.gov/air_traffic/flight_info/aeronav/digital_products/dtpp/`
- Class-based scraper
- Search by ICAO code

**Canada** (`sources/canada_scraper.py`):
- Base: NAV Canada website
- Class-based scraper
- Direct airport pages

**Brazil** (`sources/brazil_scraper.py`):
- Base: DECEA (Brazilian Air Force)
- Class-based scraper
- Portuguese chart names

---

## Pattern 4: JSON API

**Countries:** New Zealand, Taiwan, Japan

**Characteristics:**
- Website uses JSON endpoints
- Easy to parse structured data
- No HTML parsing needed
- Usually faster and more reliable

### Implementation Steps

#### Step 1: Discover API Endpoint

**Method:** Use browser DevTools → Network tab
1. Open the AIP website
2. Search for an airport
3. Look for XHR/Fetch requests with JSON responses
4. Copy the request URL and parameters

#### Step 2: Implement JSON Scraper

```python
def get_aerodrome_charts(icao_code):
    # Example: Direct JSON endpoint
    api_url = f"https://api.example.com/aip/airports/{icao_code}/charts"
    
    response = requests.get(api_url, timeout=30)
    data = response.json()
    
    charts = []
    
    # Parse JSON structure
    for chart_data in data.get('charts', []):
        charts.append({
            'name': chart_data['title'],
            'url': chart_data['pdf_url'],
            'type': categorize_chart(chart_data['title'])
        })
    
    return charts
```

### Common JSON Structures

**Structure A: Array of chart objects**
```json
{
  "charts": [
    {
      "id": "123",
      "title": "NZAA Aerodrome Chart",
      "pdf_url": "https://example.com/charts/NZAA_ADC.pdf",
      "type": "ADC"
    }
  ]
}
```

**Structure B: Nested by category**
```json
{
  "airport": "NZAA",
  "categories": {
    "departure": [
      {"name": "SID 1", "url": "..."}
    ],
    "approach": [
      {"name": "ILS RWY 05L", "url": "..."}
    ]
  }
}
```

**Structure C: Flat array with metadata**
```json
[
  {
    "chart_name": "Auckland ADC",
    "document_url": "https://...",
    "chart_type": "aerodrome",
    "icao": "NZAA"
  }
]
```

### Example Countries

**New Zealand** (`sources/new_zealand_scraper_json.py`):
- Uses pre-scraped JSON database
- File: `AIP New Zealand.json`
- Function-based: `get_aerodrome_charts(icao_code)`

**Taiwan** (`sources/taiwan_scraper.py`):
- Direct JSON API
- Function-based scraper
- Returns chart data directly

**Japan** (`sources/japan_scraper.py`):
- JSON-based structure
- Function-based scraper
- Date folder navigation

---

## Pattern 5: JavaScript SPA (Selenium Required)

**Countries:** Argentina, Colombia, Myanmar

**Characteristics:**
- Content loads dynamically via JavaScript
- No chart links in HTML source
- Requires browser automation
- Slower but necessary for SPAs

### Implementation Steps

#### Step 1: Setup Selenium

```python
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

class CountryScraper:
    def __init__(self, verbose=False):
        self.verbose = verbose
        self.base_url = "https://example.com/aip"
    
    def _setup_driver(self):
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")
        
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        return driver
```

#### Step 2: Navigate and Wait for Content

```python
def get_charts(self, icao_code):
    driver = self._setup_driver()
    charts = []
    
    try:
        # Load page
        driver.get(self.base_url)
        time.sleep(3)  # Wait for initial load
        
        # Find and click AD tab if needed
        ad_tab = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//a[contains(text(), 'AD')]"))
        )
        ad_tab.click()
        time.sleep(2)
        
        # Find search input
        search_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='search']"))
        )
        
        # Enter ICAO code
        search_input.clear()
        search_input.send_keys(icao_code)
        time.sleep(3)  # Wait for results
        
        # Extract chart links
        rows = driver.find_elements(By.CSS_SELECTOR, "tr")
        
        for row in rows:
            try:
                name_cell = row.find_element(By.CSS_SELECTOR, "td")
                chart_name = name_cell.text.strip()
                
                if icao_code not in chart_name:
                    continue
                
                download_link = row.find_element(By.CSS_SELECTOR, "a[href*='download']")
                chart_url = download_link.get_attribute('href')
                
                charts.append({
                    'name': chart_name,
                    'url': chart_url,
                    'type': self._categorize_chart(chart_name)
                })
            except:
                continue
    
    finally:
        driver.quit()
    
    return charts
```

### Debugging Tips

1. **Save page source for inspection:**
```python
if self.verbose:
    with open("debug_page.html", "w", encoding="utf-8") as f:
        f.write(driver.page_source)
```

2. **Take screenshots:**
```python
driver.save_screenshot("debug_screenshot.png")
```

3. **Print element counts:**
```python
if self.verbose:
    all_links = driver.find_elements(By.TAG_NAME, "a")
    print(f"Found {len(all_links)} total links")
```

### Example Countries

**Argentina** (`sources/argentina_scraper.py`):
- Base: `https://ais.anac.gob.ar/aip#ad`
- Requires clicking AD tab
- Search input for ICAO code
- Charts in table structure

**Colombia** (`sources/colombia_scraper.py`):
- Selenium-based navigation
- Class-based scraper

**Myanmar** (`sources/myanmar_scraper.py`):
- JavaScript-heavy SPA
- Selenium required

---

## Pattern 6: Pre-scraped JSON Database

**Countries:** Russia, New Zealand (backup method)

**Characteristics:**
- Pre-generated JSON file with all airports
- Fastest method (no network requests)
- Requires periodic updates
- Useful for unreliable/blocked websites

### Implementation Steps

#### Step 1: Create JSON Database Structure

```json
{
  "ICAO_CODE": {
    "name": "Airport Name",
    "charts": [
      {
        "name": "Chart Name",
        "url": "https://example.com/chart.pdf",
        "type": "SID"
      }
    ]
  }
}
```

#### Step 2: Implement Scraper

```python
import json
import os

def get_aerodrome_charts(icao_code):
    # Load JSON database
    json_file = os.path.join(os.path.dirname(__file__), '..', 'AIP_Country.json')
    
    if not os.path.exists(json_file):
        print(f"ERROR: JSON database not found at {json_file}")
        return []
    
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Look up airport
    if icao_code not in data:
        print(f"Airport {icao_code} not found in database")
        return []
    
    airport_data = data[icao_code]
    charts = []
    
    for chart in airport_data['charts']:
        charts.append({
            'name': chart['name'],
            'url': chart['url'],
            'type': chart.get('type', 'General')
        })
    
    return charts
```

#### Step 3: Create Pre-scraper Script

```python
# prescrape_country.py
import json
import requests
from bs4 import BeautifulSoup

def scrape_all_airports():
    """Scrape all airports and save to JSON"""
    database = {}
    
    # Get list of all airports
    airports = get_airport_list()
    
    for icao in airports:
        print(f"Scraping {icao}...")
        charts = scrape_airport_charts(icao)
        
        if charts:
            database[icao] = {
                'name': get_airport_name(icao),
                'charts': charts
            }
    
    # Save to JSON
    with open('AIP_Country.json', 'w', encoding='utf-8') as f:
        json.dump(database, f, indent=2, ensure_ascii=False)
    
    print(f"Saved {len(database)} airports to AIP_Country.json")

if __name__ == "__main__":
    scrape_all_airports()
```

### Example Countries

**Russia** (`sources/russia_scraper.py`):
- JSON file: `AIP Russia.json`
- Fallback for blocked/slow website
- Class-based scraper with JSON option

**New Zealand** (`sources/new_zealand_scraper_json.py`):
- JSON file: `AIP New Zealand.json`
- Primary method (pre-scraped)
- Function-based scraper

---

## Common Chart Categorization Logic

All scrapers should categorize charts into these standard types:

### Standard Categories

1. **SID** - Standard Instrument Departure
2. **STAR** - Standard Terminal Arrival Route
3. **Approach** - Instrument Approach Procedures (IAP)
4. **Airport Diagram** - Ground movement, parking, aerodrome charts
5. **General** - Minimums, procedures, legends, other

### Implementation

```python
def categorize_chart(chart_name):
    """
    Categorize chart based on its name.
    Add language-specific keywords as needed.
    """
    chart_name_upper = chart_name.upper()
    chart_name_lower = chart_name.lower()
    
    # SID - Departures (English + Spanish + Portuguese + French)
    if any(keyword in chart_name_lower for keyword in [
        'sid', 'standard instrument departure',
        'salida', 'departure', 'partida',
        'saída normalizada', 'sortie'
    ]):
        return 'SID'
    
    # STAR - Arrivals
    if any(keyword in chart_name_lower for keyword in [
        'star', 'standard terminal arrival', 'standard arrival',
        'llegada', 'arrival', 'arribo',
        'chegada normalizada', 'arrivée'
    ]):
        return 'STAR'
    
    # Approach procedures
    if any(keyword in chart_name_lower for keyword in [
        'approach', 'iap', 'iac',
        'aproximación', 'aproximacion', 'aproximação',
        'ils', 'rnav', 'vor', 'ndb', 'loc', 'rnp', 'gps',
        'precision approach', 'instrument approach'
    ]):
        return 'Approach'
    
    # Airport diagrams
    if any(keyword in chart_name_lower for keyword in [
        'aerodrome chart', 'airport diagram', 'airport chart',
        'plano de aeródromo', 'plano de aerodromo',
        'ground movement', 'taxi', 'parking', 'apron',
        'movimientos en tierra', 'estacionamiento',
        'adc', 'pdc', 'gmc', 'aoc', 'patc'  # Chart code abbreviations
    ]):
        return 'Airport Diagram'
    
    # Default to General
    return 'General'
```

### Language-Specific Keywords

**Spanish:**
- SID: `salida`, `salida normalizada`
- STAR: `llegada`, `llegada normalizada`
- Approach: `aproximación`, `aproximacion`, `precisión`
- Ground: `plano`, `estacionamiento`, `movimientos en tierra`

**Portuguese:**
- SID: `saída`, `saída normalizada`
- STAR: `chegada`, `chegada normalizada`
- Approach: `aproximação`, `aproximacao`
- Ground: `plano`, `estacionamento`, `movimentação`

**French:**
- SID: `départ`, `départ normalisé`, `sortie`
- STAR: `arrivée`, `arrivée normalisée`
- Approach: `approche`
- Ground: `carte`, `parking`, `circulation au sol`

---

## Testing and Validation

### Test Checklist

After implementing a scraper, test with these airports:

1. **Major hub airport** - Should have 50+ charts
2. **Small airport** - Should have 5-15 charts
3. **Airport with special characters** - Test URL encoding

### Test Script

```python
# test_scraper.py
import sys
from sources.country_scraper import get_aerodrome_charts

def test_airport(icao_code):
    print(f"\nTesting {icao_code}...")
    
    try:
        charts = get_aerodrome_charts(icao_code)
        
        if not charts:
            print(f"  ❌ No charts found")
            return False
        
        print(f"  ✅ Found {len(charts)} charts")
        
        # Check categories
        categories = {}
        for chart in charts:
            cat = chart.get('type', 'Unknown')
            categories[cat] = categories.get(cat, 0) + 1
        
        print(f"  Categories: {categories}")
        
        # Check URLs
        for chart in charts[:3]:  # Test first 3
            print(f"    - {chart['name']}")
            print(f"      {chart['url']}")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_scraper.py ICAO1 ICAO2 ...")
        sys.exit(1)
    
    for icao in sys.argv[1:]:
        test_airport(icao.upper())
```

### Validation Points

1. **URL validity:** All URLs should be accessible (200 status)
2. **Chart names:** Should not be empty or generic
3. **ICAO filtering:** Should only return charts for requested airport
4. **Categorization:** All charts should have a type
5. **URL encoding:** Special characters should be properly encoded
6. **Relative URLs:** Should be converted to absolute URLs

---

## Integration Checklist

After implementing a new scraper, integrate it into the main CLI:

### Step 1: Add Import

```python
# At top of aerodrome_charts_cli.py
from sources.country_scraper import get_aerodrome_charts as get_country_charts
```

### Step 2: Add to Source Choices

```python
parser.add_argument('-s', '--source',
                   choices=[..., 'country_name'],  # Add here
                   default=None,
                   help='Chart source (default: auto-detect from ICAO code)')
```

### Step 3: Add ICAO Prefix Detection

```python
# In main(), add ICAO prefix mapping
if icao_code.startswith('XX'):  # Replace XX with actual prefix
    # Country uses XX* prefixes (XXAA, XXBB, etc.)
    args.source = 'country_name'
```

### Step 4: Add Scraper Execution

```python
elif args.source == 'country_name':
    # Country scraper returns charts directly
    charts = get_country_charts(icao_code)
    if not charts:
        print(f"\n❌ No charts found for {icao_code}")
        sys.exit(1)
    display_charts(charts)
    print("\n" + "="*80)
    print(f"✅ Found {len(charts)} total charts")
    print("="*80 + "\n")
    return
```

### Step 5: Update Documentation

Add country information to `.github/copilot-instructions.md`:

```markdown
### Countries Using [Pattern Name]

**Country Name** (`sources/country_scraper.py`):
- Base: https://example.com/aip/
- Pattern: [Pattern description]
- Prefix: XX*
- Example airports: XXAA, XXBB
```

---

## LLM Automation Workflow

When given a new AIP website URL, follow this workflow:

### Phase 1: Analysis (5-10 minutes)

1. **Open URL in browser**
   - Note the structure and navigation
   - Try searching for an airport (use common ICAO codes)
   - Check if it's similar to existing patterns

2. **Determine pattern type**
   - Use the Quick Decision Tree at the top
   - Identify which pattern is closest match

3. **Inspect elements**
   - Open DevTools (F12)
   - Find where chart links are located
   - Check Network tab for API calls
   - View page source for static HTML

### Phase 2: Implementation (15-30 minutes)

1. **Create scraper file**
   - Use pattern template as starting point
   - Name: `sources/country_name_scraper.py`
   - Implement `get_aerodrome_charts(icao_code)` function

2. **Find ICAO prefix(es)**
   - Look up country's ICAO prefixes
   - Common patterns: 2-letter prefix (e.g., LE* for Spain)
   - Some countries have multiple prefixes

3. **Implement specific details**
   - Base URL
   - Navigation steps
   - Chart extraction logic
   - Categorization (add language-specific keywords)

### Phase 3: Testing (5-10 minutes)

1. **Test with test script**
   - Use 2-3 airports of different sizes
   - Verify chart counts seem reasonable
   - Check URL validity

2. **Integrate into CLI**
   - Follow Integration Checklist
   - Test auto-detection
   - Verify output formatting

### Phase 4: Documentation (5 minutes)

1. **Update `.github/copilot-instructions.md`**
   - Add country to appropriate pattern section
   - Document any unique characteristics
   - List example airports

2. **Test edge cases**
   - Special characters in chart names
   - Multiple chart types
   - Large and small airports

---

## Quick Reference Table

| Country | Pattern | Base URL | ICAO Prefix | Selenium? |
|---------|---------|----------|-------------|-----------|
| Albania | Eurocontrol | https://www.albcontrol.al/aip/ | LA* | No |
| Argentina | JavaScript SPA | https://ais.anac.gob.ar/aip | SA*, SC*, SE*, SG*, SL*, SO*, SU*, SV*, SY* | Yes |
| Armenia | Eurocontrol | - | UD* | No |
| Australia | Static HTML | - | Y* | No |
| Belarus | Eurocontrol | https://www.ban.by | UM* | No |
| Bosnia | Eurocontrol | - | LQ* | No |
| Brazil | Static HTML | - | SB*, SD*, SI*, SJ*, SN*, SS*, SW* | No |
| Canada | Static HTML | - | CY*, CZ* | No |
| China | Static HTML | - | Z* | No |
| Colombia | JavaScript SPA | - | SK* | Yes |
| Czech Republic | Eurocontrol | - | LK* | No |
| Hungary | Eurocontrol | - | LH* | No |
| India | Static HTML | - | VA*, VE*, VI*, VO* | No |
| Japan | JSON API | - | RJ* | No |
| Kazakhstan | Static HTML | - | UA* | No |
| Kyrgyzstan | Static HTML | - | UC* | No |
| Myanmar | JavaScript SPA | - | VY* | Yes |
| New Zealand | JSON Database | - | NZ* | No |
| Portugal | Eurocontrol | https://www.nav.pt/ | LP* | No |
| Romania | Eurocontrol | https://aisro.ro/aip/ | LR* | No |
| Russia | JSON Database | - | U* (most) | No |
| Serbia | Eurocontrol | https://smatsa.rs/upload/aip/published/ | LY* | No |
| Slovenia | Eurocontrol | - | LJ* | No |
| South Korea | Static HTML | - | RK* | No |
| Spain | Fragment Navigation | https://aip.enaire.es/aip/ | LE*, GC*, GE*, GS* | No |
| Taiwan | JSON API | - | RC* | No |
| Thailand | Static HTML | - | VT* | No |
| USA (FAA) | Static HTML | - | K* | No |
| Uruguay | Static HTML | - | SU* | No |

---

## Common Issues and Solutions

### Issue 1: 404 Errors on Chart URLs

**Symptoms:** Scraper finds chart names but URLs return 404

**Solutions:**
1. Check if URLs are relative → use `urljoin(base_url, href)`
2. Check URL encoding → use `quote()` on filename only
3. Check if base URL includes date folder → extract dynamically
4. Check if PDFs are in different directory → adjust path construction

### Issue 2: No Charts Found

**Symptoms:** Scraper returns empty list

**Solutions:**
1. Check if content is JavaScript-loaded → use Selenium
2. Check selector specificity → relax CSS selectors
3. Check if ICAO filtering is too strict → verify ICAO in URL/name
4. Check if page structure changed → re-inspect HTML

### Issue 3: Wrong Charts Returned

**Symptoms:** Charts from wrong airport included

**Solutions:**
1. Add ICAO code filtering → `if icao_code not in href: continue`
2. Check section boundaries → ensure scraping correct div/section
3. Check unique identifiers → use data attributes or IDs

### Issue 4: Special Characters in URLs

**Symptoms:** URLs with spaces or accents fail

**Solutions:**
```python
from urllib.parse import quote

# URL encode filename only (not entire path)
url_parts = full_url.rsplit('/', 1)
if len(url_parts) == 2:
    base_path, filename = url_parts
    encoded_filename = quote(filename, safe='')
    full_url = f"{base_path}/{encoded_filename}"
```

### Issue 5: Categorization Incorrect

**Symptoms:** Charts labeled with wrong category

**Solutions:**
1. Add language-specific keywords to `categorize_chart()`
2. Check for country-specific abbreviations (e.g., ADC, PDC, GMC)
3. Add explicit AIP section codes (e.g., AD-2.i for SID)

---

## Examples by Pattern

### Example 1: Implementing Eurocontrol Scraper

Given URL: `https://ais.example.com/eaip/`

```python
#!/usr/bin/env python3
"""
Country X eAIP Scraper
Scrapes aerodrome charts from Country X AIP following Eurocontrol structure
"""

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote
import re

BASE_URL = "https://ais.example.com"

def get_latest_eaip_url():
    """Get the URL of the latest Country X eAIP"""
    try:
        response = requests.get(f"{BASE_URL}/eaip/index.html", timeout=30)
        soup = BeautifulSoup(response.text, 'lxml')
        
        # Find latest AIRAC date link
        for link in soup.find_all('a', href=True):
            href = link['href']
            if 'AIRAC' in href and 'html/index' in href:
                # Extract date folder
                match = re.search(r'([0-9]{4}-[0-9]{2}-[0-9]{2}-AIRAC)', href)
                if match:
                    date_folder = match.group(1)
                    return f"{BASE_URL}/eaip/{date_folder}/html/eAIP/"
        
        return None
    except Exception as e:
        print(f"Error getting latest eAIP URL: {e}")
        return None

def get_airport_page_url(icao_code):
    """Get the URL for a specific airport's AD 2 page"""
    base_eaip = get_latest_eaip_url()
    if not base_eaip:
        return None
    
    # Format: XX-AD-2.ICAO-en-GB.html (XX is ICAO country prefix)
    prefix = icao_code[:2]  # Extract prefix from ICAO
    airport_page = f"{prefix}-AD-2.{icao_code}-en-GB.html"
    return urljoin(base_eaip, airport_page)

def categorize_chart(chart_name):
    """Categorize chart based on its name"""
    chart_name_upper = chart_name.upper()
    
    if 'SID' in chart_name_upper or 'DEPARTURE' in chart_name_upper:
        return 'SID'
    elif 'STAR' in chart_name_upper or 'ARRIVAL' in chart_name_upper:
        return 'STAR'
    elif any(kw in chart_name_upper for kw in ['APPROACH', 'ILS', 'LOC', 'NDB', 'RNP', 'RNAV']):
        return 'Approach'
    elif any(kw in chart_name_upper for kw in ['AERODROME CHART', 'GROUND', 'PARKING', 'TAXI']):
        return 'Airport Diagram'
    else:
        return 'General'

def get_aerodrome_charts(icao_code):
    """Get all aerodrome charts for a given ICAO code"""
    charts = []
    
    try:
        airport_url = get_airport_page_url(icao_code)
        if not airport_url:
            return charts
        
        response = requests.get(airport_url, timeout=30)
        soup = BeautifulSoup(response.text, 'lxml')
        
        # Find all PDF links
        for link in soup.find_all('a', href=True):
            href = link['href']
            if '.pdf' not in href.lower():
                continue
            
            # Get chart name from previous row or same row
            td_parent = link.find_parent('td')
            if td_parent:
                tr_parent = td_parent.find_parent('tr')
                prev_row = tr_parent.find_previous_sibling('tr')
                
                if prev_row:
                    name_td = prev_row.find('td')
                    if name_td:
                        chart_name = name_td.get_text(strip=True)
                        
                        # Build full URL
                        full_url = urljoin(airport_url, href)
                        
                        # URL encode filename
                        url_parts = full_url.rsplit('/', 1)
                        if len(url_parts) == 2:
                            base_path, filename = url_parts
                            encoded_filename = quote(filename, safe='')
                            full_url = f"{base_path}/{encoded_filename}"
                        
                        charts.append({
                            'name': chart_name,
                            'url': full_url,
                            'type': categorize_chart(chart_name)
                        })
        
        return charts
    
    except Exception as e:
        print(f"Error scraping {icao_code}: {e}")
        return charts

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python country_scraper.py <ICAO_CODE>")
        sys.exit(1)
    
    icao = sys.argv[1].upper()
    charts = get_aerodrome_charts(icao)
    
    if charts:
        print(f"\nFound {len(charts)} charts for {icao}:")
        for chart in charts:
            print(f"  [{chart['type']}] {chart['name']}")
            print(f"    {chart['url']}")
    else:
        print(f"No charts found for {icao}")
```

---

## Final Notes

- Always test with multiple airports before considering implementation complete
- Document any country-specific quirks in comments
- Keep scraper code clean and maintainable
- Add error handling for network issues
- Consider rate limiting for bulk scraping
- Respect robots.txt and terms of service

**Version:** 1.0  
**Last Updated:** January 24, 2026  
**Maintained by:** Aerodrome Charts CLI Project

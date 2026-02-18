"""
Taiwan eAIP scraper - dynamically fetches current AIRAC and extracts aerodrome charts.
"""

import requests
from bs4 import BeautifulSoup
from urllib.parse import quote
import re
import urllib3

# Disable SSL warnings for Taiwan eAIP (certificate issues)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def get_current_airac():
    """Fetch the current effective AIRAC information from Taiwan eAIP."""
    try:
        response = requests.get("https://ais.caa.gov.tw/eaip/", timeout=30, verify=False)
        soup = BeautifulSoup(response.text, 'lxml')
        
        # Find "Currently Effective Issue" section
        # Look for the table with effective date
        tables = soup.find_all('table')
        
        for table in tables:
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all('td')
                if len(cells) >= 3:
                    effective_date = cells[0].get_text(strip=True)
                    reason = cells[2].get_text(strip=True)
                    
                    # Check if this is an AIRAC amendment
                    if 'AIRAC AIP AMDT' in reason:
                        # Extract amendment number (e.g., "06/25" from "AIRAC AIP AMDT 06/25")
                        amdt_match = re.search(r'AIRAC AIP AMDT (\d+/\d+)', reason)
                        if amdt_match:
                            amdt = amdt_match.group(1)  # e.g., "06/25"
                            
                            # Parse date (e.g., "25 DEC 2025")
                            date_parts = effective_date.split()
                            if len(date_parts) == 3:
                                day = date_parts[0]
                                month = date_parts[1]
                                year = date_parts[2]
                                
                                # Convert month to number
                                months = {'JAN': '01', 'FEB': '02', 'MAR': '03', 'APR': '04',
                                         'MAY': '05', 'JUN': '06', 'JUL': '07', 'AUG': '08',
                                         'SEP': '09', 'OCT': '10', 'NOV': '11', 'DEC': '12'}
                                month_num = months.get(month.upper(), '01')
                                
                                # Construct URL components (use dash not slash in folder name)
                                airac_folder = f"AIRAC AIP AMDT {amdt.replace('/', '-')}_{year}_{month_num}_{day}"
                                
                                return airac_folder
        
        return None
        
    except Exception as e:
        return None

def get_base_url(airac_folder):
    """Construct the base URL for the current AIRAC."""
    # URL encode only the folder name, not the slashes
    encoded_folder = quote(airac_folder, safe='')
    base_url = f"https://ais.caa.gov.tw/eaip/{encoded_folder}"
    return base_url

def get_airport_filename(icao_code, airac_folder):
    """Get the filename for a specific airport from the menu."""
    base_url = get_base_url(airac_folder)
    
    # Fetch the menu.html which contains airport links
    menu_url = f"{base_url}/eAIP/menu.html"
    
    try:
        response = requests.get(menu_url, timeout=30, verify=False)
        if response.status_code != 200:
            return None
        
        soup = BeautifulSoup(response.text, 'lxml')
        
        # Look for link matching this specific ICAO code
        # Pattern: RC-AD 2 {ICAO} {Name}-en-GB.html
        links = soup.find_all('a', href=lambda h: h and f'RC-AD 2 {icao_code}' in h and '-en-GB.html' in h)
        
        if links:
            href = links[0].get('href')
            # Remove anchor from filename (everything after #)
            filename = href.split('#')[0]
            return filename
        
        return None
        
    except Exception as e:
        print(f"❌ Error fetching airport filename: {e}")
        return None

def categorize_chart(chart_name):
    """Categorize a chart based on its name."""
    name_lower = chart_name.lower()
    
    # SID - Standard Instrument Departure
    if 'sid' in name_lower or 'departure' in name_lower:
        return 'SID'
    
    # STAR - Standard Terminal Arrival
    if 'star' in name_lower or 'arrival' in name_lower:
        return 'STAR'
    
    # Approach charts
    if any(keyword in name_lower for keyword in ['approach', 'ils', 'rnav', 'vor', 'ndb', 'rnp', 'gnss', 'visual apch']):
        return 'Approach'
    
    # Airport diagrams
    if any(keyword in name_lower for keyword in ['aerodrome chart', 'airport', 'parking', 'taxi', 'apron', 'ground movement', 'obstruction']):
        return 'Airport Diagram'
    
    # Noise abatement
    if 'noise' in name_lower:
        return 'Noise Abatement'
    
    # Heliport
    if 'heliport' in name_lower or 'helicopter' in name_lower:
        return 'Heliport'
    
    # Default
    return 'General'

def get_all_airports(airac_folder):
    """Get list of all airports from AD 2 section (for listing purposes)."""
    base_url = get_base_url(airac_folder)
    
    # Fetch the menu.html which contains airport links
    menu_url = f"{base_url}/eAIP/menu.html"
    
    print(f"🔍 Fetching airport list from: {menu_url}")
    
    try:
        response = requests.get(menu_url, timeout=30, verify=False)
        if response.status_code != 200:
            return {}
        
        soup = BeautifulSoup(response.text, 'lxml')
        airports = {}
        
        # Look for links to individual airports: 'RC-AD 2 RCXX ....-en-GB.html'
        # Pattern: RC-AD 2 {ICAO} {Name}-en-GB.html
        links = soup.find_all('a', href=lambda h: h and 'RC-AD 2 RC' in h and '-en-GB.html' in h)
        
        for link in links:
            href = link.get('href')
            text = link.get_text(strip=True)
            
            # Extract ICAO from href (e.g., RC-AD 2 RCTP ...-en-GB.html -> RCTP)
            match = re.search(r'RC-AD 2 (RC[A-Z]{2})', href)
            if match:
                icao = match.group(1)
                if icao not in airports:  # Avoid duplicates
                    # Remove anchor from filename (everything after #)
                    filename = href.split('#')[0]
                    airports[icao] = {
                        'name': text if text else icao,
                        'icao': icao,
                        'filename': filename
                    }
        
        return airports
        
    except Exception as e:
        print(f"❌ Error fetching airport list: {e}")
        return {}

def get_aerodrome_charts(icao_code):
    """
    Fetch aerodrome charts for a Taiwan airport.
    Taiwan uses RC** ICAO codes (RCTP, RCSS, RCFG, etc.)
    """
    
    # Get current AIRAC
    airac_folder = get_current_airac()
    if not airac_folder:
        return []
    
    # Get the filename for this specific airport only
    airport_filename = get_airport_filename(icao_code, airac_folder)
    if not airport_filename:
        return []
    
    base_url = get_base_url(airac_folder)
    
    # Construct full URL to airport page
    ad_url = f"{base_url}/eAIP/{quote(airport_filename, safe='')}" 
    
    try:
        response = requests.get(ad_url, timeout=30, verify=False)
        if response.status_code != 200:
            return []
        
        soup = BeautifulSoup(response.text, 'lxml')
        
        # Find charts section - typically AD 2.24 (Charts and Related Data)
        charts = []
        
        # Look for links to PDF files - they're in <a class="ulink" href="...pdf">
        links = soup.find_all('a', {'class': 'ulink', 'href': lambda h: h and '.pdf' in h.lower()})
        
        for link in links:
            href = link.get('href')
            
            # Try to find text - it's usually in a preceding or following span
            text = link.get_text(strip=True)
            if not text:
                # Look for nearby span with text
                parent = link.parent
                if parent:
                    spans = parent.find_all('span', class_='T2_default')
                    if spans:
                        text = spans[0].get_text(strip=True)
            
            if not text:
                # Use filename as fallback
                text = href.split('/')[-1].replace('.pdf', '').replace('-', ' ')
            
            if href:
                # Make absolute URL
                if not href.startswith('http'):
                    if href.startswith('/'):
                        href = f"https://ais.caa.gov.tw{href}"
                    else:
                        # Relative URLs - href is like ../documents/Root/...
                        # We're in eAIP folder, ../ means go up to base folder
                        while href.startswith('../'):
                            href = href[3:]  # Remove ../
                        # URL encode the path
                        href = f"{base_url}/{quote(href, safe='/')}"
                
                charts.append({
                    'name': text,
                    'url': href,
                    'type': categorize_chart(text)
                })
        
        return charts
        
    except Exception as e:
        return []

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python taiwan_scraper.py <ICAO_CODE>")
        print("Example: python taiwan_scraper.py RCTP")
        sys.exit(1)
    
    icao_code = sys.argv[1].upper()
    
    charts = get_aerodrome_charts(icao_code)
    
    if charts:
        # Group by category
        categories = {}
        for chart in charts:
            cat = chart['type']
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(chart)
        
        # Print categorized results
        for category in sorted(categories.keys()):
            print(f"\n{category}:")
            for chart in categories[category]:
                print(f"  {chart['name']}")
                print(f"    {chart['url']}")
    else:
        print(f"No charts found for {icao_code}")
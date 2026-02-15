import requests
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
import re
from urllib.parse import urljoin
import warnings

# Suppress XML parsing warnings for eAIP pages
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)


class ThailandScraper:
    def __init__(self, verbose=False):
        self.base_url = "https://aip.caat.or.th"
        self.verbose = verbose

    def _get_current_airac_date(self):
        """Get the currently effective AIRAC date from the history page."""
        try:
            response = requests.get(f"{self.base_url}/", timeout=30)
            response.raise_for_status()
            
            # Look for links in the format: "2025-12-25-AIRAC/html/index-en-GB.html"
            pattern = r'(\d{4}-\d{2}-\d{2}-AIRAC)/html/index-en-GB\.html'
            matches = re.findall(pattern, response.text)
            
            if matches:
                airac_date = matches[0]  # First one is the currently effective
                if self.verbose:
                    print(f"[DEBUG] Found AIRAC date: {airac_date}")
                return airac_date
            else:
                if self.verbose:
                    print("[DEBUG] No AIRAC date found, using fallback")
                return "2025-12-25-AIRAC"  # Fallback
        except Exception as e:
            if self.verbose:
                print(f"[DEBUG] Error getting AIRAC date: {e}")
            return "2025-12-25-AIRAC"  # Fallback

    def get_charts(self, icao_code):
        """Fetch aerodrome charts for the given ICAO code."""
        charts = []
        
        # Get current AIRAC date
        airac_date = self._get_current_airac_date()
        
        # Construct menu URL
        menu_url = f"{self.base_url}/{airac_date}/html/eAIP/VT-menu-en-GB.html"
        
        try:
            # Fetch the menu page
            response = requests.get(menu_url, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'lxml')
            
            # Find the aerodrome URL in the menu
            # Looking for links like: VT-AD-2.VTBD-en-GB.html
            aerodrome_url = None
            for link in soup.find_all('a', href=True):
                href = link['href']
                if f'AD-2.{icao_code}' in href and 'en-GB.html' in href:
                    aerodrome_url = urljoin(menu_url, href)
                    if self.verbose:
                        print(f"[DEBUG] Found aerodrome URL: {aerodrome_url}")
                    break
            
            if not aerodrome_url:
                if self.verbose:
                    print(f"[DEBUG] Aerodrome URL not found in menu for {icao_code}")
                return charts
            
            # Fetch the aerodrome page
            response = requests.get(aerodrome_url, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'lxml')
            
            # Check for iframes (like Myanmar and India)
            all_soups = [soup]
            iframes = soup.find_all('iframe')
            if self.verbose:
                print(f"[DEBUG] Found {len(iframes)} iframes")
            
            for iframe in iframes:
                if 'src' in iframe.attrs:
                    iframe_url = urljoin(aerodrome_url, iframe['src'])
                    try:
                        iframe_response = requests.get(iframe_url, timeout=30)
                        iframe_response.raise_for_status()
                        iframe_soup = BeautifulSoup(iframe_response.content, 'lxml')
                        all_soups.append(iframe_soup)
                    except Exception as e:
                        if self.verbose:
                            print(f"[DEBUG] Error fetching iframe {iframe_url}: {e}")
            
            # Search for AD 2.24 section across all soups
            search_area = None
            for current_soup in all_soups:
                # Look for div with id containing "AD-2.24"
                for div in current_soup.find_all('div', id=True):
                    if 'AD-2.24' in div.get('id', ''):
                        search_area = div
                        if self.verbose:
                            print(f"[DEBUG] Found AD 2.24 section by div id: {div.get('id')}")
                        break
                
                if search_area:
                    break
            
            # If not found by div id, try searching by heading text
            if not search_area:
                for current_soup in all_soups:
                    for heading in current_soup.find_all(['h1', 'h2', 'h3', 'h4']):
                        if heading.get_text() and 'AD 2.24' in heading.get_text() and 'CHART' in heading.get_text().upper():
                            # Found the heading, get the parent div
                            search_area = heading.find_parent('div')
                            if self.verbose:
                                print(f"[DEBUG] Found AD 2.24 section by heading: {heading.get_text()[:100]}")
                            break
                    
                    if search_area:
                        break
            
            if not search_area:
                if self.verbose:
                    print("[DEBUG] AD 2.24 section not found")
                return charts
            
            # Debug: count links
            if self.verbose:
                all_links = search_area.find_all('a', href=True)
                pdf_links = [link for link in all_links if '.pdf' in link.get('href', '').lower()]
                print(f"[DEBUG] Search area has {len(all_links)} total links, {len(pdf_links)} PDF links")
            
            # Find all PDF links in the search area (not just in tables - Myanmar pattern)
            for link in search_area.find_all('a', href=True):
                href = link.get('href', '')
                
                if '.pdf' in href.lower():
                    # Extract filename from href
                    filename = href.split('/')[-1]
                    
                    # Get the chart description from the table row
                    # The link text is just the page number, so look for the previous <td> with description
                    td_with_link = link.find_parent('td')
                    if td_with_link:
                        tr = td_with_link.find_parent('tr')
                        if tr:
                            # Get all td elements in the row
                            tds = tr.find_all('td')
                            if len(tds) >= 2:
                                # First td usually has the chart description
                                description = tds[0].get_text(strip=True)
                                name = f"{description} - {link.get_text(strip=True)}"
                            else:
                                name = link.get_text(strip=True)
                        else:
                            name = link.get_text(strip=True)
                    else:
                        name = link.get_text(strip=True)
                    
                    # Fallback to filename if name is empty
                    if not name or name.lower() in ['pdf', 'click here']:
                        name = filename
                    
                    # Build absolute URL
                    pdf_url = urljoin(aerodrome_url, href)
                    
                    # Categorize the chart (use description for better accuracy)
                    category = self._categorize_chart(name, filename)
                    
                    charts.append({
                        'name': name,
                        'url': pdf_url,
                        'category': category
                    })
            
            if self.verbose:
                print(f"[DEBUG] Found {len(charts)} charts total")
            
            return charts
            
        except requests.exceptions.RequestException as e:
            if self.verbose:
                print(f"[DEBUG] Request error: {e}")
            return charts

    def _categorize_chart(self, name, filename=None):
        """Categorize the chart based on its name or filename."""
        text = (name + ' ' + (filename or '')).upper()
        
        # Check for SID/STAR first (most specific)
        if 'SID' in text or 'STAR' in text or 'DEPARTURE' in text or 'ARRIVAL' in text:
            return 'SID' if 'SID' in text or 'DEPARTURE' in text else 'STAR'
        
        # Check for approach charts
        if any(keyword in text for keyword in ['APP', 'APPROACH', 'ILS', 'VOR', 'NDB', 'RNP', 'RNAV', 'VIS']):
            return 'APP'
        
        # Check for ground/parking charts
        if any(keyword in text for keyword in ['PARK', 'GROUND', 'APRON', 'STAND', 'TAXI']):
            return 'GND'
        
        # Check for general charts (aerodrome layout, location, etc.)
        if any(keyword in text for keyword in ['LAYOUT', 'LOCATION', 'ADC', 'AERODROME CHART', 'OBSTACLE', 'TERRAIN']):
            return 'GEN'
        
        # Default to GND for anything else
        return 'GND'


def get_aerodrome_charts(icao_code):
    """Wrapper function for compatibility with function-based interface."""
    scraper = ThailandScraper(verbose=False)
    return scraper.get_charts(icao_code)

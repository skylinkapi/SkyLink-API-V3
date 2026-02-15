import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin, quote

class IndiaScraper:
    """Scraper for India AIM eAIP (https://aim-india.aai.aero/)"""
    
    def __init__(self, verbose=False):
        self.base_url = "https://aim-india.aai.aero"
        self.verbose = verbose
        self.eaip_index_url = self._get_current_eaip_index_url()
    
    def _get_current_eaip_index_url(self):
        """Get the URL to the current eAIP index page"""
        try:
            if self.verbose:
                print(f"[DEBUG] Fetching eAIP index from {self.base_url}")
            
            response = requests.get(self.base_url, timeout=30, verify=False)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Look for eAIP link pattern: /eaip/eaip-v2-XX-YYYY/index-en-GB.html
            # Find the first (most recent) eAIP link - usually marked with class="new"
            for link in soup.find_all('a', href=True):
                href = link['href']
                # Match pattern like /eaip/eaip-v2-01-2026/index-en-GB.html
                if 'eaip' in href and 'index-en-GB.html' in href:
                    # Build full URL
                    if href.startswith('http'):
                        eaip_url = href
                    else:
                        eaip_url = urljoin(self.base_url, href)
                    
                    if self.verbose:
                        print(f"[DEBUG] Found eAIP index URL: {eaip_url}")
                    
                    return eaip_url
            
            raise Exception("Could not find eAIP index URL")
        except Exception as e:
            print(f"Error getting eAIP index URL: {e}")
            # Fallback to a reasonable default
            return f"{self.base_url}/eaip/eaip-v2-01-2026/index-en-GB.html"
    
    def get_charts(self, icao_code):
        """Get aerodrome charts for the given ICAO code"""
        # Extract the eAIP version directory from the index URL
        # e.g., https://aim-india.aai.aero/eaip/eaip-v2-01-2026/index-en-GB.html
        # -> https://aim-india.aai.aero/eaip/eaip-v2-01-2026/eAIP/
        
        base_eaip = self.eaip_index_url.rsplit('/index-en-GB.html', 1)[0]
        
        # Try different URL patterns for the aerodrome page
        # Pattern 1: IN-AD 2.{ICAO}-en-GB.html
        # Pattern 2: IN-AD 2.1{ICAO}-en-GB.html
        
        url_patterns = [
            f"{base_eaip}/eAIP/IN-AD%202.{icao_code}-en-GB.html",
            f"{base_eaip}/eAIP/IN-AD%202.1{icao_code}-en-GB.html",
            f"{base_eaip}/html/eAIP/IN-AD%202.{icao_code}-en-GB.html",
            f"{base_eaip}/html/eAIP/IN-AD%202.1{icao_code}-en-GB.html",
        ]
        
        aerodrome_url = None
        for url in url_patterns:
            if self.verbose:
                print(f"[DEBUG] Trying URL: {url}")
            try:
                response = requests.get(url, timeout=30, verify=False)
                if response.status_code == 200:
                    aerodrome_url = url
                    if self.verbose:
                        print(f"[DEBUG] Success! Using: {aerodrome_url}")
                    break
            except:
                continue
        
        if not aerodrome_url:
            print(f"Could not find aerodrome page for {icao_code} - tried all URL patterns")
            return []
        
        try:
            response = requests.get(aerodrome_url, timeout=30, verify=False)
            response.raise_for_status()
            
            if self.verbose:
                print(f"[DEBUG] Got response, parsing HTML...")
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Debug: save HTML if verbose
            if self.verbose:
                with open(f"debug_{icao_code}.html", "wb") as f:
                    f.write(response.content)
                print(f"[DEBUG] Saved HTML to debug_{icao_code}.html")
            
            # Check if page uses iframes (common in eAIP)
            iframes = soup.find_all('iframe', src=True)
            if iframes and self.verbose:
                print(f"[DEBUG] Found {len(iframes)} iframes")
            
            # If there are iframes, fetch their content too
            all_soups = [soup]
            base_dir = aerodrome_url.rsplit('/', 1)[0]
            
            for iframe in iframes:
                iframe_src = iframe['src']
                iframe_url = urljoin(base_dir + '/', iframe_src)
                if self.verbose:
                    print(f"[DEBUG] Fetching iframe: {iframe_url}")
                try:
                    iframe_response = requests.get(iframe_url, timeout=30, verify=False)
                    iframe_response.raise_for_status()
                    iframe_soup = BeautifulSoup(iframe_response.content, 'html.parser')
                    all_soups.append(iframe_soup)
                except Exception as e:
                    if self.verbose:
                        print(f"[DEBUG] Failed to fetch iframe: {e}")
            
            charts = []
            seen_names = set()
            
            # Search for PDF links in all soups (main page + iframes)
            table_count = 0
            pdf_count = 0
            for soup_item in all_soups:
                for table in soup_item.find_all('table'):
                    table_count += 1
                    for link in table.find_all('a', href=True):
                        href = link['href']
                        pdf_count += 1
                        if self.verbose and pdf_count <= 5:
                            print(f"[DEBUG] Found link in table: {href}")
                        
                        if '.pdf' in href.lower():
                            # Get the filename from href
                            filename = href.split('/')[-1]
                            
                            # Get name from link text, fallback to filename
                            name = link.get_text(strip=True)
                            if not name or name == filename:
                                name = filename
                            
                            # Remove .pdf extension for cleaner name
                            if name.endswith('.pdf'):
                                name = name[:-4]
                            
                            # Skip duplicates
                            if name in seen_names:
                                continue
                            seen_names.add(name)
                            
                            # Build absolute URL
                            # PDFs are relative to the aerodrome page directory
                            pdf_url = f"{base_dir}/{filename}"
                            
                            category = self._categorize_chart(name, filename)
                            
                            if self.verbose and len(charts) < 3:
                                print(f"[DEBUG] Added chart: {name} -> {category}")
                            
                            charts.append({
                                'name': name,
                                'url': pdf_url,
                                'category': category
                            })
            
            if self.verbose:
                print(f"[DEBUG] Processed {table_count} tables, found {len(charts)} charts")
            
            return charts
        except Exception as e:
            print(f"Error fetching charts for {icao_code}: {e}")
            if self.verbose:
                import traceback
                traceback.print_exc()
            return []
    
    def _categorize_chart(self, name, filename):
        """Categorize chart based on name/filename"""
        name_upper = name.upper()
        filename_upper = filename.upper()
        combined = name_upper + ' ' + filename_upper
        
        # SID
        if any(keyword in combined for keyword in [
            'SID', 'DEPARTURE', 'STANDARD INSTRUMENT DEPARTURE'
        ]):
            return 'SID'
        
        # STAR
        if any(keyword in combined for keyword in [
            'STAR', 'ARRIVAL', 'STANDARD TERMINAL ARRIVAL'
        ]):
            return 'STAR'
        
        # APP - Approach charts (check before GND since some approach charts mention runways)
        if any(keyword in combined for keyword in [
            'ILS', 'INSTRUMENT LANDING',
            'VOR', 'NDB', 'RNP', 'RNAV',
            'APPROACH', 'APCH', 'APP',
            'PATC', 'PRECISION APPROACH TERRAIN',
            'LOC', 'LOCALIZER',
            'VISUAL APPROACH',
            'CODING', 'CRTC', 'SENS', 'CRITICAL', 'SENSITIVE'
        ]):
            return 'APP'
        
        # GND - Ground charts (more specific patterns)
        if any(keyword in combined for keyword in [
            'ADC', 'AIRPORT DIAGRAM', 'AD CHART',
            'PDC', 'PARKING', 'DOCKING',
            'GROUND MOVEMENT', 'TAXIWAY',
            'AOCTA', 'AOCTB', 'OBSTACLE CHART',
            'HOT SPOT', 'HOTSPOT', 'HOT-SPOT',
            'TORA', 'LDA', 'ASDA', 'TODA',
            'ISOLATION', 'STAND'
        ]):
            return 'GND'
        
        # GEN - General/Area charts
        if any(keyword in combined for keyword in [
            'AREA', 'LOCATION', 'VICINITY',
            'TERMINAL CHART', 'TMA'
        ]):
            return 'GEN'
        
        # Default to GND if unclear (most charts in India are ground-related)
        return 'GND'


def get_aerodrome_charts(icao_code):
    """Wrapper function for compatibility with function-based interface."""
    scraper = IndiaScraper(verbose=False)
    return scraper.get_charts(icao_code)

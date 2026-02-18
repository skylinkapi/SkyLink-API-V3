"""
South Korea AIM Scraper
Fetches aerodrome charts from South Korea's AIM eAIP system.
Based on https://aim.koca.go.kr/
"""

import requests
import re
from typing import List, Dict
from bs4 import BeautifulSoup
from urllib.parse import quote
from datetime import datetime


class SouthKoreaScraper:
    """Scraper for South Korea AIM aerodrome charts."""
    
    BASE_URL = "https://aim.koca.go.kr"
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.package_date = None
    
    def _get_current_package_date(self):
        """Get the current package date from the main eAIP page.
        
        Returns:
            Package date string like '2026-01-08' or None if not found
        """
        if self.package_date:
            return self.package_date
            
        try:
            if self.verbose:
                print("Finding current package date...")
            
            # Try to get the menu page which should have the current package date
            response = self.session.get(f"{self.BASE_URL}/eaipPub/Package/", timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find links with package dates (format: YYYY-MM-DD)
            date_pattern = re.compile(r'/Package/(\d{4}-\d{2}-\d{2})/html')
            
            dates = []
            for link in soup.find_all('a', href=True):
                match = date_pattern.search(link['href'])
                if match:
                    dates.append(match.group(1))
            
            if dates:
                # Get the most recent date
                self.package_date = max(dates)
                if self.verbose:
                    print(f"Found current package date: {self.package_date}")
                return self.package_date
            
            if self.verbose:
                print("Could not find package date, using fallback")
            return None
            
        except Exception as e:
            if self.verbose:
                print(f"Error getting package date: {e}")
            return None
    
    def get_charts(self, icao_code: str) -> List[Dict[str, str]]:
        """
        Fetch aerodrome charts for a South Korean airport.
        
        Args:
            icao_code: ICAO code of the airport (e.g., 'RKSI', 'RKSS')
            
        Returns:
            List of chart dictionaries with 'name', 'url', and 'type' keys
        """
        icao_code = icao_code.upper()
        
        try:
            # Get current package date
            package_date = self._get_current_package_date()
            if not package_date:
                if self.verbose:
                    print("Could not determine package date, using default")
                package_date = "2026-01-08"  # fallback
            
            if self.verbose:
                print(f"Fetching South Korea eAIP for {icao_code}...")
                print(f"Package date: {package_date}")
            
            # Build the URL - format: KR-AD-2.RKSI-en-GB.html (NOT RK-AD-2)
            url = f"{self.BASE_URL}/eaipPub/Package/{package_date}/html/eAIP/KR-AD-2.{icao_code}-en-GB.html"
            
            if self.verbose:
                print(f"URL: {url}")
            
            # Get the page
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            # Parse HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find AD 2.24 section - "CHARTS RELATED TO THE AERODROME"
            ad_24_section = None
            for heading in soup.find_all(['h4', 'h3', 'h2']):
                if 'AD' in heading.get_text() and '2.24' in heading.get_text():
                    # Get the parent div or the next section
                    ad_24_section = heading.find_parent('div')
                    break
            
            if not ad_24_section:
                if self.verbose:
                    print("Could not find AD 2.24 section")
                return []
            
            if self.verbose:
                print("Found AD 2.24 section")
            
            # Find all PDF links in this section
            all_pdf_links = ad_24_section.find_all('a', href=lambda x: x and '.pdf' in x.lower())
            
            if self.verbose:
                print(f"Found {len(all_pdf_links)} PDF links in AD 2.24")
            
            # Group PDFs by name and get the most recent version
            charts_by_name = {}
            
            for link in all_pdf_links:
                href = link.get('href', '')
                name = link.get_text(strip=True)
                
                if not name or not href:
                    continue
                
                # Extract date from href (format: /Package/YYYY-MM-DD-AIRAC/... or /Package/YYYY-MM-DD/...)
                date_match = re.search(r'/Package/(\d{4}-\d{2}-\d{2}(?:-AIRAC)?)', href)
                if not date_match:
                    continue
                
                pdf_date = date_match.group(1).replace('-AIRAC', '')  # Normalize date
                
                # Check if this is a deleted version (should skip)
                parent_div = link.find_parent('div')
                if parent_div and 'AmdtDeleted' in parent_div.get('class', []):
                    continue
                
                # Keep track of the most recent version of each chart
                if name not in charts_by_name:
                    charts_by_name[name] = {'href': href, 'date': pdf_date}
                else:
                    # Compare dates and keep the most recent
                    if pdf_date > charts_by_name[name]['date']:
                        charts_by_name[name] = {'href': href, 'date': pdf_date}
            
            # Build final chart list
            charts = []
            for name, data in charts_by_name.items():
                href = data['href']
                
                # URL encode the filename part (spaces become %20)
                # Split URL to encode only the filename
                parts = href.rsplit('/', 1)
                if len(parts) == 2:
                    base_path, filename = parts
                    # URL encode the filename
                    encoded_filename = quote(filename, safe='')
                    full_url = f"{base_path}/{encoded_filename}"
                else:
                    full_url = href
                
                # Make absolute URL if needed
                if not full_url.startswith('http'):
                    full_url = f"{self.BASE_URL}{full_url}" if full_url.startswith('/') else f"{self.BASE_URL}/{full_url}"
                
                # Categorize the chart
                chart_type = self._categorize_chart(name, href)
                
                charts.append({
                    'name': name,
                    'url': full_url,
                    'type': chart_type
                })
            
            if self.verbose:
                print(f"Extracted {len(charts)} unique charts")
            
            return charts
            
        except requests.exceptions.RequestException as e:
            if self.verbose:
                print(f"Error fetching data for {icao_code}: {e}")
            return []
    
    def _categorize_chart(self, name: str, filename: str) -> str:
        """
        Categorize a chart based on its name and filename.
        
        Args:
            name: Chart name
            filename: Chart filename
            
        Returns:
            Chart type: 'general', 'airport_diagram', 'sid', 'star', or 'approach'
        """
        name_lower = name.lower()
        filename_lower = filename.lower()
        combined = f"{name_lower} {filename_lower}"
        
        # SID (Standard Instrument Departure)
        if any(keyword in combined for keyword in [
            'sid', 'departure', 'dep ', 'standard departure', 'instrument departure', 'area chart - icao(dep)', 'area chart(dep)'
        ]):
            return 'sid'
        
        # STAR (Standard Terminal Arrival Route)
        if any(keyword in combined for keyword in [
            'star', 'standard arrival', 'instrument arrival', 'area chart(arr)', 'area chart - icao(arr)'
        ]):
            return 'star'
        
        # Approach charts
        if any(keyword in combined for keyword in [
            'approach', 'apch', 'app', 'iac', 'ils', 'vor', 'ndb', 'rnav', 'rnp', 
            'landing', 'final', 'precision', 'non-precision', 'instr apch', 'visual apch',
            'atc surveillance minimum altitude'
        ]):
            return 'approach'
        
        # Airport/Ground charts
        if any(keyword in combined for keyword in [
            'aerodrome', 'airport', 'ground', 'parking', 'taxi', 'stand',
            'apron', 'movement', 'agc', 'adc', 'ad chart', 'obstacle', 'terrain',
            'bird concentration', 'docking'
        ]):
            return 'airport_diagram'
        
        # Default to general
        return 'general'


def get_aerodrome_charts(icao_code):
    """Wrapper function for compatibility with function-based interface."""
    scraper = SouthKoreaScraper(verbose=False)
    return scraper.get_charts(icao_code)


if __name__ == '__main__':
    # Test the scraper
    import sys
    
    icao = sys.argv[1] if len(sys.argv) > 1 else 'RKSI'  # Seoul Incheon
    
    scraper = SouthKoreaScraper(verbose=True)
    charts = scraper.get_charts(icao)
    
    print(f"\nFound {len(charts)} charts:")
    for chart in charts:
        print(f"  {chart['type']}: {chart['name']}")
        print(f"    {chart['url']}")

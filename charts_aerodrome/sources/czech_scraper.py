"""
Czech Republic Aerodrome Charts Scraper (LK* prefixes)
Downloads charts from Czech AIP (aim.rlp.cz)
"""

import urllib.request
import ssl
from html.parser import HTMLParser
from urllib.parse import urljoin, quote
import re

class CzechChartParser(HTMLParser):
    """Parser for Czech eAIP AD 2.24 section"""
    
    def __init__(self):
        super().__init__()
        self.charts = []
        self.in_charts_section = False
        self.in_table = False
        self.in_row = False
        self.in_chart_name_cell = False
        self.in_chart_link_cell = False
        self.current_chart_name = None
        self.current_chart_url = None
        self.current_cell_text = []
        
    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        
        # Check if we're in the AD 2.24 section
        if tag == 'div' and attrs_dict.get('id', '').endswith('-AD-2.24'):
            self.in_charts_section = True
            
        if not self.in_charts_section:
            return
            
        # Look for the table with charts
        if tag == 'table':
            self.in_table = True
            
        if self.in_table and tag == 'tr':
            self.in_row = True
            self.current_chart_name = None
            self.current_chart_url = None
            self.in_chart_name_cell = False
            self.in_chart_link_cell = False
            
        if self.in_row and tag == 'td':
            # First td typically contains chart name
            if self.current_chart_name is None:
                self.in_chart_name_cell = True
                self.current_cell_text = []
            # Second td typically contains the link
            else:
                self.in_chart_link_cell = True
                self.current_cell_text = []
                
        if self.in_chart_link_cell and tag == 'a':
            href = attrs_dict.get('href', '')
            if href and '.pdf' in href.lower():
                self.current_chart_url = href
    
    def handle_data(self, data):
        if self.in_chart_name_cell or self.in_chart_link_cell:
            text = data.strip()
            if text:
                self.current_cell_text.append(text)
    
    def handle_endtag(self, tag):
        if tag == 'div' and self.in_charts_section:
            # Check if we're leaving the charts section
            self.in_charts_section = False
            self.in_table = False
            
        if tag == 'table' and self.in_table:
            self.in_table = False
            
        if tag == 'tr' and self.in_row:
            # End of row - save chart if we have both name and URL
            if self.current_chart_name and self.current_chart_url:
                self.charts.append({
                    'name': self.current_chart_name,
                    'url': self.current_chart_url
                })
            self.in_row = False
            
        if tag == 'td':
            if self.in_chart_name_cell:
                # Save the chart name
                text = ' '.join(self.current_cell_text).strip()
                if text and text != 'Chart name':  # Skip header row
                    self.current_chart_name = text
                self.in_chart_name_cell = False
                self.current_cell_text = []
            elif self.in_chart_link_cell:
                self.in_chart_link_cell = False
                self.current_cell_text = []

def categorize_chart(name):
    """Categorize chart based on its name"""
    name_upper = name.upper()
    
    # SID patterns
    if any(x in name_upper for x in ['SID', 'STANDARD INSTRUMENT DEPARTURE', 'OMNIDIRECTIONAL DEPARTURE']):
        return 'SID'
    
    # STAR patterns
    if any(x in name_upper for x in ['STAR', 'STANDARD INSTRUMENT ARRIVAL', 'ARRIVAL']):
        return 'STAR'
    
    # Approach patterns
    if any(x in name_upper for x in ['ILS', 'VOR', 'NDB', 'RNP', 'RNAV', 'APPROACH', 'RWY', 'VISUAL', 'CIRCLING']):
        return 'Approach'
    
    # Airport diagrams
    if any(x in name_upper for x in ['AERODROME CHART', 'AIRPORT CHART', 'GROUND MOVEMENT', 'PARKING', 
                                      'AIRCRAFT PARKING', 'DOCKING', 'TAXI', 'APRON']):
        return 'Airport Diagram'
    
    # Default
    return 'General'

def get_aerodrome_charts(icao):
    """
    Get aerodrome charts for a Czech airport
    
    Args:
        icao: ICAO code (e.g., 'LKPR' for Prague)
        
    Returns:
        List of dicts with keys: name, url, type
    """
    if not icao.startswith('LK'):
        raise ValueError(f"Invalid Czech ICAO code: {icao}")
    
    # Construct URL for airport page
    base_url = "https://aim.rlp.cz/eaip/html/"
    airport_url = f"{base_url}eAIP/LK-AD-2.{icao}-en-GB.html"
    
    try:
        # Create SSL context that doesn't verify certificates
        context = ssl._create_unverified_context()
        
        # Download the airport page
        with urllib.request.urlopen(airport_url, context=context) as response:
            html_content = response.read().decode('utf-8')
        
        # Parse the HTML to extract charts
        parser = CzechChartParser()
        parser.feed(html_content)
        
        # Process charts
        charts = []
        for chart in parser.charts:
            # Build full URL
            full_url = urljoin(airport_url, chart['url'])
            
            # URL encode any special characters in the path
            from urllib.parse import urlparse, urlunparse
            parsed = urlparse(full_url)
            path_parts = parsed.path.split('/')
            encoded_parts = [quote(part, safe='') for part in path_parts]
            encoded_path = '/'.join(encoded_parts)
            full_url = urlunparse((parsed.scheme, parsed.netloc, encoded_path, '', '', ''))
            
            # Categorize chart
            chart_type = categorize_chart(chart['name'])
            
            charts.append({
                'name': chart['name'],
                'url': full_url,
                'type': chart_type
            })
        
        if not charts:
            print(f"Warning: No charts found for {icao}")
        
        return charts
        
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise ValueError(f"Airport {icao} not found in Czech eAIP")
        else:
            raise Exception(f"HTTP error accessing Czech eAIP: {e.code}")
    except Exception as e:
        raise Exception(f"Error fetching charts for {icao}: {str(e)}")

if __name__ == '__main__':
    # Test with Prague airport
    import sys
    icao = sys.argv[1] if len(sys.argv) > 1 else 'LKPR'
    
    print(f"Fetching charts for {icao}...")
    try:
        charts = get_aerodrome_charts(icao)
        print(f"\nFound {len(charts)} charts:\n")
        
        for chart in charts:
            print(f"[{chart['type']}] {chart['name']}")
            print(f"  URL: {chart['url']}\n")
            
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

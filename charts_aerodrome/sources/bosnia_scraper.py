"""
Bosnia and Herzegovina eAIP scraper for aerodrome charts.

Base URL: https://eaip.bhansa.gov.ba/
Uses Eurocontrol eAIP structure with date-based AIRAC folders.

ICAO prefix: LQ*
Example: LQSA (Sarajevo), LQMO (Mostar), LQTZ (Tuzla), LQBK (Banja Luka)

Structure: Same as Serbia/Montenegro
- Start page at base URL shows AIRAC dates
- Date folder format: "2025-11-27-AIRAC"
- Airport pages: html/eAIP/LQ-AD-2.{ICAO}-en-GB.html
- Charts in AD 2.24 section
"""

import re
import urllib.request
from urllib.parse import urljoin, quote
from html.parser import HTMLParser


class AIRACLinkParser(HTMLParser):
    """Parser to extract the latest AIRAC link from start page."""
    
    def __init__(self):
        super().__init__()
        self.airac_link = None
        self.in_green_cell = False
        
    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        if tag == 'td' and attrs_dict.get('class') == 'green':
            self.in_green_cell = True
        elif tag == 'a' and self.in_green_cell:
            href = attrs_dict.get('href', '')
            # Look for AIRAC link like "../../2025-11-27-AIRAC/html/index.html"
            if 'AIRAC/html/index.html' in href:
                # Extract just the AIRAC folder part
                match = re.search(r'(\d{4}-\d{2}-\d{2}-AIRAC)', href)
                if match:
                    self.airac_link = match.group(1)
                    
    def handle_endtag(self, tag):
        if tag == 'td':
            self.in_green_cell = False


class ChartLinksParser(HTMLParser):
    """Parser to extract chart links and names from AD 2.24 section."""
    
    def __init__(self):
        super().__init__()
        self.charts = []
        self.current_chart_name = None
        self.in_chart_name_td = False
        
    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        
        if tag == 'td':
            # Chart name cells have rowspan and valign="top"
            rowspan = attrs_dict.get('rowspan', '')
            valign = attrs_dict.get('valign', '')
            if rowspan and valign == 'top':
                self.in_chart_name_td = True
                self.current_chart_name = None
        elif tag == 'a' and 'href' in attrs_dict:
            href = attrs_dict['href']
            # Look for PDF links in graphics/eAIP/ folder
            if '.pdf' in href.lower() and 'graphics/eAIP/' in href:
                if self.current_chart_name:
                    # Clean up the chart name
                    chart_name = self.current_chart_name.strip()
                    chart_name = re.sub(r'\s*–\s*ICAO\s*$', '', chart_name)
                    chart_name = re.sub(r'\s*-\s*ICAO\s*$', '', chart_name)
                    
                    self.charts.append({
                        'name': chart_name,
                        'url': href
                    })
                    
    def handle_data(self, data):
        if self.in_chart_name_td:
            text = data.strip()
            if text and not text.startswith('AD ') and ('RWY' in text.upper() or any(x in text for x in ['Chart', 'Departure', 'Arrival', 'Approach', 'Parking', 'Obstacle', 'Terrain'])):
                self.current_chart_name = text
                
    def handle_endtag(self, tag):
        if tag == 'td':
            self.in_chart_name_td = False


def get_latest_airac_folder():
    """
    Fetch the latest AIRAC folder from the start page.
    
    Returns:
        str: AIRAC folder like "2025-11-27-AIRAC"
    """
    base_url = 'https://eaip.bhansa.gov.ba/'
    
    try:
        with urllib.request.urlopen(base_url) as response:
            html = response.read().decode('utf-8', errors='ignore')
            
        parser = AIRACLinkParser()
        parser.feed(html)
        
        if parser.airac_link:
            return parser.airac_link
        else:
            raise Exception("Could not find AIRAC folder in start page")
            
    except Exception as e:
        raise Exception(f"Failed to fetch latest AIRAC folder: {e}")


def get_airport_page_url(icao_code):
    """
    Construct the URL for an airport's eAIP page.
    
    Args:
        icao_code (str): 4-letter ICAO code (e.g., 'LQSA')
        
    Returns:
        str: Full URL to airport page
    """
    base_url = 'https://eaip.bhansa.gov.ba/'
    airac_folder = get_latest_airac_folder()
    
    # Airport pages are in eAIP subfolder with format LQ-AD-2.{ICAO}-en-GB.html
    airport_page = f"html/eAIP/LQ-AD-2.{icao_code}-en-GB.html"
    
    return urljoin(base_url, f"{airac_folder}/{airport_page}")


def categorize_chart(chart_name):
    """
    Categorize a chart based on its name.
    
    Args:
        chart_name (str): Name of the chart
        
    Returns:
        str: Chart category (SID/STAR/Approach/Airport Diagram/General)
    """
    name_upper = chart_name.upper()
    
    # SID charts
    if any(keyword in name_upper for keyword in ['DEPARTURE', 'SID']):
        return 'SID'
    
    # STAR charts
    if any(keyword in name_upper for keyword in ['ARRIVAL', 'STAR']):
        return 'STAR'
    
    # Approach charts
    if any(keyword in name_upper for keyword in ['APPROACH', 'ILS', 'VOR', 'RNP', 'RNAV', 'LOC', 'NDB', 'DME']):
        return 'Approach'
    
    # Airport diagrams
    if any(keyword in name_upper for keyword in ['AERODROME CHART', 'AIRPORT CHART', 'PARKING', 'DOCKING', 'GROUND MOVEMENT']):
        return 'Airport Diagram'
    
    # Everything else is general
    return 'General'


def get_aerodrome_charts(icao_code):
    """
    Fetch aerodrome charts for a given ICAO code from Bosnia and Herzegovina eAIP.
    
    Args:
        icao_code (str): 4-letter ICAO code (e.g., 'LQSA')
        
    Returns:
        list: List of dictionaries with 'name', 'url', and 'type' keys
    """
    # Get the airport page URL
    airport_url = get_airport_page_url(icao_code)
    base_url = 'https://eaip.bhansa.gov.ba/'
    
    try:
        # Fetch the airport page
        with urllib.request.urlopen(airport_url) as response:
            html = response.read().decode('utf-8', errors='ignore')
        
        # Parse for chart links
        parser = ChartLinksParser()
        parser.feed(html)
        
        if not parser.charts:
            # Try alternative parsing - look for AD 2.24 section directly with regex
            ad_224_match = re.search(r'<h4[^>]*>.*?AD 2\.24.*?</h4>(.*?)(?=<h4[^>]*>|<div[^>]*id="AD2)', html, re.DOTALL | re.IGNORECASE)
            
            if ad_224_match:
                ad_224_section = ad_224_match.group(1)
                
                # Find all PDF links in this section with their descriptions
                chart_pattern = r'<td[^>]*>([^<]*(?:Chart|Departure|Arrival|Approach|Parking|Obstacle|Terrain)[^<]*)</td>.*?<a[^>]*href="([^"]*\.pdf)"'
                
                matches = re.finditer(chart_pattern, ad_224_section, re.DOTALL | re.IGNORECASE)
                
                charts_temp = []
                for match in matches:
                    name = match.group(1).strip()
                    url = match.group(2)
                    
                    # Clean up name
                    name = re.sub(r'\s+', ' ', name)
                    name = re.sub(r'\s*–\s*ICAO\s*$', '', name)
                    name = re.sub(r'\s*-\s*ICAO\s*$', '', name)
                    
                    if name and url:
                        charts_temp.append({'name': name, 'url': url})
                
                if charts_temp:
                    parser.charts = charts_temp
        
        if not parser.charts:
            return []
        
        # Process charts - convert relative URLs to absolute and categorize
        airac_folder = get_latest_airac_folder()
        result = []
        
        for chart in parser.charts:
            # Convert relative URL to absolute
            # URLs are like "../../graphics/eAIP/6688438_LQ_AD_2_LQSA_2-24-12-1_en.pdf"
            # Airport page is at: {base}/{airac}/html/eAIP/LQ-AD-2.{ICAO}-en-GB.html
            # Charts are at: {base}/{airac}/graphics/eAIP/{filename}.pdf
            if chart['url'].startswith('../../graphics/eAIP/'):
                # Extract just the filename and URL encode it (spaces, etc.)
                filename = chart['url'].replace('../../graphics/eAIP/', '')
                filename_encoded = quote(filename, safe='')
                chart_url = urljoin(base_url, f"{airac_folder}/graphics/eAIP/{filename_encoded}")
            elif chart['url'].startswith('../'):
                chart_url = urljoin(base_url, f"{airac_folder}/" + chart['url'].replace('../', '', 1))
            else:
                chart_url = urljoin(airport_url, chart['url'])
            
            result.append({
                'name': chart['name'],
                'url': chart_url,
                'type': categorize_chart(chart['name'])
            })
        
        return result
        
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print(f"Airport {icao_code} not found in Bosnia and Herzegovina eAIP")
            return []
        else:
            raise Exception(f"HTTP error fetching charts for {icao_code}: {e}")
    except Exception as e:
        raise Exception(f"Error fetching charts for {icao_code}: {e}")


# For CLI compatibility
if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        icao = sys.argv[1].upper()
        charts = get_aerodrome_charts(icao)
        
        if charts:
            print(f"\nFound {len(charts)} charts for {icao}:")
            for chart in charts:
                print(f"  [{chart['type']}] {chart['name']}")
                print(f"     {chart['url']}")
        else:
            print(f"No charts found for {icao}")

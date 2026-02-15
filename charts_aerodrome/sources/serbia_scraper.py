"""
Serbia/Montenegro eAIP scraper for aerodrome charts.

Base URL: https://smatsa.rs/upload/aip/published/
Uses Eurocontrol eAIP structure with date-based AIRAC folders.

ICAO prefix: LY*
Example: LYBE (Belgrade/Nikola Tesla), LYPG (Podgorica), LYTV (Tivat), LYNI (Niš)

Structure:
- start_page.html contains link to latest AIRAC date folder
- Date folder format: "27-Nov-2025-A/2025-11-27-AIRAC"
- Airport pages: html/eAIP/LY-AD-2.{ICAO}-en-GB.html
- Charts in AD 2.24 section
"""

import re
import urllib.request
from urllib.parse import urljoin, quote
from html.parser import HTMLParser


class DateFolderParser(HTMLParser):
    """Parser to extract the latest AIRAC date folder from start page."""
    
    def __init__(self):
        super().__init__()
        self.date_folder = None
        
    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            attrs_dict = dict(attrs)
            href = attrs_dict.get('href', '')
            # Look for date folder pattern like "./27-Nov-2025-A/2025-11-27-AIRAC/html/index_commands.html"
            if 'AIRAC' in href and 'html/index_commands.html' in href:
                # Extract the date folder part: "27-Nov-2025-A/2025-11-27-AIRAC"
                match = re.search(r'\./([^/]+/[^/]+AIRAC)', href)
                if match:
                    self.date_folder = match.group(1)


class ChartLinksParser(HTMLParser):
    """Parser to extract chart links and names from AD 2.24 section."""
    
    def __init__(self):
        super().__init__()
        self.charts = []
        self.in_ad_224 = False
        self.current_chart_name = None
        self.in_chart_name_td = False
        
    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        
        # Check if we're entering AD 2.24 section
        if tag == 'h4':
            self.current_chart_name = None
        elif tag == 'td':
            # Chart name cells have specific pattern
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
                    # Clean up the chart name (remove ICAO prefix like "ICAO")
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
            if text and not text.startswith('AD ') and 'RWY' in text.upper() or any(x in text for x in ['Chart', 'Departure', 'Arrival', 'Approach', 'Parking', 'Obstacle', 'Terrain']):
                # This looks like a chart type name
                self.current_chart_name = text
                
    def handle_endtag(self, tag):
        if tag == 'td':
            self.in_chart_name_td = False
        elif tag == 'h4':
            # Check if this is AD 2.24 section
            if hasattr(self, 'current_section_title'):
                if 'AD 2.24' in self.current_section_title or 'Charts related' in self.current_section_title:
                    self.in_ad_224 = True


def get_latest_date_folder():
    """
    Fetch the latest AIRAC date folder from the start page.
    
    Returns:
        str: Date folder path like "27-Nov-2025-A/2025-11-27-AIRAC"
    """
    base_url = 'https://smatsa.rs/upload/aip/published/'
    start_url = urljoin(base_url, 'start_page.html')
    
    try:
        with urllib.request.urlopen(start_url) as response:
            html = response.read().decode('utf-8', errors='ignore')
            
        parser = DateFolderParser()
        parser.feed(html)
        
        if parser.date_folder:
            return parser.date_folder
        else:
            raise Exception("Could not find AIRAC date folder in start page")
            
    except Exception as e:
        raise Exception(f"Failed to fetch latest date folder: {e}")


def get_airport_page_url(icao_code):
    """
    Construct the URL for an airport's eAIP page.
    
    Args:
        icao_code (str): 4-letter ICAO code (e.g., 'LYBE')
        
    Returns:
        str: Full URL to airport page
    """
    base_url = 'https://smatsa.rs/upload/aip/published/'
    date_folder = get_latest_date_folder()
    
    # Airport pages are in eAIP subfolder with format LY-AD-2.{ICAO}-en-GB.html
    airport_page = f"html/eAIP/LY-AD-2.{icao_code}-en-GB.html"
    
    return urljoin(base_url, f"{date_folder}/{airport_page}")


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
    Fetch aerodrome charts for a given ICAO code from Serbia/Montenegro eAIP.
    
    Args:
        icao_code (str): 4-letter ICAO code (e.g., 'LYBE')
        
    Returns:
        list: List of dictionaries with 'name', 'url', and 'type' keys
    """
    # Get the airport page URL
    airport_url = get_airport_page_url(icao_code)
    base_url = 'https://smatsa.rs/upload/aip/published/'
    
    try:
        # Fetch the airport page
        with urllib.request.urlopen(airport_url) as response:
            html = response.read().decode('utf-8', errors='ignore')
        
        # Parse for chart links
        parser = ChartLinksParser()
        parser.feed(html)
        
        if not parser.charts:
            # Try alternative parsing - look for AD 2.24 section directly with regex
            # Find the AD 2.24 section
            ad_224_match = re.search(r'<h4[^>]*>.*?AD 2\.24.*?</h4>(.*?)(?=<h4[^>]*>|<div[^>]*id="AD2[^"]*2015072409482302)', html, re.DOTALL | re.IGNORECASE)
            
            if ad_224_match:
                ad_224_section = ad_224_match.group(1)
                
                # Find all PDF links in this section with their descriptions
                # Pattern: look for table rows with chart names and PDF links
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
        date_folder = get_latest_date_folder()
        result = []
        
        for chart in parser.charts:
            # Convert relative URL to absolute
            # URLs are like "../../graphics/eAIP/6688438_LY_AD_2_LYBE_2-24-12-1_en.pdf"
            # Airport page is at: {base}/{date}/html/eAIP/LY-AD-2.{ICAO}-en-GB.html
            # Charts are at: {base}/{date}/graphics/eAIP/{filename}.pdf
            # So ../../graphics/eAIP/ goes up from eAIP/ to html/ to {date}/ then into graphics/eAIP/
            if chart['url'].startswith('../../graphics/eAIP/'):
                # Extract just the filename and URL encode it (spaces, etc.)
                filename = chart['url'].replace('../../graphics/eAIP/', '')
                filename_encoded = quote(filename, safe='')
                chart_url = urljoin(base_url, f"{date_folder}/graphics/eAIP/{filename_encoded}")
            elif chart['url'].startswith('../'):
                chart_url = urljoin(base_url, f"{date_folder}/" + chart['url'].replace('../', '', 1))
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
            print(f"Airport {icao_code} not found in Serbia/Montenegro eAIP")
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

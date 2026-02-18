"""
Armenia eAIP Scraper
Handles airports with UD* prefix (UDYZ, UDYE, UDSG)
Base URL: https://armats.am/activities/ais/eaip
"""

import urllib.request
import ssl
from html.parser import HTMLParser
from urllib.parse import urljoin, quote
import re


def get_latest_eaip_link():
    """Get the latest eAIP link from Armenia AIS page."""
    base_url = "https://armats.am/activities/ais/eaip"
    
    context = ssl._create_unverified_context()
    req = urllib.request.Request(base_url)
    
    with urllib.request.urlopen(req, context=context) as response:
        html_content = response.read().decode('utf-8')
    
    # Find the current effective eAIP link
    # Pattern: href="/storage/attachments/176657412906-25(25DEC2025)/index.html"
    pattern = r'href="(/storage/attachments/[^"]+/index\.html)"'
    match = re.search(pattern, html_content)
    
    if match:
        relative_path = match.group(1)
        return urljoin('https://armats.am', relative_path)
    
    return None


def get_airport_page_url(icao, eaip_url):
    """Construct the URL for an airport's AD 2.24 page."""
    # Extract base path from eAIP URL
    # https://armats.am/storage/attachments/176657412906-25(25DEC2025)/index.html
    # -> https://armats.am/storage/attachments/176657412906-25(25DEC2025)/
    base_path = eaip_url.rsplit('/', 1)[0]
    
    # Airport pages are in html/eAIP/UD-AD-2.{ICAO}-en-GB.html
    airport_page = f"{base_path}/html/eAIP/UD-AD-2.{icao}-en-GB.html"
    
    return airport_page


class ChartLinksParser(HTMLParser):
    """Parser to extract chart links from AD 2.24 section."""
    
    def __init__(self):
        super().__init__()
        self.in_ad_224 = False
        self.charts = []
        self.current_title = ""
        self.in_figure_title = False
        self.title_depth = 0
    
    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        
        # Check if we're entering AD 2.24 section
        if tag == 'div' and attrs_dict.get('id', '').endswith('-AD-2.24'):
            self.in_ad_224 = True
        
        # Look for figure titles
        if self.in_ad_224 and tag == 'span':
            if 'Figure-title' in attrs_dict.get('class', ''):
                self.in_figure_title = True
                self.current_title = ""
                self.title_depth = 0
        
        # Track depth when in title
        if self.in_figure_title:
            self.title_depth += 1
        
        # Look for PDF links
        if self.in_ad_224 and tag == 'a':
            href = attrs_dict.get('href', '')
            if href.endswith('.pdf'):
                self.charts.append({
                    'title': self.current_title.strip(),
                    'url': href
                })
    
    def handle_data(self, data):
        if self.in_figure_title:
            self.current_title += data
    
    def handle_endtag(self, tag):
        if self.in_figure_title:
            self.title_depth -= 1
            if self.title_depth == 0:
                self.in_figure_title = False


def categorize_chart(title):
    """Categorize chart based on title."""
    title_lower = title.lower() if title else ""
    
    # Specific pattern matching
    if 'sid' in title_lower or 'departure' in title_lower:
        return 'SID'
    elif 'star' in title_lower or 'arrival' in title_lower:
        return 'STAR'
    elif ('approach' in title_lower or 'ils' in title_lower or 'rnp' in title_lower or 
          'dvor' in title_lower or 'visual approach' in title_lower):
        return 'Approach'
    elif ('ground movement' in title_lower or 'parking' in title_lower or 
          'aerodrome chart' in title_lower):
        return 'Airport Diagram'
    else:
        return 'General'


def get_aerodrome_charts(icao):
    """
    Fetch aerodrome charts for Armenian airports (UD* prefix).
    
    Args:
        icao: ICAO code (e.g., 'UDYZ', 'UDYE', 'UDSG')
    
    Returns:
        List of dictionaries with chart information
    """
    # Get latest eAIP link
    eaip_url = get_latest_eaip_link()
    if not eaip_url:
        return []
    
    # Construct airport page URL
    airport_page_url = get_airport_page_url(icao, eaip_url)
    
    # Download airport page
    context = ssl._create_unverified_context()
    req = urllib.request.Request(airport_page_url)
    
    try:
        with urllib.request.urlopen(req, context=context) as response:
            html_content = response.read().decode('utf-8')
    except:
        return []
    
    # Parse charts
    parser = ChartLinksParser()
    parser.feed(html_content)
    
    # Convert relative URLs to absolute and encode filenames
    base_path = eaip_url.rsplit('/', 1)[0]
    charts = []
    
    for chart in parser.charts:
        # chart['url'] is like ../../graphics/UDYZ AD 2.2-1-255.pdf
        # Need to resolve relative path
        if chart['url'].startswith('../../graphics/'):
            filename = chart['url'].replace('../../graphics/', '')
            filename_encoded = quote(filename, safe='')
            full_url = f"{base_path}/graphics/{filename_encoded}"
        else:
            full_url = urljoin(airport_page_url, chart['url'])
        
        chart_type = categorize_chart(chart['title'])
        
        charts.append({
            'name': chart['title'] or 'Unknown',
            'url': full_url,
            'type': chart_type
        })
    
    return charts

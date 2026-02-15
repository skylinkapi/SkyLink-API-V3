"""
Slovenia eAIP Scraper
Handles airports with LJ* prefix (LJLJ, LJMB, LJPZ, LJCE)
Base URL: https://aim.sloveniacontrol.si/aim/eAIP/Operations/
"""

import urllib.request
import ssl
from html.parser import HTMLParser
from urllib.parse import urljoin, quote
import re


def get_latest_airac_folder():
    """Get the latest AIRAC folder from Slovenia eAIP history page."""
    history_url = "https://aim.sloveniacontrol.si/aim/eAIP/Operations/history-en-GB.html"
    
    context = ssl._create_unverified_context()
    req = urllib.request.Request(history_url)
    
    with urllib.request.urlopen(req, context=context) as response:
        html_content = response.read().decode('utf-8')
    
    # Find the latest AIRAC (class="Red" or class="green")
    # Pattern: <a href="../Operations/2026-02-19-AIRAC/html/index.html">19 FEB 2026</a>
    pattern = r'href="../Operations/([^/]+)/html/index\.html"'
    matches = re.findall(pattern, html_content)
    
    if matches:
        # Return the first match (should be the latest)
        return matches[0]
    
    return None


def get_airport_page_url(icao, airac_folder):
    """Construct the URL for an airport's AD 2.24 page."""
    base_url = "https://aim.sloveniacontrol.si/aim/eAIP/Operations"
    
    # Airport pages are in {airac}/html/eAIP/LJ-AD-2.{ICAO}-en-GB.html
    airport_page = f"{base_url}/{airac_folder}/html/eAIP/LJ-AD-2.{icao}-en-GB.html"
    
    return airport_page


class ChartLinksParser(HTMLParser):
    """Parser to extract chart links from AD 2.24 table."""
    
    def __init__(self):
        super().__init__()
        self.in_ad_224 = False
        self.in_table = False
        self.in_row = False
        self.in_first_td = False
        self.in_second_td = False
        self.charts = []
        self.last_chart_id = None  # Keep last chart ID across rows
        self.last_chart_title = None  # Keep last title across rows
        self.collecting_title = False
        self.td_count = 0
        self.row_number = 0
    
    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        
        # Check if we're entering AD 2.24 section
        div_id = attrs_dict.get('id', '')
        if tag == 'div' and 'AD-2.24' in div_id:
            self.in_ad_224 = True
        
        # Look for table in AD 2.24 section
        if self.in_ad_224 and tag == 'table':
            self.in_table = True
        
        # Track rows in the table
        if self.in_table and tag == 'tr':
            self.in_row = True
            self.td_count = 0
            self.row_number += 1
        
        # Track table cells
        if self.in_row and tag == 'td':
            self.td_count += 1
            rowspan = attrs_dict.get('rowspan', '1')
            
            # First td with rowspan="2" contains chart ID
            if self.td_count == 1 and rowspan == '2':
                self.in_first_td = True
            # Second td in first row contains title
            elif self.td_count == 2:
                self.in_second_td = True
                self.collecting_title = True
        
        # Look for PDF links in the <a> tag
        if self.in_table and tag == 'a':
            href = attrs_dict.get('href', '')
            if href and '.pdf' in href:
                # Use the last saved chart ID and title
                if self.last_chart_title and self.last_chart_id:
                    self.charts.append({
                        'id': self.last_chart_id,
                        'title': self.last_chart_title,
                        'url': href
                    })
    
    def handle_data(self, data):
        data = data.strip()
        if not data:
            return
        
        # Collect chart ID from first td
        if self.in_first_td:
            self.last_chart_id = data
            self.in_first_td = False
        
        # Collect chart title from second td
        if self.collecting_title and self.in_second_td:
            self.last_chart_title = data
            self.collecting_title = False
    
    def handle_endtag(self, tag):
        if tag == 'td':
            self.in_second_td = False
        elif tag == 'tr':
            self.in_row = False
        elif tag == 'table':
            self.in_table = False
        elif tag == 'div' and self.in_ad_224:
            self.in_ad_224 = False


def categorize_chart(title):
    """Categorize chart based on title."""
    if not title:
        return 'General'
    
    title_lower = title.lower()
    
    # Specific pattern matching
    if 'departure' in title_lower or 'sid' in title_lower:
        return 'SID'
    elif 'arrival' in title_lower or 'star' in title_lower:
        return 'STAR'
    elif 'approach' in title_lower or 'ils' in title_lower or 'rnp' in title_lower or 'vor' in title_lower or 'loc' in title_lower:
        return 'Approach'
    elif 'parking' in title_lower or 'docking' in title_lower or 'aerodrome chart' in title_lower:
        return 'Airport Diagram'
    else:
        return 'General'


def get_aerodrome_charts(icao):
    """
    Fetch aerodrome charts for Slovenian airports (LJ* prefix).
    
    Args:
        icao: ICAO code (e.g., 'LJLJ', 'LJMB', 'LJPZ', 'LJCE')
    
    Returns:
        List of dictionaries with chart information
    """
    # Get latest AIRAC folder
    airac_folder = get_latest_airac_folder()
    if not airac_folder:
        return []
    
    # Construct airport page URL
    airport_page_url = get_airport_page_url(icao, airac_folder)
    
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
    base_url = f"https://aim.sloveniacontrol.si/aim/eAIP/Operations/{airac_folder}"
    charts = []
    
    for chart in parser.charts:
        # chart['url'] is like ../../graphics/eAIP/LJ_AD_2_LJLJ_01-1_en.pdf
        # Need to resolve relative path
        if chart['url'].startswith('../../graphics/eAIP/'):
            filename = chart['url'].replace('../../graphics/eAIP/', '')
            filename_encoded = quote(filename, safe='')
            full_url = f"{base_url}/graphics/eAIP/{filename_encoded}"
        else:
            full_url = urljoin(airport_page_url, chart['url'])
        
        chart_type = categorize_chart(chart['title'])
        
        charts.append({
            'name': chart['title'] or 'Unknown',
            'url': full_url,
            'type': chart_type
        })
    
    return charts

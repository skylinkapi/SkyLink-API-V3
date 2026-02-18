"""
North Macedonia eAIP Scraper
Handles airports with LW* prefix (LWSK - Skopje, LWOH - Ohrid)
Base URL: https://ais.m-nav.info/eAIP/current/en/
Charts are in: https://ais.m-nav.info/eAIP/current/aipcharts/{ICAO}/...
"""

import urllib.request
import ssl
import re
import warnings
warnings.filterwarnings('ignore', message='Unverified HTTPS request')


def download_tree_items():
    """Download the tree_items.js file that contains chart links."""
    tree_url = "https://ais.m-nav.info/eAIP/current/en/tree_items.js"
    
    context = ssl._create_unverified_context()
    req = urllib.request.Request(
        tree_url,
        headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': '*/*',
            'Referer': 'https://ais.m-nav.info/eAIP/current/en/menu.htm'
        }
    )
    
    with urllib.request.urlopen(req, context=context) as response:
        return response.read().decode('utf-8')


def parse_charts_from_tree(tree_content, icao):
    """Parse chart links from tree_items.js for the given ICAO code."""
    charts = []
    
    # Find the section for this ICAO code
    # Pattern: ['LWSK Charts', '', followed by chart entries
    pattern = rf"\['{icao} Charts'[^\[]*\[(.*?)\n\s*\],"
    match = re.search(pattern, tree_content, re.DOTALL)
    
    if not match:
        return []
    
    charts_section = match.group(1)
    
    # Extract individual chart entries
    # Pattern: ['LWSK AD 2.24-1 (Related Charts)', '../aipcharts/LWSK/LW_AD_2_LWSK_24_1_en.pdf'],
    chart_pattern = r"\['([^']+)',\s*'\.\./(aipcharts/[^']+)'\]"
    matches = re.findall(chart_pattern, charts_section)
    
    for chart_name, chart_path in matches:
        # Build full URL
        full_url = f"https://ais.m-nav.info/eAIP/current/{chart_path}"
        
        chart_type = categorize_chart(chart_name)
        
        charts.append({
            'name': chart_name,
            'url': full_url,
            'type': chart_type
        })
    
    return charts


def categorize_chart(name):
    """Categorize chart based on name."""
    if not name:
        return 'General'
    
    name_lower = name.lower()
    
    # Specific pattern matching
    if 'sid' in name_lower or 'departure' in name_lower:
        return 'SID'
    elif 'star' in name_lower or 'arrival' in name_lower:
        return 'STAR'
    elif 'iac' in name_lower or 'ils' in name_lower or 'vor' in name_lower or 'rnp' in name_lower or 'loc' in name_lower or 'rnav' in name_lower or 'approach' in name_lower:
        return 'Approach'
    elif 'adc' in name_lower or 'aerodrome chart' in name_lower or 'airport chart' in name_lower or 'ground movement' in name_lower:
        return 'Airport Diagram'
    elif 'apdc' in name_lower or 'parking' in name_lower:
        return 'Parking'
    elif 'related charts' in name_lower:
        return 'Reference'
    elif 'aoc' in name_lower or 'aob' in name_lower or 'obstacle' in name_lower:
        return 'Obstacles'
    elif 'mrva' in name_lower or 'minima' in name_lower:
        return 'Minimums'
    else:
        return 'General'


def get_aerodrome_charts(icao):
    """
    Fetch aerodrome charts for North Macedonian airports (LW* prefix).
    
    Args:
        icao: ICAO code (e.g., 'LWSK', 'LWOH')
    
    Returns:
        List of dictionaries with chart information
    """
    try:
        # Download tree items
        tree_content = download_tree_items()
        
        # Parse charts for this ICAO
        charts = parse_charts_from_tree(tree_content, icao)
        
        return charts
    except Exception as e:
        print(f"Error fetching charts for {icao}: {e}")
        return []


# Test the scraper
if __name__ == '__main__':
    # Test with Skopje Airport
    print("Testing North Macedonia scraper with LWSK (Skopje)...")
    charts = get_aerodrome_charts('LWSK')
    
    if charts:
        print(f"\nFound {len(charts)} charts:")
        for chart in charts:
            print(f"  [{chart['type']}] {chart['name']}")
            print(f"      {chart['url']}")
    else:
        print("No charts found.")
    
    print("\n" + "="*80 + "\n")
    
    # Test with Ohrid Airport
    print("Testing North Macedonia scraper with LWOH (Ohrid)...")
    charts = get_aerodrome_charts('LWOH')
    
    if charts:
        print(f"\nFound {len(charts)} charts:")
        for chart in charts:
            print(f"  [{chart['type']}] {chart['name']}")
            print(f"      {chart['url']}")
    else:
        print("No charts found.")

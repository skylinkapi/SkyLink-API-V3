#!/usr/bin/env python3
"""
Myanmar eAIP Scraper
Scrapes aerodrome charts from Myanmar AIS following Eurocontrol structure
https://www.ais.gov.mm/eAIP/history-en-GB.html
"""

import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin, quote
import sys

BASE_URL = "https://www.ais.gov.mm"


def get_current_eaip_date(verbose=False):
    """Get the currently effective eAIP date from history page"""
    history_url = f"{BASE_URL}/eAIP/history-en-GB.html"
    
    if verbose:
        print(f"Fetching eAIP history from {history_url}")
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(history_url, headers=headers, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find all eAIP links and prioritize AIRAC amendments
        eaip_links = []
        for row in soup.find_all('tr'):
            link = row.find('a', href=True)
            if link:
                href = link['href']
                # Extract date from href like "2022-05-30/html/index-en-GB.html"
                match = re.search(r'(\d{4}-\d{2}-\d{2}(?:-AIRAC)?)/html/index-en-GB\.html', href)
                if match:
                    date_str = match.group(1)
                    # Prioritize AIRAC amendments over regular publications
                    is_airac = '-AIRAC' in date_str
                    eaip_links.append((date_str, is_airac, href))
        
        if not eaip_links:
            raise Exception("Could not find any eAIP dates")
        
        # Sort by AIRAC priority first, then by date
        eaip_links.sort(key=lambda x: (x[1], x[0]), reverse=True)
        
        latest_date = eaip_links[0][0]
        if verbose:
            print(f"Found latest eAIP: {latest_date}")
        
        return latest_date
        
    except Exception as e:
        if verbose:
            print(f"Error getting eAIP date: {e}")
        return None


def categorize_chart(chart_name):
    """Categorize chart based on its name"""
    name_upper = chart_name.upper()
    
    # SID
    if 'SID' in name_upper or 'DEPARTURE' in name_upper:
        return 'SID'
    
    # STAR
    if 'STAR' in name_upper or 'ARRIVAL' in name_upper:
        return 'STAR'
    
    # APP - Approach charts
    if any(keyword in name_upper for keyword in [
        'ILS', 'VOR', 'NDB', 'RNP', 'RNAV', 'APPROACH', 'APCH',
        'LOC', 'VISUAL APP', 'CODING', 'MINIMUM', 'PATC'
    ]):
        return 'APP'
    
    # GND - Ground charts
    if any(keyword in name_upper for keyword in [
        'ADC', 'DIAGRAM', 'PDC', 'PARKING', 'DOCKING',
        'GROUND', 'TAXIWAY', 'GMC', 'OBSTACLE', 'HOT SPOT',
        'STAND', 'APRON', 'LAYOUT'
    ]):
        return 'GND'
    
    # GEN - General charts (area charts, VFR procedures, etc.)
    if any(keyword in name_upper for keyword in [
        'AREA', 'TMA', 'VFR', 'PROCEDURE', 'GENERAL', 'GEN'
    ]):
        return 'GEN'
    
    # Default to GEN
    return 'GEN'


def clean_chart_name(name):
    """Clean up chart name by removing pagespeed artifacts"""
    # Remove .pdf.pagespeed.ce.*.pdf patterns
    name = re.sub(r'\.pdf\.pagespeed\.ce\.[A-Za-z0-9_-]+\.pdf$', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\.pdf\.pagespeed\.ce\.[A-Za-z0-9_-]+$', '', name, flags=re.IGNORECASE)
    # Remove .pagespeed.ce.* suffix
    name = re.sub(r'\.pagespeed\.ce\.[A-Za-z0-9_-]+$', '', name)
    # Remove .pdf extension
    name = re.sub(r'\.pdf$', '', name, flags=re.IGNORECASE)
    return name.strip()


def get_aerodrome_charts(icao_code, verbose=False):
    """
    Get all aerodrome charts for a given ICAO code from Myanmar eAIP
    
    Args:
        icao_code: 4-letter ICAO code (e.g., 'VYYY')
        verbose: Print debug information
        
    Returns:
        List of dictionaries with 'name', 'url', and 'type' keys
    """
    charts = []
    icao_code = icao_code.upper()
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    # Get current eAIP date
    eaip_date = get_current_eaip_date(verbose)
    if not eaip_date:
        if verbose:
            print("Could not determine current eAIP date")
        return []
    
    # Construct airport page URL following Eurocontrol pattern
    # Format: https://www.ais.gov.mm/eAIP/{date}/html/eAIP/AD-2.{ICAO}-en-GB.html
    airport_url = f"{BASE_URL}/eAIP/{eaip_date}/html/eAIP/AD-2.{icao_code}-en-GB.html"
    
    if verbose:
        print(f"Constructed airport page URL: {airport_url}")
    
    try:
        response = requests.get(airport_url, headers=headers, timeout=30)
        if response.status_code != 200:
            if verbose:
                print(f"Airport page not found: {response.status_code}")
            return []
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find all PDF links on the airport page (Myanmar eAIP structure)
        # Unlike strict Eurocontrol, Myanmar puts charts throughout the page
        all_charts = []
        for link in soup.find_all('a', href=True):
            href = link['href']
            
            # Only process PDF links
            if '.pdf' not in href.lower():
                continue
            
            # Get chart name from filename (clean up pagespeed artifacts)
            filename = href.split('/')[-1]
            chart_name = clean_chart_name(filename)
            
            if not chart_name:
                continue
            
            # Build full URL
            full_url = urljoin(airport_url, href)
            
            # URL encode the PDF filename (spaces and special characters)
            # Split URL into base and filename, encode filename only
            url_parts = full_url.rsplit('/', 1)
            if len(url_parts) == 2:
                base_url, filename = url_parts
                encoded_filename = quote(filename, safe='')
                full_url = f"{base_url}/{encoded_filename}"
            
            # Categorize
            chart_type = categorize_chart(chart_name)
            
            all_charts.append({
                'name': chart_name,
                'url': full_url,
                'type': chart_type,
                'filename': filename
            })
        
        # Filter to get only current charts (remove older amendments)
        # Group by chart type and base name, keep the most recent version
        chart_groups = {}
        for chart in all_charts:
            # Extract base chart type from filename (remove amendment dates)
            # e.g., "VYYY-ILSY-RWY21-AIRAC-AMDT-2022" -> "VYYY-ILSY-RWY21"
            base_name = chart['filename']
            
            # Remove pagespeed suffix properly
            base_name = re.sub(r'\.pagespeed\.ce\.[A-Za-z0-9_-]+(?:\.pdf)?$', '', base_name)
            # Remove .pdf extension
            base_name = re.sub(r'\.pdf$', '', base_name, flags=re.IGNORECASE)
            
            # Remove various date/amendment patterns to group similar charts
            # Patterns: -AIRAC-AMDT-01-2022, -AIRAC-AMDT-2018-04, -AIRAC-2018-2, -02-2020
            base_name = re.sub(r'-AIRAC-AMDT-\d+-\d+$', '', base_name)         # -AMDT-2018-04 or -AMDT-01-2022
            base_name = re.sub(r'-AIRAC-AMDT-\d+$', '', base_name)            # -AMDT-2022
            base_name = re.sub(r'-AIRAC-\d+-\d+$', '', base_name)             # -AIRAC-2018-2
            base_name = re.sub(r'-\d+-\d+$', '', base_name)                   # -02-2020
            
            key = (chart['type'], base_name)
            
            if key not in chart_groups:
                chart_groups[key] = []
            chart_groups[key].append(chart)
        
        # For each group, keep only the most recent chart
        for group_key, group_charts in chart_groups.items():
            if len(group_charts) == 1:
                # Only one version, keep it
                charts.append(group_charts[0])
            else:
                # Multiple versions, keep the one with the most recent date
                def get_sort_key(chart):
                    filename = chart['filename'].upper()
                    # Extract all 4-digit years
                    years = re.findall(r'(\d{4})', filename)
                    if years:
                        return max(int(y) for y in years)  # Use the highest year found
                    return 0
                
                group_charts.sort(key=get_sort_key, reverse=True)
                charts.append(group_charts[0])  # Keep the most recent
        
        # Sort by type then name
        type_order = {'GEN': 0, 'GND': 1, 'SID': 2, 'STAR': 3, 'APP': 4}
        charts.sort(key=lambda x: (type_order.get(x['type'], 99), x['name']))
        
        if verbose:
            print(f"Found {len(charts)} charts")
        
        return charts
        
    except Exception as e:
        if verbose:
            print(f"Error scraping {icao_code}: {e}")
            import traceback
            traceback.print_exc()
        return []


def main():
    if len(sys.argv) < 2:
        print("Usage: python myanmar_scraper.py <ICAO_CODE>")
        print("Example: python myanmar_scraper.py VYYY")
        sys.exit(1)
    
    icao_code = sys.argv[1].upper()
    
    print(f"Fetching charts for {icao_code}...")
    charts = get_aerodrome_charts(icao_code, verbose=True)
    
    if charts:
        print(f"\nFound {len(charts)} charts:")
        for chart in charts:
            print(f"  [{chart['type']}] {chart['name']}")
            print(f"    {chart['url']}")
    else:
        print("No charts found")


if __name__ == "__main__":
    main()

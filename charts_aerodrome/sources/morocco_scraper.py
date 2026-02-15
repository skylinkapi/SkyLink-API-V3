"""
Morocco AIP Scraper
Scrapes aerodrome charts from Morocco SIA (Service d'Information Aéronautique)

Base URL: https://siamaroc.onda.ma/eAIP/AD/cartes.htm
Structure:
- Single page with all airports in tables
- Each airport has its own table with chart links
- PDF URLs: ../cartes/AD2{ICAO}/AD2{ICAO}{number}.pdf
- ICAO prefix: GM*

Examples: GMMN (Casablanca), GMTT (Tangier), GMMX (Rabat)
"""

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import sys


BASE_URL = "https://siamaroc.onda.ma/eAIP/AD/cartes.htm"
PDF_BASE_URL = "https://siamaroc.onda.ma/eAIP/"


def categorize_chart(chart_name: str) -> str:
    """
    Categorize chart based on its name.
    
    Args:
        chart_name: Name/description of the chart
        
    Returns:
        Category string (SID, STAR, Approach, Airport Diagram, General)
    """
    name_upper = chart_name.upper()
    
    # SID
    if 'SID' in name_upper or 'DÉPART' in name_upper or 'DEPARTURE' in name_upper:
        return 'SID'
    
    # STAR
    if 'STAR' in name_upper or 'ARRIVÉE' in name_upper or 'ARRIVAL' in name_upper:
        return 'STAR'
    
    # Approach charts
    if any(keyword in name_upper for keyword in [
        'APPROCHE AUX INSTRUMENTS', 'INSTRUMENT APPROACH',
        'APPROCHE À VUE', 'VISUAL APPROACH',
        'ATTERRISAGE', 'LANDING'
    ]):
        return 'Approach'
    
    # Ground/Airport diagrams
    if any(keyword in name_upper for keyword in [
        'AÉRODROME', 'AERODROME', 'HÉLISTATION', 'HELIPORT',
        'STATIONNEMENT', 'PARKING', 'DOCKING',
        'MOUVEMENTS', 'MOVEMENT', 'GROUND'
    ]):
        return 'Airport Diagram'
    
    # General (obstacles, terrain, area charts, radar minimums)
    return 'General'


def get_aerodrome_charts(icao_code: str) -> list:
    """
    Get all aerodrome charts for a given ICAO code from Morocco AIP.
    
    Args:
        icao_code: 4-letter ICAO code (e.g., 'GMMN')
        
    Returns:
        List of dictionaries with 'name', 'url', and 'type' keys
    """
    icao_code = icao_code.upper()
    charts = []
    
    try:
        # Fetch the charts page
        response = requests.get(BASE_URL, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'lxml')
        
        # Find the table for the requested airport
        # Tables have the ICAO code in the first row/header
        target_table = None
        
        for table in soup.find_all('table'):
            table_text = table.get_text()
            # Check if this table contains the ICAO code
            if icao_code in table_text:
                # Verify it's the right table (ICAO should be in header)
                first_row = table.find('tr')
                if first_row and icao_code in first_row.get_text():
                    target_table = table
                    break
        
        if not target_table:
            print(f"Airport {icao_code} not found in Morocco AIP")
            return charts
        
        # Extract all PDF links from the table
        rows = target_table.find_all('tr')
        
        current_chart_type = ""
        
        for row in rows:
            cells = row.find_all(['td', 'th'])
            
            # Skip header row
            if len(cells) < 2:
                continue
            
            # Get chart description from the row
            row_text = row.get_text(strip=True)
            
            # Find description cell (usually the middle one)
            for cell in cells:
                cell_text = cell.get_text(strip=True)
                if len(cell_text) > 20:  # Likely a description
                    current_chart_type = cell_text
                    break
            
            # Find all PDF links in this row
            links = row.find_all('a', href=True)
            
            for link in links:
                href = link['href']
                if not href.lower().endswith('.pdf'):
                    continue
                
                # Get chart code from link text
                chart_code = link.get_text(strip=True)
                
                # Build full URL
                # href is like ../cartes/AD2GMMN/AD2GMMN15.pdf
                full_url = urljoin(PDF_BASE_URL + "AD/", href)
                
                # Create chart name
                chart_name = f"{icao_code} {chart_code}"
                if current_chart_type:
                    # Extract just the French name for brevity
                    if 'Carte' in current_chart_type:
                        desc_end = current_chart_type.find('–')
                        if desc_end == -1:
                            desc_end = current_chart_type.find('-')
                        if desc_end > 0:
                            chart_name = f"{icao_code} - {current_chart_type[:desc_end].strip()}"
                        else:
                            chart_name = f"{icao_code} - {current_chart_type[:60]}"
                
                # Categorize
                chart_type = categorize_chart(current_chart_type)
                
                charts.append({
                    'name': chart_name,
                    'url': full_url,
                    'type': chart_type
                })
        
        return charts
        
    except Exception as e:
        print(f"Error scraping {icao_code}: {e}")
        import traceback
        traceback.print_exc()
        return charts


def main():
    """CLI entry point for testing."""
    if len(sys.argv) < 2:
        print("Usage: python morocco_scraper.py <ICAO_CODE>")
        print("Example: python morocco_scraper.py GMMN")
        sys.exit(1)
    
    icao_code = sys.argv[1].upper()
    
    print(f"Fetching charts for {icao_code}...")
    charts = get_aerodrome_charts(icao_code)
    
    if charts:
        print(f"\nFound {len(charts)} charts:")
        
        # Group by type
        by_type = {}
        for chart in charts:
            t = chart['type']
            if t not in by_type:
                by_type[t] = []
            by_type[t].append(chart)
        
        for chart_type, type_charts in sorted(by_type.items()):
            print(f"\n{chart_type} ({len(type_charts)}):")
            for chart in type_charts:
                print(f"  {chart['name']}")
                print(f"    {chart['url']}")
    else:
        print("No charts found")


if __name__ == "__main__":
    main()

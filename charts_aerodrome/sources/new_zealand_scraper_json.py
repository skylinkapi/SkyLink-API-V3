"""
New Zealand Aerodrome Chart Scraper
Source: Pre-scraped JSON database from AIP New Zealand
"""

import json
import os


def get_aerodrome_charts(icao_code):
    """
    Gets aerodrome charts for a New Zealand airport from JSON database.
    
    Args:
        icao_code: ICAO code (e.g., 'NZAA' for Auckland)
        
    Returns:
        List of dictionaries with chart information
    """
    # Load the JSON database
    json_file = os.path.join(os.path.dirname(__file__), '..', 'AIP New Zealand.json')
    
    if not os.path.exists(json_file):
        print(f"ERROR: JSON database not found at {json_file}")
        print("Please run prescrape_new_zealand.py first to generate the database")
        return []
    
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Look up the airport
    if icao_code not in data:
        print(f"Airport {icao_code} not found in database")
        print(f"Database contains {len(data)} airports")
        return []
    
    airport_data = data[icao_code]
    charts = []
    
    # Process charts and add categories
    for chart in airport_data['charts']:
        category = categorize_chart(chart['name'])
        charts.append({
            'name': chart['name'],
            'url': chart['url'],
            'category': category
        })
    
    return charts


def categorize_chart(chart_name):
    """
    Categorize a chart based on its name.
    
    Args:
        chart_name: The name/title of the chart
        
    Returns:
        Category string
    """
    name_lower = chart_name.lower()
    
    # Arrival/Departure procedures
    if any(x in name_lower for x in ['arrival', 'departure', 'star', 'sid']):
        return 'Arrival/Departure'
    
    # Approach charts
    if any(x in name_lower for x in ['ils', 'loc', 'vor', 'ndb', 'rnp', 'approach', 'rnav']):
        return 'Approach'
    
    # Airport diagrams
    if any(x in name_lower for x in ['aerodrome', 'ground movement', 'airport diagram', 'parking']):
        return 'Airport Diagram'
    
    # Operational data
    if 'operational data' in name_lower or 'operational' in name_lower:
        return 'Operational Data'
    
    # Visual procedures
    if 'vfr' in name_lower or 'visual' in name_lower:
        return 'Visual'
    
    # Noise abatement
    if 'noise' in name_lower:
        return 'Noise Abatement'
    
    # Standard route clearances
    if 'standard route' in name_lower or 'clearance' in name_lower:
        return 'Standard Routes'
    
    # Heliport
    if 'heliport' in name_lower or 'helicopter' in name_lower:
        return 'Heliport'
    
    # Default
    return 'Other'


# For testing
def test_scraper():
    """Test the scraper with Auckland airport"""
    print("Testing New Zealand scraper with Auckland (NZAA)...")
    charts = get_aerodrome_charts("NZAA")
    
    if charts:
        print(f"\nSuccessfully retrieved {len(charts)} charts for NZAA:")
        
        # Group by category
        categories = {}
        for chart in charts:
            cat = chart['category']
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(chart)
        
        # Print summary
        for category, cat_charts in sorted(categories.items()):
            print(f"\n{category}: {len(cat_charts)} charts")
            for chart in cat_charts[:3]:  # Show first 3 of each category
                print(f"  - {chart['name']}")
            if len(cat_charts) > 3:
                print(f"  ... and {len(cat_charts) - 3} more")
    else:
        print("No charts found!")


if __name__ == "__main__":
    test_scraper()

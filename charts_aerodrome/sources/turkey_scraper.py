"""
Turkey AIP Scraper
Returns link to Turkey's AIP portal (requires account for full access).
URL: https://www.dhmi.gov.tr/Sayfalar/aipturkey.aspx

ICAO prefix: LT* (LTFM, LTAI, LTBA, etc.)
"""

from typing import List, Dict


def get_aerodrome_charts(icao_code: str, verbose: bool = False) -> List[Dict[str, str]]:
    """
    Returns Turkey AIP portal link.
    
    Note: Full chart access requires an account at the DHMI portal.
    
    Args:
        icao_code: ICAO code (LT* prefix)
        verbose: Print debug information
        
    Returns:
        List with AIP portal link
    """
    icao_code = icao_code.upper()
    
    if not icao_code.startswith('LT'):
        if verbose:
            print(f"Invalid Turkey ICAO code: {icao_code} (should start with LT)")
        return []
    
    return [{
        'name': f'Turkey AIP Portal - {icao_code} (Account Required)',
        'url': 'https://www.dhmi.gov.tr/Sayfalar/aipturkey.aspx',
        'type': 'General'
    }]


if __name__ == '__main__':
    import sys
    
    icao = sys.argv[1].upper() if len(sys.argv) > 1 else 'LTFM'
    
    print(f"Turkey AIP for {icao}:")
    charts = get_aerodrome_charts(icao)
    for chart in charts:
        print(f"  [{chart['type']}] {chart['name']}")
        print(f"    {chart['url']}")

#!/usr/bin/env python3
"""
Croatia AIM Scraper
Returns link to Croatia Aeronautical Information Management system
"""

def get_aerodrome_charts(icao_code):
    """
    Return Croatia AIM link for any Croatian airport
    """
    return [
        {
            'name': 'Croatia Aeronautical Information Management (AIM)',
            'url': 'https://aim.crocontrol.hr/#/',
            'type': 'GEN'
        }
    ]
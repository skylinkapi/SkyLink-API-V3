#!/usr/bin/env python3
"""
Cyprus AIS Scraper
Returns link to Cyprus Aeronautical Information Service
"""

def get_aerodrome_charts(icao_code):
    """
    Return Cyprus AIS link for any Cypriot airport
    """
    return [
        {
            'name': 'Cyprus Aeronautical Information Service (AIS)',
            'url': 'https://www.mcw.gov.cy/mcw/DCA/AIS/ais.nsf/All/57B39BFA3276159CC2257C7E00233AA2?OpenDocument',
            'type': 'GEN'
        }
    ]
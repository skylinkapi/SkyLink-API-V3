#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CLI tool to fetch aerodrome chart PDF links from FAA website
and categorize them into: GEN, GND, SID, STAR, APP
"""

import argparse
import sys
import os

# Set console encoding to UTF-8 for Windows
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

from sources.faa_scraper import FAAScraper
from sources.canada_fltplan_scraper import CanadaScraper
from sources.brazil_scraper import BrazilScraper
from sources.argentina_scraper import ArgentinaScraper
from sources.colombia_scraper import ColombiaScraper
from sources.russia_scraper import RussiaScraper
from sources.kazakhstan_scraper import KazakhstanScraper
from sources.kyrgyzstan_scraper import KyrgyzstanScraper
from sources.china_scraper import ChinaScraper
from sources.australia_scraper import AustraliaScraper
from sources.belgium_luxembourg_scraper import get_aerodrome_charts as get_belgium_luxembourg_charts
from sources.slovakia_scraper import get_aerodrome_charts as get_slovakia_charts
from sources.austria_scraper import get_aerodrome_charts as get_austria_charts
from sources.netherlands_scraper import get_aerodrome_charts as get_netherlands_charts
from sources.germany_scraper import GermanyScraper
from sources.poland_scraper import get_aerodrome_charts as get_poland_charts
from sources.lithuania_scraper import get_aerodrome_charts as get_lithuania_charts
from sources.latvia_scraper import get_aerodrome_charts as get_latvia_charts
from sources.estonia_scraper import get_aerodrome_charts as get_estonia_charts
from sources.finland_scraper import get_aerodrome_charts as get_finland_charts
from sources.france_scraper import get_aerodrome_charts as get_france_charts
from sources.sweden_scraper import get_aerodrome_charts as get_sweden_charts
from sources.norway_scraper import get_aerodrome_charts as get_norway_charts
from sources.ireland_scraper import get_aerodrome_charts as get_ireland_charts
from sources.uk_scraper import get_aerodrome_charts as get_uk_charts
from sources.kosovo_scraper import get_aerodrome_charts as get_kosovo_charts
from sources.aruba_scraper import get_aerodrome_charts as get_aruba_charts
from sources.cape_verde_scraper import get_aerodrome_charts as get_cape_verde_charts
from sources.algeria_scraper import get_aerodrome_charts as get_algeria_charts
from sources.asecna_scraper import get_aerodrome_charts as get_asecna_charts
from sources.djibouti_scraper import get_aerodrome_charts as get_djibouti_charts
from sources.morocco_scraper import get_aerodrome_charts as get_morocco_charts
from sources.somalia_scraper import get_aerodrome_charts as get_somalia_charts
from sources.south_africa_scraper import get_aerodrome_charts as get_south_africa_charts
from sources.south_sudan_scraper import get_aerodrome_charts as get_south_sudan_charts
from sources.cocesna_scraper import get_aerodrome_charts as get_cocesna_charts
from sources.chile_scraper import get_aerodrome_charts as get_chile_charts
from sources.cuba_scraper import get_aerodrome_charts as get_cuba_charts
from sources.croatia_scraper import get_aerodrome_charts as get_croatia_charts
from sources.cyprus_scraper import get_aerodrome_charts as get_cyprus_charts
from sources.malta_scraper import get_aerodrome_charts as get_malta_charts
from sources.denmark_scraper import get_aerodrome_charts as get_denmark_charts
from sources.venezuela_scraper import get_aerodrome_charts as get_venezuela_charts
from sources.uruguay_scraper import get_aerodrome_charts as get_uruguay_charts
from sources.dominican_republic_scraper import get_aerodrome_charts as get_dominican_republic_charts
from sources.haiti_scraper import get_aerodrome_charts as get_haiti_charts
from sources.cayman_scraper import get_aerodrome_charts as get_cayman_charts
from sources.panama_scraper import get_aerodrome_charts as get_panama_charts
from sources.afghanistan_scraper import get_aerodrome_charts as get_afghanistan_charts
from sources.bahrain_scraper import get_aerodrome_charts as get_bahrain_charts
from sources.iceland_scraper import get_aerodrome_charts as get_iceland_charts
from sources.bangladesh_scraper import get_aerodrome_charts as get_bangladesh_charts
from sources.belarus_scraper import get_aerodrome_charts as get_belarus_charts
from sources.bhutan_scraper import get_aerodrome_charts as get_bhutan_charts
from sources.brunei_scraper import get_aerodrome_charts as get_brunei_charts
from sources.georgia_scraper import get_aerodrome_charts as get_georgia_charts
from sources.hongkong_scraper import get_aerodrome_charts as get_hongkong_charts
from sources.israel_scraper import get_aerodrome_charts as get_israel_charts
from sources.kuwait_scraper import get_aerodrome_charts as get_kuwait_charts
from sources.malaysia_scraper import get_aerodrome_charts as get_malaysia_charts
from sources.maldives_scraper import get_aerodrome_charts as get_maldives_charts
from sources.mongolia_scraper import get_aerodrome_charts as get_mongolia_charts
from sources.myanmar_scraper import get_aerodrome_charts as get_myanmar_charts
from sources.nepal_scraper import get_aerodrome_charts as get_nepal_charts
from sources.oman_scraper import get_aerodrome_charts as get_oman_charts
from sources.pakistan_scraper import get_aerodrome_charts as get_pakistan_charts
from sources.qatar_scraper import get_aerodrome_charts as get_qatar_charts
from sources.saudi_arabia_scraper import get_aerodrome_charts as get_saudi_arabia_charts
from sources.singapore_scraper import get_aerodrome_charts as get_singapore_charts
from sources.sri_lanka_scraper import get_aerodrome_charts as get_sri_lanka_charts
from sources.tajikistan_scraper import get_aerodrome_charts as get_tajikistan_charts
from sources.turkey_scraper import get_aerodrome_charts as get_turkey_charts
from sources.turkmenistan_scraper import get_aerodrome_charts as get_turkmenistan_charts
from sources.uzbekistan_scraper import get_aerodrome_charts as get_uzbekistan_charts
from sources.india_scraper import IndiaScraper
from sources.south_korea_scraper import SouthKoreaScraper
from sources.thailand_scraper import ThailandScraper


def categorize_chart(chart_info):
    """
    Categorize chart based on its name and type
    
    Categories:
    - GEN: General information (procedures, requirements, operations, minimums)
    - GND: Ground charts (airport diagrams, taxi diagrams, parking, facilities)
    - SID: Standard Instrument Departure
    - STAR: Standard Terminal Arrival Route
    - APP: Approach procedures (IAP)
    """
    chart_name = chart_info['name'].lower()
    chart_type = chart_info.get('type', '').lower()
    
    # Use type first if available
    if chart_type == 'star':
        return 'STAR'
    
    if chart_type in ['departure', 'sid']:
        return 'SID'
    
    if chart_type in ['approach', 'iap', 'app']:
        return 'APP'
    
    if chart_type in ['gnd', 'ground']:
        return 'GND'
    
    if chart_type == 'gen':
        return 'GEN'
    
    # For airport_diagram type, need to distinguish between GND and GEN
    if chart_type == 'airport_diagram':
        # GEN - Procedures, operations, requirements, minimums
        if any(keyword in chart_name for keyword in [
            'procedure', 'requirement', 'operation', 'minimum', 
            'reduced take-off', 'reduced takeoff', 'alternate',
            'takeoff minimum', 'legend', 'note'
        ]):
            return 'GEN'
        
        # GND - Physical layouts and diagrams
        if any(keyword in chart_name for keyword in [
            'aerodrome chart', 'taxi chart', 'parking', 'facility',
            'hot spot', 'lahso', 'apron', 'start box'
        ]):
            return 'GND'
        
        # Default airport_diagram to GND
        return 'GND'
    
    # GND - Ground/Airport diagrams (check BEFORE SID/STAR to catch "ground movement / departure")
    if any(keyword in chart_name for keyword in ['airport diagram', 'taxi', 'hot spot', 'lahso', 'parking', 'apron', 'ground movement', 'docking', 'adc', 'apdc', 'gmc']):
        return 'GND'
    
    # GEN - Minimums and general info (but not approaches)
    if any(keyword in chart_name for keyword in ['minimum', 'alternate', 'takeoff minimum', 'legend', 'procedure', 'requirement', 'operation']):
        # Exclude approach charts that might contain "minimum"
        if not any(keyword in chart_name for keyword in ['ils', 'rnav', 'vor', 'approach', 'loc']):
            return 'GEN'
    
    # STAR - Standard Terminal Arrival (check keywords too as fallback)
    if any(keyword in chart_name for keyword in [' arrival', 'star']):
        # But not if it says departure or ground movement
        if 'departure' not in chart_name and ' dp' not in chart_name and 'ground' not in chart_name:
            return 'STAR'
    
    # SID - Standard Instrument Departure  
    if any(keyword in chart_name for keyword in ['departure', ' dp ', 'sid']):
        # But not ground movement charts
        if 'ground' not in chart_name:
            return 'SID'
    
    # APP - Approach procedures and RNAV routes
    if any(keyword in chart_name for keyword in ['approach', 'iap', 'ils', 'rnav', 'rnp', 'vor', 'ndb', 'gps', 'loc', 'tacan', 'visual', 'aoc', 'patc']):
        return 'APP'
    
    # Default to GEN for unknown types
    return 'GEN'


def display_charts(charts):
    """Display charts organized by category"""
    
    # Organize charts by category
    categorized = {
        'GEN': [],
        'GND': [],
        'SID': [],
        'STAR': [],
        'APP': []
    }
    
    for chart in charts:
        category = categorize_chart(chart)
        categorized[category].append(chart)
    
    # Display results
    print("\n" + "="*80)
    print(f"AERODROME CHARTS")
    print("="*80 + "\n")
    
    for category in ['GEN', 'GND', 'SID', 'STAR', 'APP']:
        if categorized[category]:
            print(f"\n📁 {category} ({len(categorized[category])} charts)")
            print("-" * 80)
            for chart in categorized[category]:
                print(f"  📄 {chart['name']}")
                print(f"     🔗 {chart['url']}")
                print()


def main():
    parser = argparse.ArgumentParser(
        description='Fetch aerodrome chart PDF links for a given ICAO code',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s KJFK        # Get charts for JFK Airport
  %(prog)s KLAX        # Get charts for LAX Airport
  %(prog)s KSFO        # Get charts for San Francisco Airport
        """
    )
    
    parser.add_argument('icao_code', 
                       help='ICAO airport code (e.g., KJFK, KLAX, KSFO)')
    
    parser.add_argument('-s', '--source',
                       choices=['faa', 'canada', 'brazil', 'argentina', 'colombia', 'russia', 'kazakhstan', 'kyrgyzstan', 'china', 'australia', 'belarus', 'belgium', 'luxembourg', 'slovakia', 'austria', 'netherlands', 'germany', 'poland', 'lithuania', 'latvia', 'estonia', 'finland', 'france', 'sweden', 'norway', 'ireland', 'uk', 'kosovo', 'aruba', 'cape_verde', 'algeria', 'asecna', 'djibouti', 'morocco', 'somalia', 'south_africa', 'south_sudan', 'cocesna', 'belize', 'costa_rica', 'el_salvador', 'guatemala', 'honduras', 'nicaragua', 'chile', 'cuba', 'croatia', 'cyprus', 'malta', 'denmark', 'venezuela', 'uruguay', 'dominican_republic', 'haiti', 'iceland', 'cayman', 'panama', 'uae', 'uzbekistan', 'india', 'south_korea', 'thailand'],
                       default=None,
                       help='Chart source (default: auto-detect from ICAO code)')
    
    parser.add_argument('-v', '--verbose',
                       action='store_true',
                       help='Verbose output')
    
    parser.add_argument('-e', '--extract-pdfs',
                       action='store_true',
                       help='Extract individual chart PDFs locally (for Canada, Djibouti, Somalia)')
    
    args = parser.parse_args()
    
    # Convert to uppercase
    icao_code = args.icao_code.upper()
    
    # Auto-detect source if not specified
    if args.source is None:
        if icao_code.startswith('K') and len(icao_code) == 4:
            args.source = 'faa'
        elif icao_code.startswith('CY') or icao_code.startswith('CZ'):
            args.source = 'canada'
        elif icao_code.startswith(('SB', 'SD', 'SI', 'SJ', 'SN', 'SS', 'SW')):
            args.source = 'brazil'
        elif icao_code.startswith('SC'):
            # Chile uses SC* prefixes (SCEL, SCIE, SCDA, SCFA, etc.)
            args.source = 'chile'
        elif icao_code.startswith('LM'):
            # Malta uses LM* prefixes (LMML, etc.)
            args.source = 'malta'
        elif icao_code.startswith('SU'):
            # Uruguay uses SU* prefixes (SUMU, SUAA, SUAG, SUCA, etc.)
            args.source = 'uruguay'
        elif icao_code.startswith('SV'):
            # Venezuela uses SV* prefixes (SVMI, SVMC, SVVA, SVBC, etc.)
            args.source = 'venezuela'
        elif icao_code.startswith(('SA', 'SE', 'SG', 'SL', 'SO', 'SY')):
            # Argentina uses: SA, SE, SG, SL, SO, SY prefixes
            args.source = 'argentina'
        elif icao_code.startswith('SK'):
            args.source = 'colombia'
        elif icao_code.startswith('UA'):
            # Kazakhstan uses UA* prefixes (UAAA, UAKK, UATE, etc.)
            args.source = 'kazakhstan'
        elif icao_code.startswith('UC'):
            # Kyrgyzstan uses UC* prefixes (UCFM, UCFO, etc.)
            args.source = 'kyrgyzstan'
        elif icao_code.startswith('ZM'):
            # Mongolia uses ZM* prefixes (ZMUB, ZMKD, etc.)
            args.source = 'mongolia'
        elif icao_code.startswith(('ZB', 'ZP', 'ZY', 'ZG', 'ZH', 'ZU', 'ZW', 'ZL', 'ZS')):
            # China uses Z* prefixes (ZBAA, ZSPD, ZGGG, ZPPP, etc.)
            args.source = 'china'
        elif icao_code.startswith('Y'):
            # Australia uses Y* prefixes (YSSY, YMML, YBBN, etc.)
            args.source = 'australia'
        elif icao_code.startswith('EB'):
            # Belgium uses EB* prefixes (EBBR, EBAW, EBCI, EBLG, EBOS, etc.)
            args.source = 'belgium'
        elif icao_code.startswith('EL'):
            # Luxembourg uses EL* prefixes (ELLX)
            args.source = 'luxembourg'
        elif icao_code.startswith('EH'):
            # Netherlands uses EH* prefixes (EHAM, EHRD, EHGG, EHBK, etc.)
            args.source = 'netherlands'
        elif icao_code.startswith('EY'):
            # Lithuania uses EY* prefixes (EYVI, EYKA, EYPA, EYSA, etc.)
            args.source = 'lithuania'
        elif icao_code.startswith('EV'):
            # Latvia uses EV* prefixes (EVRA, EVLA, etc.)
            args.source = 'latvia'
        elif icao_code.startswith('EE'):
            # Estonia uses EE* prefixes (EETN, EEEI, EEKA, EEPU, etc.)
            args.source = 'estonia'
        elif icao_code.startswith('EF'):
            # Finland uses EF* prefixes (EFHK, EFOU, EFTP, etc.)
            args.source = 'finland'
        elif icao_code.startswith('LF'):
            # France uses LF* prefixes (LFPG, LFPO, LFMN, LFLL, LFBO, etc.)
            args.source = 'france'
        elif icao_code.startswith('TFF'):
            # French Antilles uses TFF* prefixes (TFFF, TFFR, etc.)
            args.source = 'france'
        elif icao_code.startswith('SO'):
            # French Guiana uses SO* prefixes (SOCA, etc.)
            args.source = 'france'
        elif icao_code.startswith('NW'):
            # New Caledonia uses NW* prefixes (NWWW, etc.)
            args.source = 'france'
        elif icao_code.startswith('NL'):
            # Wallis and Futuna uses NL* prefixes (NLWW, etc.)
            args.source = 'france'
        elif icao_code.startswith('NT'):
            # French Polynesia uses NT* prefixes (NTAA, etc.)
            args.source = 'france'
        elif icao_code.startswith('FM'):
            # Reunion/Mayotte uses FM* prefixes (FMEE, etc.)
            args.source = 'france'
        elif icao_code.startswith('ES'):
            # Sweden uses ES* prefixes (ESSA, ESGG, ESSB, etc.)
            args.source = 'sweden'
        elif icao_code.startswith('EN'):
            # Norway uses EN* prefixes (ENGM, ENBR, ENZV, ENSO, etc.)
            args.source = 'norway'
        elif icao_code.startswith('EI'):
            # Ireland uses EI* prefixes (EIDW, EICK, EINN, etc.)
            args.source = 'ireland'
        elif icao_code.startswith('EG'):
            # UK uses EG* prefixes (EGLL, EGKK, EGCC, EGGW, etc.)
            args.source = 'uk'
        elif icao_code.startswith('EK'):
            # Denmark uses EK* prefixes (EKCH, EKRK, EKBI, etc.)
            args.source = 'denmark'
        elif icao_code.startswith('LC'):
            # Cyprus uses LC* prefixes (LCLK, LCEN, etc.)
            args.source = 'cyprus'
        elif icao_code.startswith('LM'):
            # Malta uses LM* prefixes (LMML, etc.)
            args.source = 'malta'
        elif icao_code.startswith('LD'):
            # Croatia uses LD* prefixes (LDDU, LDZA, etc.)
            args.source = 'croatia'
        elif icao_code.startswith('BK'):
            # Kosovo uses BK* prefixes (BKPR, etc.)
            args.source = 'kosovo'
        elif icao_code.startswith('LT'):
            # Turkey uses LT* prefixes (LTFM, LTAI, LTBA, etc.)
            args.source = 'turkey'
        elif icao_code.startswith('TN'):
            # Dutch Caribbean uses TN* prefixes (TNCA, TNCC, TNCM, TNCB, TNCS, TNCE)
            args.source = 'aruba'
        elif icao_code.startswith('GV'):
            # Cape Verde uses GV* prefixes (GVAC, GVNP, GVSV, etc.)
            args.source = 'cape_verde'
        elif icao_code.startswith('DA'):
            # Algeria uses DA* prefixes (DAAG, DABB, DAOO, etc.)
            args.source = 'algeria'
        elif icao_code.startswith('HD'):
            # Djibouti uses HD* prefixes (HDAM)
            args.source = 'djibouti'
        elif icao_code.startswith('GM'):
            # Morocco uses GM* prefixes (GMMN, GMTT, GMMX, etc.)
            args.source = 'morocco'
        elif icao_code.startswith('HC'):
            # Somalia uses HC* prefixes (HCMM, HCMH, HCMI, etc.)
            args.source = 'somalia'
        elif icao_code.startswith('FA'):
            # South Africa uses FA* prefixes (FAOR, FACT, FALE, FALA, etc.)
            args.source = 'south_africa'
        elif icao_code.startswith('HJ'):
            # South Sudan uses HJ* prefixes (HJJJ, HJMK, HJWW, etc.)
            args.source = 'south_sudan'
        elif icao_code.startswith('MU'):
            # Cuba uses MU* prefixes (MUHA, MUCU, MUVR, etc.)
            args.source = 'cuba'
        elif icao_code.startswith('MD'):
            # Dominican Republic uses MD* prefixes (MDSD, MDPC, MDST, MDLR, etc.)
            args.source = 'dominican_republic'
        elif icao_code.startswith('MT'):
            # Haiti uses MT* prefixes (MTPP, MTCH, MTJA, MTCA, etc.)
            args.source = 'haiti'
        elif icao_code.startswith('MW'):
            # Cayman Islands uses MW* prefixes (MWCR, MWCB)
            args.source = 'cayman'
        elif icao_code.startswith('MP'):
            # Panama uses MP* prefixes (MPTO, MPMG, MPDA, MPBO, etc.)
            args.source = 'panama'
        elif icao_code.startswith('MZ'):
            # Belize uses MZ* prefixes (MZBZ, etc.) - COCESNA
            args.source = 'cocesna'
        elif icao_code.startswith('MR'):
            # Costa Rica uses MR* prefixes (MROC, MRLB, MRPV, etc.) - COCESNA
            args.source = 'cocesna'
        elif icao_code.startswith('MS'):
            # El Salvador uses MS* prefixes (MSSS, MSLP, etc.) - COCESNA
            args.source = 'cocesna'
        elif icao_code.startswith('MG'):
            # Guatemala uses MG* prefixes (MGGT, MGPB, etc.) - COCESNA
            args.source = 'cocesna'
        elif icao_code.startswith('MH'):
            # Honduras uses MH* prefixes (MHTG, MHLM, etc.) - COCESNA
            args.source = 'cocesna'
        elif icao_code.startswith('MN'):
            # Nicaragua uses MN* prefixes (MNMG, etc.) - COCESNA
            args.source = 'cocesna'
        elif icao_code.startswith('OA'):
            # Afghanistan uses OA* prefixes (OAKB, etc.)
            args.source = 'afghanistan'
        elif icao_code.startswith('OB'):
            # Bahrain uses OB* prefixes (OBBI, etc.)
            args.source = 'bahrain'
        elif icao_code.startswith('BI'):
            # Iceland uses BI* prefixes (BIRK, BIAR, BIKF, etc.)
            args.source = 'iceland'
        elif icao_code.startswith(('VA', 'VE', 'VI', 'VO')):
            # India uses VA*, VE*, VI*, VO* prefixes (VIDP, VABB, VECC, VOMM, etc.)
            args.source = 'india'
        elif icao_code.startswith('VG'):
            # Bangladesh uses VG* prefixes (VGHS, VGEG, VGCB, etc.)
            args.source = 'bangladesh'
        elif icao_code.startswith('VQ'):
            # Bhutan uses VQ* prefixes (VQPR, etc.)
            args.source = 'bhutan'
        elif icao_code.startswith('VY'):
            # Myanmar uses VY* prefixes (VYYY, VYMN, VYMD, etc.)
            args.source = 'myanmar'
        elif icao_code.startswith('VN'):
            # Nepal uses VN* prefixes (VNKT, VNBW, VNPK, etc.)
            args.source = 'nepal'
        elif icao_code.startswith('WB'):
            # Brunei uses WB* prefixes (WBSB, etc.)
            args.source = 'brunei'
        elif icao_code.startswith('VH'):
            # Hong Kong uses VH* prefixes (VHHH, etc.)
            args.source = 'hongkong'
        elif icao_code.startswith('LL'):
            # Israel uses LL* prefixes (LLBG, LLER, LLHA)
            args.source = 'israel'
        elif icao_code.startswith('OK'):
            # Kuwait uses OK* prefixes (OKKK)
            args.source = 'kuwait'
        elif icao_code.startswith('OO'):
            # Oman uses OO* prefixes (OOMS, OOSA, OOSQ, etc.)
            args.source = 'oman'
        elif icao_code.startswith('OP'):
            # Pakistan uses OP* prefixes (OPKC, OPLA, OPIS, etc.)
            args.source = 'pakistan'
        elif icao_code.startswith('OT'):
            # Qatar uses OT* prefixes (OTHH, OTBD)
            args.source = 'qatar'
        elif icao_code.startswith('OE'):
            # Saudi Arabia uses OE* prefixes (OEJN, OERK, OEDF, etc.)
            args.source = 'saudi_arabia'
        elif icao_code.startswith('WM'):
            # Malaysia uses WM* prefixes (WMKK, WMKP, WMSA, etc.)
            args.source = 'malaysia'
        elif icao_code.startswith('WS'):
            # Singapore uses WS* prefixes (WSSS, WSSL)
            args.source = 'singapore'
        elif icao_code.startswith('VR'):
            # Maldives uses VR* prefixes (VRMM, VRMG, VRMH, etc.)
            args.source = 'maldives'
        elif icao_code.startswith('VC'):
            # Sri Lanka uses VC* prefixes (VCBI, VCRI, VCCA, etc.)
            args.source = 'sri_lanka'
        elif icao_code.startswith(('DB', 'DF', 'DI', 'DR', 'DX')):
            # ASECNA West African countries:
            # DB* = Bénin, DF* = Burkina Faso, DI* = Côte d'Ivoire
            # DR* = Niger, DX* = Togo
            args.source = 'asecna'
        elif icao_code.startswith(('FC', 'FE', 'FG', 'FK', 'FM', 'FO', 'FT')):
            # ASECNA Central African countries:
            # FC* = Congo, FE* = Centrafrique, FG* = Guinée Equatoriale
            # FK* = Cameroun, FM* = Madagascar/Comores, FO* = Gabon, FT* = Tchad
            args.source = 'asecna'
        elif icao_code.startswith(('GA', 'GG', 'GO', 'GQ')):
            # ASECNA countries with G* prefix:
            # GA* = Mali, GG* = Guinée Bissau, GO* = Sénégal, GQ* = Mauritanie
            args.source = 'asecna'
        elif icao_code.startswith('LZ'):
            # Slovakia uses LZ* prefixes (LZIB, LZKZ, LZPP, LZSL, etc.)
            args.source = 'slovakia'
        elif icao_code.startswith('LO'):
            # Austria uses LO* prefixes (LOWW, LOWI, LOWS, LOWG, LOWK, LOWL, etc.)
            args.source = 'austria'
        elif icao_code.startswith(('ED', 'ET')):
            # Germany uses ED* (civil) and ET* (military) prefixes (EDDB, EDDF, EDDM, ETNL, etc.)
            args.source = 'germany'
        elif icao_code.startswith('EP'):
            # Poland uses EP* prefixes (EPWA, EPPO, EPKK, EPGD, etc.)
            args.source = 'poland'
        elif icao_code.startswith('UTD'):
            # Tajikistan uses UTD* prefixes (UTDD, UTDL, UTDK, UTDT)
            args.source = 'tajikistan'
        elif icao_code.startswith('UTA'):
            # Turkmenistan uses UTA* prefixes (UTAA, UTAN, UTAT, UTAE, UTAM, UTAV, UTAK)
            args.source = 'turkmenistan'
        elif icao_code.startswith(('UT', 'UZ')):
            # Uzbekistan uses UT* and UZ* prefixes (UTTT, UZFA, UZNU, UZTT, etc.)
            args.source = 'uzbekistan'
        elif icao_code.startswith('OM'):
            # UAE uses OM* prefixes (OMAA, OMDB, OMDW, OMSJ, etc.)
            args.source = 'uae'
        elif icao_code.startswith('UM'):
            # Belarus uses UM* prefixes (UMMS, etc.)
            args.source = 'belarus'
        elif icao_code.startswith('UG'):
            # Georgia uses UG* prefixes (UGTB, UGSB, etc.)
            args.source = 'georgia'
        elif icao_code.startswith('RK'):
            # South Korea uses RK* prefixes (RKSI, RKSS, RKTN, etc.)
            args.source = 'south_korea'
        elif icao_code.startswith('VT'):
            # Thailand uses VT* prefixes (VTBS, VTBD, VTCC, etc.)
            args.source = 'thailand'
        elif icao_code.startswith('U') and not icao_code.startswith(('SU', 'UA', 'UC', 'UT', 'UZ', 'UM', 'UG')):
            # Russia uses U* prefixes (UU*, UW*, UL*, UR*, etc.) except Uruguay's SU*, Kazakhstan's UA*, Kyrgyzstan's UC*, Uzbekistan's UT*/UZ*, Belarus's UM*
            args.source = 'russia'
        else:
            # Try FAA by default
            args.source = 'faa'
        
        if args.verbose:
            print(f"[DEBUG] Auto-detected source: {args.source}")
    
    print(f"\n🔍 Fetching charts for {icao_code} from {args.source.upper()}...")
    
    try:
        # Initialize scraper
        if args.source == 'faa':
            scraper = FAAScraper(verbose=args.verbose)
        elif args.source == 'canada':
            scraper = CanadaScraper(verbose=args.verbose)
        elif args.source == 'brazil':
            scraper = BrazilScraper()
        elif args.source == 'argentina':
            scraper = ArgentinaScraper(verbose=args.verbose)
        elif args.source == 'colombia':
            scraper = ColombiaScraper()
        elif args.source == 'russia':
            scraper = RussiaScraper(verbose=args.verbose)
        elif args.source == 'kazakhstan':
            scraper = KazakhstanScraper(verbose=args.verbose)
        elif args.source == 'kyrgyzstan':
            scraper = KyrgyzstanScraper(verbose=args.verbose)
        elif args.source == 'china':
            scraper = ChinaScraper(verbose=args.verbose)
        elif args.source == 'australia':
            scraper = AustraliaScraper(verbose=args.verbose)
        elif args.source == 'india':
            scraper = IndiaScraper(verbose=args.verbose)
        elif args.source == 'south_korea':
            scraper = SouthKoreaScraper(verbose=args.verbose)
        elif args.source == 'thailand':
            scraper = ThailandScraper(verbose=args.verbose)
        elif args.source == 'belarus':
            # Belarus scraper returns charts directly
            charts = get_belarus_charts(icao_code)
            if not charts:
                print(f"\n❌ No charts found for {icao_code}")
                sys.exit(1)
            display_charts(charts)
            print("\n" + "="*80)
            print(f"✅ Found {len(charts)} total charts")
            print("="*80 + "\n")
            return
        elif args.source == 'georgia':
            # Georgia scraper returns charts directly
            charts = get_georgia_charts(icao_code)
            if not charts:
                print(f"\n❌ No charts found for {icao_code}")
                sys.exit(1)
            display_charts(charts)
            print("\n" + "="*80)
            print(f"✅ Found {len(charts)} total charts")
            print("="*80 + "\n")
            return
        elif args.source in ('belgium', 'luxembourg'):
            # Belgium/Luxembourg scraper returns charts directly
            charts = get_belgium_luxembourg_charts(icao_code)
            if not charts:
                print(f"\n❌ No charts found for {icao_code}")
                sys.exit(1)
            display_charts(charts)
            print("\n" + "="*80)
            print(f"✅ Found {len(charts)} total charts")
            print("="*80 + "\n")
            return
        elif args.source == 'slovakia':
            # Slovakia scraper returns charts directly
            charts = get_slovakia_charts(icao_code)
            if not charts:
                print(f"\n❌ No charts found for {icao_code}")
                sys.exit(1)
            display_charts(charts)
            print("\n" + "="*80)
            print(f"✅ Found {len(charts)} total charts")
            print("="*80 + "\n")
            return
        elif args.source == 'austria':
            # Austria scraper returns charts directly
            charts = get_austria_charts(icao_code)
            if not charts:
                print(f"\n❌ No charts found for {icao_code}")
                sys.exit(1)
            display_charts(charts)
            print("\n" + "="*80)
            print(f"✅ Found {len(charts)} total charts")
            print("="*80 + "\n")
            return
        elif args.source == 'netherlands':
            # Netherlands scraper returns charts directly
            charts = get_netherlands_charts(icao_code)
            if not charts:
                print(f"\n❌ No charts found for {icao_code}")
                sys.exit(1)
            display_charts(charts)
            print("\n" + "="*80)
            print(f"✅ Found {len(charts)} total charts")
            print("="*80 + "\n")
            return
        elif args.source == 'germany':
            scraper = GermanyScraper(verbose=args.verbose)
        elif args.source == 'poland':
            # Poland scraper returns charts directly
            charts = get_poland_charts(icao_code)
            if not charts:
                print(f"\n❌ No charts found for {icao_code}")
                sys.exit(1)
            display_charts(charts)
            print("\n" + "="*80)
            print(f"✅ Found {len(charts)} total charts")
            print("="*80 + "\n")
            return
        elif args.source == 'lithuania':
            # Lithuania scraper returns charts directly
            charts = get_lithuania_charts(icao_code)
            if not charts:
                print(f"\n❌ No charts found for {icao_code}")
                sys.exit(1)
            display_charts(charts)
            print("\n" + "="*80)
            print(f"✅ Found {len(charts)} total charts")
            print("="*80 + "\n")
            return
        elif args.source == 'latvia':
            # Latvia scraper returns charts directly
            charts = get_latvia_charts(icao_code)
            if not charts:
                print(f"\n❌ No charts found for {icao_code}")
                sys.exit(1)
            display_charts(charts)
            print("\n" + "="*80)
            print(f"✅ Found {len(charts)} total charts")
            print("="*80 + "\n")
            return
        elif args.source == 'estonia':
            # Estonia scraper returns charts directly
            charts = get_estonia_charts(icao_code)
            if not charts:
                print(f"\n❌ No charts found for {icao_code}")
                sys.exit(1)
            display_charts(charts)
            print("\n" + "="*80)
            print(f"✅ Found {len(charts)} total charts")
            print("="*80 + "\n")
            return
        elif args.source == 'finland':
            # Finland scraper returns charts directly
            charts = get_finland_charts(icao_code)
            if not charts:
                print(f"\n❌ No charts found for {icao_code}")
                sys.exit(1)
            display_charts(charts)
            print("\n" + "="*80)
            print(f"✅ Found {len(charts)} total charts")
            print("="*80 + "\n")
            return
        elif args.source == 'france':
            # France scraper returns charts directly
            charts = get_france_charts(icao_code)
            if not charts:
                print(f"\n❌ No charts found for {icao_code}")
                sys.exit(1)
            display_charts(charts)
            print("\n" + "="*80)
            print(f"✅ Found {len(charts)} total charts")
            print("="*80 + "\n")
            return
        elif args.source == 'sweden':
            # Sweden scraper returns charts directly
            charts = get_sweden_charts(icao_code)
            if not charts:
                print(f"\n❌ No charts found for {icao_code}")
                sys.exit(1)
            display_charts(charts)
            print("\n" + "="*80)
            print(f"✅ Found {len(charts)} total charts")
            print("="*80 + "\n")
            return
        elif args.source == 'norway':
            # Norway scraper returns charts directly
            charts = get_norway_charts(icao_code)
            if not charts:
                print(f"\n❌ No charts found for {icao_code}")
                sys.exit(1)
            display_charts(charts)
            print("\n" + "="*80)
            print(f"✅ Found {len(charts)} total charts")
            print("="*80 + "\n")
            return
        elif args.source == 'ireland':
            # Ireland scraper returns charts directly
            charts = get_ireland_charts(icao_code)
            if not charts:
                print(f"\n❌ No charts found for {icao_code}")
                sys.exit(1)
            display_charts(charts)
            print("\n" + "="*80)
            print(f"✅ Found {len(charts)} total charts")
            print("="*80 + "\n")
            return
        elif args.source == 'uk':
            # UK scraper returns charts directly
            charts = get_uk_charts(icao_code)
            if not charts:
                print(f"\n❌ No charts found for {icao_code}")
                sys.exit(1)
            display_charts(charts)
            print("\n" + "="*80)
            print(f"✅ Found {len(charts)} total charts")
            print("="*80 + "\n")
            return
        elif args.source == 'kosovo':
            # Kosovo scraper returns charts directly
            charts = get_kosovo_charts(icao_code)
            if not charts:
                print(f"\n❌ No charts found for {icao_code}")
                sys.exit(1)
            display_charts(charts)
            print("\n" + "="*80)
            print(f"✅ Found {len(charts)} total charts")
            print("="*80 + "\n")
            return
        elif args.source == 'aruba':
            # Dutch Caribbean/Aruba scraper returns charts directly
            charts = get_aruba_charts(icao_code)
            if not charts:
                print(f"\n❌ No charts found for {icao_code}")
                sys.exit(1)
            display_charts(charts)
            print("\n" + "="*80)
            print(f"✅ Found {len(charts)} total charts")
            print("="*80 + "\n")
            return
        elif args.source == 'cape_verde':
            # Cape Verde scraper returns charts directly
            charts = get_cape_verde_charts(icao_code)
            if not charts:
                print(f"\n❌ No charts found for {icao_code}")
                sys.exit(1)
            display_charts(charts)
            print("\n" + "="*80)
            print(f"✅ Found {len(charts)} total charts")
            print("="*80 + "\n")
            return
        elif args.source == 'algeria':
            # Algeria scraper returns charts directly
            charts = get_algeria_charts(icao_code)
            if not charts:
                print(f"\n❌ No charts found for {icao_code}")
                sys.exit(1)
            display_charts(charts)
            print("\n" + "="*80)
            print(f"✅ Found {len(charts)} total charts")
            print("="*80 + "\n")
            return
        elif args.source == 'asecna':
            # ASECNA scraper returns charts directly (17 African countries)
            charts = get_asecna_charts(icao_code)
            if not charts:
                print(f"\n❌ No charts found for {icao_code}")
                sys.exit(1)
            display_charts(charts)
            print("\n" + "="*80)
            print(f"✅ Found {len(charts)} total charts")
            print("="*80 + "\n")
            return
        elif args.source == 'djibouti':
            # Djibouti scraper returns charts directly (page refs by default, or extracts PDFs with -e)
            charts = get_djibouti_charts(icao_code, extract_pdfs=args.extract_pdfs)
            if not charts:
                print(f"\n❌ No charts found for {icao_code}")
                sys.exit(1)
            display_charts(charts)
            print("\n" + "="*80)
            print(f"✅ Found {len(charts)} total charts")
            print("="*80 + "\n")
            return
        elif args.source == 'morocco':
            # Morocco scraper returns charts directly
            charts = get_morocco_charts(icao_code)
            if not charts:
                print(f"\n❌ No charts found for {icao_code}")
                sys.exit(1)
            display_charts(charts)
            print("\n" + "="*80)
            print(f"✅ Found {len(charts)} total charts")
            print("="*80 + "\n")
            return
        elif args.source == 'somalia':
            # Somalia scraper returns charts directly (page refs by default, or extracts PDFs with -e)
            charts = get_somalia_charts(icao_code, extract_pdfs=args.extract_pdfs)
            if not charts:
                print(f"\n❌ No charts found for {icao_code}")
                sys.exit(1)
            display_charts(charts)
            print("\n" + "="*80)
            print(f"✅ Found {len(charts)} total charts")
            print("="*80 + "\n")
            return
        elif args.source == 'south_africa':
            # South Africa scraper returns charts directly
            charts = get_south_africa_charts(icao_code)
            if not charts:
                print(f"\n❌ No charts found for {icao_code}")
                sys.exit(1)
            display_charts(charts)
            print("\n" + "="*80)
            print(f"✅ Found {len(charts)} total charts")
            print("="*80 + "\n")
            return
        elif args.source == 'south_sudan':
            # South Sudan scraper returns charts directly
            charts = get_south_sudan_charts(icao_code)
            if not charts:
                print(f"\n❌ No charts found for {icao_code}")
                sys.exit(1)
            display_charts(charts)
            print("\n" + "="*80)
            print(f"✅ Found {len(charts)} total charts")
            print("="*80 + "\n")
            return
        elif args.source in ('cocesna', 'belize', 'costa_rica', 'el_salvador', 'guatemala', 'honduras', 'nicaragua'):
            # COCESNA scraper covers all Central American countries
            charts = get_cocesna_charts(icao_code)
            if not charts:
                print(f"\n❌ No charts found for {icao_code}")
                sys.exit(1)
            display_charts(charts)
            print("\n" + "="*80)
            print(f"✅ Found {len(charts)} total charts")
            print("="*80 + "\n")
            return
        elif args.source == 'chile':
            # Chile scraper returns charts directly
            charts = get_chile_charts(icao_code)
            if not charts:
                print(f"\n❌ No charts found for {icao_code}")
                sys.exit(1)
            display_charts(charts)
            print("\n" + "="*80)
            print(f"✅ Found {len(charts)} total charts")
            print("="*80 + "\n")
            return
        elif args.source == 'cuba':
            # Cuba scraper returns charts directly (page refs by default, or extracts PDFs with -e)
            charts = get_cuba_charts(icao_code, extract_pdfs=args.extract_pdfs)
            if not charts:
                print(f"\n❌ No charts found for {icao_code}")
                sys.exit(1)
            display_charts(charts)
            print("\n" + "="*80)
            print(f"✅ Found {len(charts)} total charts")
            print("="*80 + "\n")
            return
        elif args.source == 'croatia':
            # Croatia scraper returns charts directly
            charts = get_croatia_charts(icao_code)
            if not charts:
                print(f"\n❌ No charts found for {icao_code}")
                sys.exit(1)
            display_charts(charts)
            print("\n" + "="*80)
            print(f"✅ Found {len(charts)} total charts")
            print("="*80 + "\n")
            return
        elif args.source == 'cyprus':
            # Cyprus scraper returns charts directly
            charts = get_cyprus_charts(icao_code)
            if not charts:
                print(f"\n❌ No charts found for {icao_code}")
                sys.exit(1)
            display_charts(charts)
            print("\n" + "="*80)
            print(f"✅ Found {len(charts)} total charts")
            print("="*80 + "\n")
            return
        elif args.source == 'malta':
            # Malta scraper returns charts directly
            charts = get_malta_charts(icao_code)
            if not charts:
                print(f"\n❌ No charts found for {icao_code}")
                sys.exit(1)
            display_charts(charts)
            print("\n" + "="*80)
            print(f"✅ Found {len(charts)} total charts")
            print("="*80 + "\n")
            return
        elif args.source == 'denmark':
            # Denmark scraper returns charts directly
            charts = get_denmark_charts(icao_code, verbose=args.verbose)
            if not charts:
                print(f"\n❌ No charts found for {icao_code}")
                sys.exit(1)
            display_charts(charts)
            print("\n" + "="*80)
            print(f"✅ Found {len(charts)} total charts")
            print("="*80 + "\n")
            return
        elif args.source == 'uruguay':
            # Uruguay scraper returns charts directly (page refs by default, or extracts PDFs with -e)
            charts = get_uruguay_charts(icao_code, extract_pdfs=args.extract_pdfs)
            if not charts:
                print(f"\n❌ No charts found for {icao_code}")
                sys.exit(1)
            display_charts(charts)
            print("\n" + "="*80)
            print(f"✅ Found {len(charts)} total charts")
            print("="*80 + "\n")
            return
        elif args.source == 'venezuela':
            # Venezuela scraper returns charts directly
            charts = get_venezuela_charts(icao_code)
            if not charts:
                print(f"\n❌ No charts found for {icao_code}")
                sys.exit(1)
            display_charts(charts)
            print("\n" + "="*80)
            print(f"✅ Found {len(charts)} total charts")
            print("="*80 + "\n")
            return
        elif args.source == 'dominican_republic':
            # Dominican Republic scraper returns charts directly
            charts = get_dominican_republic_charts(icao_code)
            if not charts:
                print(f"\n❌ No charts found for {icao_code}")
                sys.exit(1)
            display_charts(charts)
            print("\n" + "="*80)
            print(f"✅ Found {len(charts)} total charts")
            print("="*80 + "\n")
            return
        elif args.source == 'haiti':
            # Haiti scraper returns the full AIP PDF link
            charts = get_haiti_charts(icao_code)
            if not charts:
                print(f"\n❌ No charts found for {icao_code}")
                sys.exit(1)
            display_charts(charts)
            print("\n" + "="*80)
            print(f"✅ Found {len(charts)} total charts")
            print("="*80 + "\n")
            return
        elif args.source == 'cayman':
            # Cayman Islands scraper returns the AIP Aerodrome PDF link
            charts = get_cayman_charts(icao_code)
            if not charts:
                print(f"\n❌ No charts found for {icao_code}")
                sys.exit(1)
            display_charts(charts)
            print("\n" + "="*80)
            print(f"✅ Found {len(charts)} total charts")
            print("="*80 + "\n")
            return
        elif args.source == 'panama':
            # Panama scraper returns the aerodrome PDF link
            charts = get_panama_charts(icao_code)
            if not charts:
                print(f"\n❌ No charts found for {icao_code}")
                sys.exit(1)
            display_charts(charts)
            print("\n" + "="*80)
            print(f"✅ Found {len(charts)} total charts")
            print("="*80 + "\n")
            return
        elif args.source == 'afghanistan':
            # Afghanistan scraper returns OAKB charts
            charts = get_afghanistan_charts(icao_code)
            if not charts:
                print(f"\n❌ No charts found for {icao_code}")
                sys.exit(1)
            display_charts(charts)
            print("\n" + "="*80)
            print(f"✅ Found {len(charts)} total charts")
            print("="*80 + "\n")
            return
        elif args.source == 'bahrain':
            # Bahrain eAIP scraper
            charts = get_bahrain_charts(icao_code)
            if not charts:
                print(f"\n❌ No charts found for {icao_code}")
                sys.exit(1)
            display_charts(charts)
            print("\n" + "="*80)
            print(f"✅ Found {len(charts)} total charts")
            print("="*80 + "\n")
            return
        elif args.source == 'iceland':
            # Iceland eAIP scraper
            charts = get_iceland_charts(icao_code)
            if not charts:
                print(f"\n❌ No charts found for {icao_code}")
                sys.exit(1)
            display_charts(charts)
            print("\n" + "="*80)
            print(f"✅ Found {len(charts)} total charts")
            print("="*80 + "\n")
            return
        elif args.source == 'bangladesh':
            # Bangladesh scraper returns aerodrome PDF
            charts = get_bangladesh_charts(icao_code)
            if not charts:
                print(f"\n❌ No charts found for {icao_code}")
                sys.exit(1)
            display_charts(charts)
            print("\n" + "="*80)
            print(f"✅ Found {len(charts)} total charts")
            print("="*80 + "\n")
            return
        elif args.source == 'bhutan':
            # Bhutan scraper returns AIP link
            charts = get_bhutan_charts(icao_code)
            if not charts:
                print(f"\n❌ No charts found for {icao_code}")
                sys.exit(1)
            display_charts(charts)
            print("\n" + "="*80)
            print(f"✅ Found {len(charts)} total charts")
            print("="*80 + "\n")
            return
        elif args.source == 'brunei':
            # Brunei scraper returns aerodrome charts
            charts = get_brunei_charts(icao_code)
            if not charts:
                print(f"\n❌ No charts found for {icao_code}")
                sys.exit(1)
            display_charts(charts)
            print("\n" + "="*80)
            print(f"✅ Found {len(charts)} total charts")
            print("="*80 + "\n")
            return
        elif args.source == 'hongkong':
            # Hong Kong scraper returns aerodrome charts
            charts = get_hongkong_charts(icao_code)
            if not charts:
                print(f"\n❌ No charts found for {icao_code}")
                sys.exit(1)
            display_charts(charts)
            print("\n" + "="*80)
            print(f"✅ Found {len(charts)} total charts")
            print("="*80 + "\n")
            return
        elif args.source == 'israel':
            # Israel scraper returns aerodrome charts
            charts = get_israel_charts(icao_code)
            if not charts:
                print(f"\n❌ No charts found for {icao_code}")
                sys.exit(1)
            display_charts(charts)
            print("\n" + "="*80)
            print(f"✅ Found {len(charts)} total charts")
            print("="*80 + "\n")
            return
        elif args.source == 'kuwait':
            # Kuwait DGCA scraper returns aerodrome charts (PDFs are password protected)
            charts = get_kuwait_charts(icao_code)
            if not charts:
                print(f"\n❌ No charts found for {icao_code}")
                sys.exit(1)
            display_charts(charts)
            print("\n" + "="*80)
            print(f"✅ Found {len(charts)} total charts")
            print("Note: Kuwait PDFs are password protected")
            print("="*80 + "\n")
            return
        elif args.source == 'malaysia':
            # Malaysia CAAM eAIP scraper returns aerodrome charts
            charts = get_malaysia_charts(icao_code)
            if not charts:
                print(f"\n❌ No charts found for {icao_code}")
                sys.exit(1)
            display_charts(charts)
            print("\n" + "="*80)
            print(f"✅ Found {len(charts)} total charts")
            print("="*80 + "\n")
            return
        elif args.source == 'maldives':
            # Maldives MACL AIP returns single AD 2 document per airport
            charts = get_maldives_charts(icao_code)
            if not charts:
                print(f"\n❌ No charts found for {icao_code}")
                sys.exit(1)
            display_charts(charts)
            print("\n" + "="*80)
            print(f"✅ Found {len(charts)} document (combined AD 2)")
            print("="*80 + "\n")
            return
        elif args.source == 'mongolia':
            # Mongolia AIS eAIP (Eurocontrol-style)
            charts = get_mongolia_charts(icao_code)
            if not charts:
                print(f"\n❌ No charts found for {icao_code}")
                sys.exit(1)
            display_charts(charts)
            print("\n" + "="*80)
            print(f"✅ Found {len(charts)} total charts")
            print("="*80 + "\n")
            return
        elif args.source == 'myanmar':
            # Myanmar DCA eAIP (Eurocontrol-style)
            charts = get_myanmar_charts(icao_code)
            if not charts:
                print(f"\n❌ No charts found for {icao_code}")
                sys.exit(1)
            display_charts(charts)
            print("\n" + "="*80)
            print(f"✅ Found {len(charts)} total charts")
            print("="*80 + "\n")
            return
        elif args.source == 'nepal':
            # Nepal CAAN eAIP
            charts = get_nepal_charts(icao_code)
            if not charts:
                print(f"\n❌ No charts found for {icao_code}")
                sys.exit(1)
            display_charts(charts)
            print("\n" + "="*80)
            print(f"✅ Found {len(charts)} document (combined AD 2)")
            print("="*80 + "\n")
            return
        elif args.source == 'oman':
            # Oman CAA eAIP (Eurocontrol-style)
            charts = get_oman_charts(icao_code)
            if not charts:
                print(f"\n❌ No charts found for {icao_code}")
                sys.exit(1)
            display_charts(charts)
            print("\n" + "="*80)
            print(f"✅ Found {len(charts)} total charts")
            print("="*80 + "\n")
            return
        elif args.source == 'pakistan':
            # Pakistan PAA eAIP
            charts = get_pakistan_charts(icao_code)
            if not charts:
                print(f"\n❌ No charts found for {icao_code}")
                sys.exit(1)
            display_charts(charts)
            print("\n" + "="*80)
            print(f"✅ Found {len(charts)} total charts")
            print("="*80 + "\n")
            return
        elif args.source == 'qatar':
            # Qatar CAA eAIP
            charts = get_qatar_charts(icao_code)
            if not charts:
                print(f"\n❌ No charts found for {icao_code}")
                sys.exit(1)
            display_charts(charts)
            print("\n" + "="*80)
            print(f"✅ Found {len(charts)} total charts")
            print("="*80 + "\n")
            return
        elif args.source == 'saudi_arabia':
            # Saudi Arabia SANS eAIP
            charts = get_saudi_arabia_charts(icao_code)
            if not charts:
                print(f"\n❌ No charts found for {icao_code}")
                sys.exit(1)
            display_charts(charts)
            print("\n" + "="*80)
            print(f"✅ Found {len(charts)} total charts")
            print("="*80 + "\n")
            return
        elif args.source == 'singapore':
            # Singapore CAAS eAIP
            charts = get_singapore_charts(icao_code)
            if not charts:
                print(f"\n❌ No charts found for {icao_code}")
                sys.exit(1)
            display_charts(charts)
            print("\n" + "="*80)
            print(f"✅ Found {len(charts)} total charts")
            print("="*80 + "\n")
            return
        elif args.source == 'sri_lanka':
            # Sri Lanka AASL eAIP
            charts = get_sri_lanka_charts(icao_code)
            if not charts:
                print(f"\n❌ No charts found for {icao_code}")
                sys.exit(1)
            display_charts(charts)
            print("\n" + "="*80)
            print(f"✅ Found {len(charts)} total charts")
            print("="*80 + "\n")
            return
        elif args.source == 'tajikistan':
            # Tajikistan CAICA AIP
            charts = get_tajikistan_charts(icao_code)
            if not charts:
                print(f"\n❌ No charts found for {icao_code}")
                sys.exit(1)
            display_charts(charts)
            print("\n" + "="*80)
            print(f"✅ Found {len(charts)} total charts")
            print("="*80 + "\n")
            return
        elif args.source == 'turkey':
            # Turkey AIP (requires account)
            charts = get_turkey_charts(icao_code)
            if not charts:
                print(f"\n❌ No charts found for {icao_code}")
                sys.exit(1)
            display_charts(charts)
            print("\n" + "="*80)
            print(f"✅ Found {len(charts)} total charts")
            print("="*80 + "\n")
            return
        elif args.source == 'turkmenistan':
            # Turkmenistan CAICA AIP
            charts = get_turkmenistan_charts(icao_code)
            if not charts:
                print(f"\n❌ No charts found for {icao_code}")
                sys.exit(1)
            display_charts(charts)
            print("\n" + "="*80)
            print(f"✅ Found {len(charts)} total charts")
            print("="*80 + "\n")
            return
        elif args.source == 'uzbekistan':
            # Uzbekistan UzAeroNavigation AIP
            charts = get_uzbekistan_charts(icao_code)
            if not charts:
                print(f"\n❌ No charts found for {icao_code}")
                sys.exit(1)
            display_charts(charts)
            print("\n" + "="*80)
            print(f"✅ Found {len(charts)} total charts")
            print("="*80 + "\n")
            return
        elif args.source == 'uae':
            # UAE GCAA eAIP
            charts = get_uae_charts(icao_code)
            if not charts:
                print(f"\n❌ No charts found for {icao_code}")
                sys.exit(1)
            display_charts(charts)
            print("\n" + "="*80)
            print(f"✅ Found {len(charts)} total charts")
            print("="*80 + "\n")
            return
        else:
            print(f"❌ Source '{args.source}' not implemented yet")
            sys.exit(1)
        
        # Ensure scraper is initialized for class-based scrapers
        if 'scraper' not in locals():
            print(f"❌ Internal error: scraper not initialized for source '{args.source}'")
            sys.exit(1)
        
        # Fetch charts
        if args.source == 'canada':
            charts = scraper.get_charts(icao_code, extract_pdfs=args.extract_pdfs)
        else:
            charts = scraper.get_charts(icao_code)
        
        if not charts:
            print(f"\n❌ No charts found for {icao_code}")
            sys.exit(1)
        
        # Display organized charts
        display_charts(charts)
        
        print("\n" + "="*80)
        print(f"✅ Found {len(charts)} total charts")
        print("="*80 + "\n")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

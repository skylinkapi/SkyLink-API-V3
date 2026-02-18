"""
Charts service layer that wraps the existing aerodrome charts CLI scrapers
for use as an async API service.
"""

import asyncio
import logging
import sys
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from models.v3.charts import Chart, ChartCategory, ChartsResponse

logger = logging.getLogger(__name__)

# Ensure charts_aerodrome package is importable
_charts_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'charts_aerodrome')
if _charts_dir not in sys.path:
    sys.path.insert(0, os.path.abspath(_charts_dir))


# ── ICAO prefix -> source mapping ─────────────────────────────────────────────
# Ordered from most-specific to least-specific prefixes so longer prefixes
# are checked first (e.g. 'TFF' before 'TN', 'UTD' before 'UT').

ICAO_SOURCE_RULES: List[Tuple[tuple, str]] = [
    # 3-char prefixes (must come before 2-char and 1-char)
    (('TFF',), 'france'),       # French Antilles
    (('UTD',), 'tajikistan'),   # Tajikistan
    (('UTA',), 'turkmenistan'), # Turkmenistan

    # 2-char prefixes
    (('CY', 'CZ'), 'canada'),
    (('SB', 'SD', 'SI', 'SJ', 'SN', 'SS', 'SW'), 'brazil'),
    (('SC',), 'chile'),
    (('SU',), 'uruguay'),
    (('SV',), 'venezuela'),
    (('SA', 'SE', 'SG', 'SL', 'SO', 'SY'), 'argentina'),
    (('SK',), 'colombia'),
    (('UA',), 'kazakhstan'),
    (('UC',), 'kyrgyzstan'),
    (('ZM',), 'mongolia'),
    (('ZB', 'ZP', 'ZY', 'ZG', 'ZH', 'ZU', 'ZW', 'ZL', 'ZS'), 'china'),
    (('EB',), 'belgium'),
    (('EL',), 'luxembourg'),
    (('EH',), 'netherlands'),
    (('EY',), 'lithuania'),
    (('EV',), 'latvia'),
    (('EE',), 'estonia'),
    (('EF',), 'finland'),
    (('EI',), 'ireland'),
    (('EG',), 'uk'),
    (('EK',), 'denmark'),
    (('ES',), 'sweden'),
    (('EN',), 'norway'),
    (('EP',), 'poland'),
    (('LF',), 'france'),
    (('LC',), 'cyprus'),
    (('LM',), 'malta'),
    (('LD',), 'croatia'),
    (('LT',), 'turkey'),
    (('LZ',), 'slovakia'),
    (('LO',), 'austria'),
    (('LL',), 'israel'),
    (('ED', 'ET'), 'germany'),
    (('BK',), 'kosovo'),
    (('BI',), 'iceland'),
    (('TN',), 'aruba'),        # Dutch Caribbean
    (('GV',), 'cape_verde'),
    (('DA',), 'algeria'),
    (('HD',), 'djibouti'),
    (('GM',), 'morocco'),
    (('HC',), 'somalia'),
    (('FA',), 'south_africa'),
    (('HJ',), 'south_sudan'),
    (('MU',), 'cuba'),
    (('MD',), 'dominican_republic'),
    (('MT',), 'haiti'),
    (('MW',), 'cayman'),
    (('MP',), 'panama'),
    (('MZ',), 'cocesna'),      # Belize
    (('MR',), 'cocesna'),      # Costa Rica
    (('MS',), 'cocesna'),      # El Salvador
    (('MG',), 'cocesna'),      # Guatemala
    (('MH',), 'cocesna'),      # Honduras
    (('MN',), 'cocesna'),      # Nicaragua
    (('OA',), 'afghanistan'),
    (('OB',), 'bahrain'),
    (('OE',), 'saudi_arabia'),
    (('OK',), 'kuwait'),
    (('OM',), 'uae'),
    (('OO',), 'oman'),
    (('OP',), 'pakistan'),
    (('OT',), 'qatar'),
    (('VA', 'VE', 'VI', 'VO'), 'india'),
    (('VG',), 'bangladesh'),
    (('VQ',), 'bhutan'),
    (('VY',), 'myanmar'),
    (('VN',), 'nepal'),
    (('VH',), 'hongkong'),
    (('VR',), 'maldives'),
    (('VC',), 'sri_lanka'),
    (('VT',), 'thailand'),
    (('WB',), 'brunei'),
    (('WM',), 'malaysia'),
    (('WS',), 'singapore'),
    (('UM',), 'belarus'),
    (('UG',), 'georgia'),
    (('RJ',), 'japan'),
    (('RK',), 'south_korea'),
    (('NW',), 'france'),       # New Caledonia
    (('NL',), 'france'),       # Wallis and Futuna
    (('NT',), 'france'),       # French Polynesia
    (('FM',), 'france'),       # Reunion/Mayotte
    (('UT', 'UZ'), 'uzbekistan'),
    # ASECNA - West Africa
    (('DB', 'DF', 'DI', 'DR', 'DX'), 'asecna'),
    # ASECNA - Central Africa
    (('FC', 'FE', 'FG', 'FK', 'FO', 'FT'), 'asecna'),
    # ASECNA - G* prefixes
    (('GA', 'GG', 'GO', 'GQ'), 'asecna'),

    # 1-char prefixes (last resort, most general)
    (('K',), 'faa'),           # USA
    (('Y',), 'australia'),     # Australia
]

# Sources where Russia is the catch-all for U* that didn't match earlier
_RUSSIA_EXCLUDED = {'SU', 'UA', 'UC', 'UT', 'UZ', 'UM', 'UG'}

# ── Human-readable source names ──────────────────────────────────────────────

SOURCE_NAMES: Dict[str, str] = {
    'faa': 'FAA (United States)',
    'canada': 'NAV CANADA',
    'brazil': 'DECEA (Brazil)',
    'argentina': 'ANAC (Argentina)',
    'colombia': 'Aerocivil (Colombia)',
    'chile': 'DGAC (Chile)',
    'uruguay': 'DINACIA (Uruguay)',
    'venezuela': 'INAC (Venezuela)',
    'russia': 'Russia AIP',
    'kazakhstan': 'Kazakhstan AIP',
    'kyrgyzstan': 'Kyrgyzstan AIP',
    'china': 'CAAC (China)',
    'australia': 'Airservices Australia',
    'india': 'AAI (India)',
    'japan': 'Japan AIP',
    'south_korea': 'MOLIT (South Korea)',
    'thailand': 'AEROTHAI (Thailand)',
    'germany': 'DFS (Germany)',
    'france': 'SIA (France)',
    'uk': 'NATS (United Kingdom)',
    'ireland': 'IAA (Ireland)',
    'belgium': 'skeyes (Belgium)',
    'luxembourg': 'ANA (Luxembourg)',
    'netherlands': 'LVNL (Netherlands)',
    'austria': 'Austro Control',
    'slovakia': 'LPS (Slovakia)',
    'poland': 'PANSA (Poland)',
    'finland': 'ANS Finland',
    'sweden': 'LFV (Sweden)',
    'norway': 'Avinor (Norway)',
    'denmark': 'Naviair (Denmark)',
    'estonia': 'EANS (Estonia)',
    'latvia': 'LGS (Latvia)',
    'lithuania': 'ANS (Lithuania)',
    'iceland': 'ISAVIA (Iceland)',
    'croatia': 'CCAA (Croatia)',
    'cyprus': 'DCA (Cyprus)',
    'malta': 'TM-CAD (Malta)',
    'kosovo': 'Kosovo CAA',
    'turkey': 'DHMI (Turkey)',
    'israel': 'IAA (Israel)',
    'aruba': 'DCA (Dutch Caribbean)',
    'cape_verde': 'ASA (Cape Verde)',
    'algeria': 'ENNA (Algeria)',
    'asecna': 'ASECNA (Africa)',
    'djibouti': 'Djibouti AIP',
    'morocco': 'ONDA (Morocco)',
    'somalia': 'SCAMA (Somalia)',
    'south_africa': 'ATNS (South Africa)',
    'south_sudan': 'SSCAA (South Sudan)',
    'cocesna': 'COCESNA (Central America)',
    'cuba': 'IACC (Cuba)',
    'dominican_republic': 'IDAC (Dominican Republic)',
    'haiti': 'OFNAC (Haiti)',
    'cayman': 'CIAA (Cayman Islands)',
    'panama': 'AAC (Panama)',
    'afghanistan': 'Afghanistan AIP',
    'bahrain': 'BCAA (Bahrain)',
    'saudi_arabia': 'GACA (Saudi Arabia)',
    'kuwait': 'DGCA (Kuwait)',
    'uae': 'GCAA (UAE)',
    'oman': 'PACA (Oman)',
    'pakistan': 'PCAA (Pakistan)',
    'qatar': 'QCAA (Qatar)',
    'bangladesh': 'CAAB (Bangladesh)',
    'bhutan': 'Bhutan AIP',
    'myanmar': 'DCA (Myanmar)',
    'nepal': 'CAAN (Nepal)',
    'hongkong': 'CAD (Hong Kong)',
    'maldives': 'MACL (Maldives)',
    'sri_lanka': 'AASL (Sri Lanka)',
    'brunei': 'DCA (Brunei)',
    'malaysia': 'CAAM (Malaysia)',
    'singapore': 'CAAS (Singapore)',
    'mongolia': 'MCAA (Mongolia)',
    'tajikistan': 'Tajikistan AIP',
    'turkmenistan': 'Turkmenistan AIP',
    'uzbekistan': 'UzAeroNavigation',
    'belarus': 'Belaeronavigatsia',
    'georgia': 'GCAA (Georgia)',
}


def determine_source(icao_code: str) -> str:
    """Map an ICAO code to its chart source identifier."""
    icao = icao_code.upper()

    # Check rules from most-specific to least-specific
    for prefixes, source in ICAO_SOURCE_RULES:
        if icao.startswith(prefixes):
            return source

    # Russia catch-all: any U* that didn't match specific U-prefixes above
    if icao.startswith('U') and icao[:2] not in _RUSSIA_EXCLUDED:
        return 'russia'

    # Default fallback
    return 'faa'


def _fetch_charts_sync(icao_code: str, source: str) -> List[dict]:
    """
    Synchronously fetch charts using the appropriate scraper.
    Returns raw list of chart dicts with 'name', 'url', and optionally 'type' keys.
    """
    # ── Class-based scrapers (instantiate, then call .get_charts()) ────────
    if source == 'faa':
        from sources.faa_scraper import FAAScraper
        return FAAScraper().get_charts(icao_code) or []

    if source == 'canada':
        from sources.canada_fltplan_scraper import CanadaScraper
        return CanadaScraper().get_charts(icao_code) or []

    if source == 'brazil':
        from sources.brazil_scraper import BrazilScraper
        return BrazilScraper().get_charts(icao_code) or []

    if source == 'argentina':
        from sources.argentina_scraper import ArgentinaScraper
        return ArgentinaScraper().get_charts(icao_code) or []

    if source == 'colombia':
        from sources.colombia_scraper import ColombiaScraper
        return ColombiaScraper().get_charts(icao_code) or []

    if source == 'russia':
        from sources.russia_scraper import RussiaScraper
        return RussiaScraper().get_charts(icao_code) or []

    if source == 'kazakhstan':
        from sources.kazakhstan_scraper import KazakhstanScraper
        return KazakhstanScraper().get_charts(icao_code) or []

    if source == 'kyrgyzstan':
        from sources.kyrgyzstan_scraper import KyrgyzstanScraper
        return KyrgyzstanScraper().get_charts(icao_code) or []

    if source == 'china':
        from sources.china_scraper import ChinaScraper
        return ChinaScraper().get_charts(icao_code) or []

    if source == 'australia':
        from sources.australia_scraper import AustraliaScraper
        return AustraliaScraper().get_charts(icao_code) or []

    if source == 'germany':
        from sources.germany_scraper import GermanyScraper
        return GermanyScraper().get_charts(icao_code) or []

    if source == 'india':
        from sources.india_scraper import IndiaScraper
        return IndiaScraper().get_charts(icao_code) or []

    if source == 'south_korea':
        from sources.south_korea_scraper import SouthKoreaScraper
        return SouthKoreaScraper().get_charts(icao_code) or []

    if source == 'thailand':
        from sources.thailand_scraper import ThailandScraper
        return ThailandScraper().get_charts(icao_code) or []

    # ── Function-based scrapers (call directly) ───────────────────────────
    _FUNCTION_SCRAPERS = {
        'belgium':             ('sources.belgium_luxembourg_scraper', 'get_aerodrome_charts'),
        'luxembourg':          ('sources.belgium_luxembourg_scraper', 'get_aerodrome_charts'),
        'slovakia':            ('sources.slovakia_scraper', 'get_aerodrome_charts'),
        'austria':             ('sources.austria_scraper', 'get_aerodrome_charts'),
        'netherlands':         ('sources.netherlands_scraper', 'get_aerodrome_charts'),
        'poland':              ('sources.poland_scraper', 'get_aerodrome_charts'),
        'lithuania':           ('sources.lithuania_scraper', 'get_aerodrome_charts'),
        'latvia':              ('sources.latvia_scraper', 'get_aerodrome_charts'),
        'estonia':             ('sources.estonia_scraper', 'get_aerodrome_charts'),
        'finland':             ('sources.finland_scraper', 'get_aerodrome_charts'),
        'france':              ('sources.france_scraper', 'get_aerodrome_charts'),
        'sweden':              ('sources.sweden_scraper', 'get_aerodrome_charts'),
        'norway':              ('sources.norway_scraper', 'get_aerodrome_charts'),
        'ireland':             ('sources.ireland_scraper', 'get_aerodrome_charts'),
        'uk':                  ('sources.uk_scraper', 'get_aerodrome_charts'),
        'kosovo':              ('sources.kosovo_scraper', 'get_aerodrome_charts'),
        'aruba':               ('sources.aruba_scraper', 'get_aerodrome_charts'),
        'cape_verde':          ('sources.cape_verde_scraper', 'get_aerodrome_charts'),
        'algeria':             ('sources.algeria_scraper', 'get_aerodrome_charts'),
        'asecna':              ('sources.asecna_scraper', 'get_aerodrome_charts'),
        'djibouti':            ('sources.djibouti_scraper', 'get_aerodrome_charts'),
        'morocco':             ('sources.morocco_scraper', 'get_aerodrome_charts'),
        'somalia':             ('sources.somalia_scraper', 'get_aerodrome_charts'),
        'south_africa':        ('sources.south_africa_scraper', 'get_aerodrome_charts'),
        'south_sudan':         ('sources.south_sudan_scraper', 'get_aerodrome_charts'),
        'cocesna':             ('sources.cocesna_scraper', 'get_aerodrome_charts'),
        'chile':               ('sources.chile_scraper', 'get_aerodrome_charts'),
        'cuba':                ('sources.cuba_scraper', 'get_aerodrome_charts'),
        'croatia':             ('sources.croatia_scraper', 'get_aerodrome_charts'),
        'cyprus':              ('sources.cyprus_scraper', 'get_aerodrome_charts'),
        'malta':               ('sources.malta_scraper', 'get_aerodrome_charts'),
        'denmark':             ('sources.denmark_scraper', 'get_aerodrome_charts'),
        'venezuela':           ('sources.venezuela_scraper', 'get_aerodrome_charts'),
        'uruguay':             ('sources.uruguay_scraper', 'get_aerodrome_charts'),
        'dominican_republic':  ('sources.dominican_republic_scraper', 'get_aerodrome_charts'),
        'haiti':               ('sources.haiti_scraper', 'get_aerodrome_charts'),
        'cayman':              ('sources.cayman_scraper', 'get_aerodrome_charts'),
        'panama':              ('sources.panama_scraper', 'get_aerodrome_charts'),
        'afghanistan':         ('sources.afghanistan_scraper', 'get_aerodrome_charts'),
        'bahrain':             ('sources.bahrain_scraper', 'get_aerodrome_charts'),
        'iceland':             ('sources.iceland_scraper', 'get_aerodrome_charts'),
        'bangladesh':          ('sources.bangladesh_scraper', 'get_aerodrome_charts'),
        'belarus':             ('sources.belarus_scraper', 'get_aerodrome_charts'),
        'bhutan':              ('sources.bhutan_scraper', 'get_aerodrome_charts'),
        'brunei':              ('sources.brunei_scraper', 'get_aerodrome_charts'),
        'georgia':             ('sources.georgia_scraper', 'get_aerodrome_charts'),
        'hongkong':            ('sources.hongkong_scraper', 'get_aerodrome_charts'),
        'israel':              ('sources.israel_scraper', 'get_aerodrome_charts'),
        'japan':               ('sources.japan_scraper', 'get_aerodrome_charts'),
        'kuwait':              ('sources.kuwait_scraper', 'get_aerodrome_charts'),
        'malaysia':            ('sources.malaysia_scraper', 'get_aerodrome_charts'),
        'maldives':            ('sources.maldives_scraper', 'get_aerodrome_charts'),
        'mongolia':            ('sources.mongolia_scraper', 'get_aerodrome_charts'),
        'myanmar':             ('sources.myanmar_scraper', 'get_aerodrome_charts'),
        'nepal':               ('sources.nepal_scraper', 'get_aerodrome_charts'),
        'oman':                ('sources.oman_scraper', 'get_aerodrome_charts'),
        'pakistan':             ('sources.pakistan_scraper', 'get_aerodrome_charts'),
        'qatar':               ('sources.qatar_scraper', 'get_aerodrome_charts'),
        'saudi_arabia':        ('sources.saudi_arabia_scraper', 'get_aerodrome_charts'),
        'singapore':           ('sources.singapore_scraper', 'get_aerodrome_charts'),
        'sri_lanka':           ('sources.sri_lanka_scraper', 'get_aerodrome_charts'),
        'tajikistan':          ('sources.tajikistan_scraper', 'get_aerodrome_charts'),
        'turkey':              ('sources.turkey_scraper', 'get_aerodrome_charts'),
        'turkmenistan':        ('sources.turkmenistan_scraper', 'get_aerodrome_charts'),
        'uzbekistan':          ('sources.uzbekistan_scraper', 'get_aerodrome_charts'),
    }

    if source in _FUNCTION_SCRAPERS:
        module_path, func_name = _FUNCTION_SCRAPERS[source]
        import importlib
        mod = importlib.import_module(module_path)
        func = getattr(mod, func_name)
        return func(icao_code) or []

    raise ValueError(f"Unknown chart source: {source}")


def _categorize_chart(chart_info: dict) -> ChartCategory:
    """
    Categorize a raw chart dict into a ChartCategory.
    Replicates the logic from aerodrome_charts_cli.categorize_chart().
    """
    chart_name = chart_info.get('name', '').lower()
    chart_type = chart_info.get('type', '').lower()

    # Use explicit type field first
    if chart_type == 'star':
        return ChartCategory.STAR
    if chart_type in ('departure', 'sid'):
        return ChartCategory.SID
    if chart_type in ('approach', 'iap', 'app'):
        return ChartCategory.APP
    if chart_type in ('gnd', 'ground'):
        return ChartCategory.GND
    if chart_type == 'gen':
        return ChartCategory.GEN

    # airport_diagram type
    if chart_type == 'airport_diagram':
        if any(kw in chart_name for kw in (
            'procedure', 'requirement', 'operation', 'minimum',
            'reduced take-off', 'reduced takeoff', 'alternate',
            'takeoff minimum', 'legend', 'note'
        )):
            return ChartCategory.GEN
        return ChartCategory.GND

    # Keyword-based fallback
    if any(kw in chart_name for kw in (
        'airport diagram', 'taxi', 'hot spot', 'lahso', 'parking',
        'apron', 'ground movement', 'docking', 'adc', 'apdc', 'gmc'
    )):
        return ChartCategory.GND

    if any(kw in chart_name for kw in (
        'minimum', 'alternate', 'takeoff minimum', 'legend',
        'procedure', 'requirement', 'operation'
    )):
        if not any(kw in chart_name for kw in ('ils', 'rnav', 'vor', 'approach', 'loc')):
            return ChartCategory.GEN

    if any(kw in chart_name for kw in (' arrival', 'star')):
        if 'departure' not in chart_name and ' dp' not in chart_name and 'ground' not in chart_name:
            return ChartCategory.STAR

    if any(kw in chart_name for kw in ('departure', ' dp ', 'sid')):
        if 'ground' not in chart_name:
            return ChartCategory.SID

    if any(kw in chart_name for kw in (
        'approach', 'iap', 'ils', 'rnav', 'rnp', 'vor', 'ndb',
        'gps', 'loc', 'tacan', 'visual', 'aoc', 'patc'
    )):
        return ChartCategory.APP

    return ChartCategory.GEN


class ChartsService:
    """Service for fetching and categorizing aerodrome charts."""

    def determine_source(self, icao_code: str) -> str:
        """Map ICAO code to chart source identifier."""
        return determine_source(icao_code)

    async def get_charts(self, icao_code: str, source: Optional[str] = None) -> ChartsResponse:
        """
        Fetch and categorize charts for an airport.

        Runs the synchronous scraper in a thread pool so it doesn't block
        the event loop.
        """
        icao = icao_code.upper().strip()
        resolved_source = source or determine_source(icao)

        logger.info("Fetching charts for %s from source %s", icao, resolved_source)

        # Run synchronous scraper in thread pool
        raw_charts = await asyncio.to_thread(_fetch_charts_sync, icao, resolved_source)

        # Categorize into response structure
        categorized: Dict[ChartCategory, List[Chart]] = {cat: [] for cat in ChartCategory}

        for raw in raw_charts:
            category = _categorize_chart(raw)
            categorized[category].append(Chart(
                name=raw['name'],
                url=raw['url'],
                category=category,
            ))

        # Remove empty categories
        categorized = {k: v for k, v in categorized.items() if v}

        return ChartsResponse(
            icao_code=icao,
            source=resolved_source,
            charts=categorized,
            total_count=len(raw_charts),
            fetched_at=datetime.utcnow(),
        )

    def get_supported_sources(self) -> List[dict]:
        """Return list of all supported chart sources with their ICAO prefixes."""
        source_prefixes: Dict[str, List[str]] = {}

        for prefixes, source in ICAO_SOURCE_RULES:
            source_prefixes.setdefault(source, []).extend(prefixes)

        # Add Russia manually since it's a catch-all
        source_prefixes.setdefault('russia', []).append('U* (except UA,UC,UG,UM,UT,UZ)')

        result = []
        for source_id, prefixes in source_prefixes.items():
            result.append({
                'source_id': source_id,
                'name': SOURCE_NAMES.get(source_id, source_id),
                'icao_prefixes': prefixes,
            })

        return result


# Global singleton
charts_service = ChartsService()

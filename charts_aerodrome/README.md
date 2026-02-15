# Aerodrome Charts CLI

Multi-country aerodrome chart scraper supporting 40+ national aviation authorities. Each scraper extracts PDF chart links for airports worldwide and categorizes them into standardized types (GEN, GND, SID, STAR, APP).

## Installation

```bash
# Aerodrome Charts CLI

![SkyLink logo](SkyLink_black.svg)

Copyright (c) 2026 SkyLink API — Aerodrome Charts CLI

Overview
--------

`Aerodrome Charts CLI` is a multi-country aerodrome chart scraper and CLI tool that extracts PDF chart links for airports worldwide and classifies the charts into the standard aviation categories: `GEN`, `GND`, `SID`, `STAR`, and `APP`.

This repository contains a set of per-country scrapers (in `sources/`) using a combination of HTML parsing, JSON APIs, and browser automation where required.

About SkyLink API
------------------

SkyLink API provides comprehensive aviation data, including real-time flight information, airline and airport details, weather forecasts, and live flight tracking. It's designed for developers to easily integrate aviation data into their applications, ensuring high reliability and global coverage.

This project is published under the SkyLink API brand and is intended to be used as a developer utility to collect and present aerodrome chart links programmatically.

Installation
------------

Create a virtual environment and install the required dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Optional dependencies (only if needed by specific scrapers):

- `selenium` + `webdriver-manager` — for JavaScript-heavy AIP web apps
- `pymupdf` — used by a small subset of scripts that inspect PDFs

Quick Usage
-----------

Auto-detect source from ICAO: 

```powershell
python aerodrome_charts_cli.py LFPG
```

Specify source explicitly:

```powershell
python aerodrome_charts_cli.py LFPG --source france --verbose
```

How the scrapers behave (compatibility categories)
-------------------------------------------------

Each country scraper falls into one of the following compatibility categories:

- `Direct PDF chart links` — scraper returns direct links to individual chart PDF files (best case)
- `AIP PDF package` — scraper returns links to a combined PDF AIP (regional or country AIP) that contains charts as pages (needs local extraction)
- `AIP homepage links` — scraper only returns the AIP landing page or menu (manual navigation required)
- `Paid/Restricted` — AIP requires payment / login or is otherwise behind a paywall (manual/paid access required)

Response-time estimates
-----------------------

Estimates are provided as a guideline and depend on network conditions and remote server performance. They are grouped as:

- Fast: < 3s (recommended)
- Moderate: 3–10s
- Slow: > 10s (often Selenium-driven)

Per-country compatibility table
-------------------------------

The table below was generated from the `sources/` directory and contains an inferred compatibility classification and a conservative response-time estimate. These are intended as guidance and should be verified against real runs for high accuracy.

| Country / Module | Source file | Compatibility | Expected response time |
|---|---:|---|---:|
 
| Afghanistan | `afghanistan_scraper.py` | Direct PDF links (requests) — Free | ~500–1,200 ms |
| Albania | `albania_scraper.py` | Direct PDF links (Eurocontrol eAIP) — Free | ~1,000–3,500 ms |
| Algeria | `algeria_scraper.py` | Direct PDF links — Free | ~1,000–2,000 ms |
| Argentina | `argentina_scraper.py` | Selenium (JS SPA) — Direct PDF extraction; slower | ~20,000–40,000 ms (Selenium)
| Armenia | `armenia_scraper.py` | Direct PDF links (Eurocontrol eAIP) — Free | ~500–900 ms |
| Aruba | `aruba_scraper.py` | Direct PDF links — Free/verify | ~500–1,000 ms |
| ASECNA (multiple African states) | `asecna_scraper.py` | AIP/Regional package or PDF links — Free | ~800–2,000 ms |
| Australia | `australia_scraper.py` | Direct PDF links / AIP pages — Free | ~1,500–4,500 ms |
| Austria | `austria_scraper.py` | Direct chart PDFs (Eurocontrol) — Free | ~600–1,200 ms |
| Bahrain | `bahrain_scraper.py` | Direct PDF links — Free | ~800–1,800 ms |
| Bangladesh | `bangladesh_scraper.py` | Direct AIP/links — Free | ~700–1,500 ms |
| Belarus | `belarus_scraper.py` | Eurocontrol eAIP (direct PDFs) — Free | ~700–2,200 ms |
| Belgium & Luxembourg | `belgium_luxembourg_scraper.py` | Direct PDFs (eAIP) — Free | ~800–1,500 ms |
| Bhutan | `bhutan_scraper.py` | AIP links (country AIP) — Free/verify | ~800–1,800 ms |
| Bosnia & Herzegovina | `bosnia_scraper.py` | Eurocontrol eAIP — Direct PDFs | ~600–1,000 ms |
| Brazil | `brazil_scraper.py` | Direct PDFs / API — Free | ~1,500–4,000 ms |
| Brunei | `brunei_scraper.py` | Direct AIP PDFs or links — Free | ~800–1,800 ms |
| Canada (FLTPlan) | `canada_fltplan_scraper.py` | Direct PDFs (FLTPlan) — Free; optional PyMuPDF for PDF processing | ~1,000–3,500 ms |
| Cape Verde | `cape_verde_scraper.py` | AIP link or PDF — Free/verify | ~1,500–2,000 ms |
| Cayman | `cayman_scraper.py` | PDF links — Free | ~800–1,500 ms |
| Chile | `chile_scraper.py` | Direct PDFs or AIP PDFs — Free | ~800–2,000 ms |
| China | `china_scraper.py` | Selenium (JS app) — slower; extracts direct PDFs if available | ~20,000–60,000 ms (Selenium)
| COCESNA (Central America) | `cocesna_scraper.py` | Regional AIP links / PDFs — Free | ~800–2,500 ms |
| Colombia | `colombia_scraper.py` | Direct PDFs — Free | ~1,000–4,000 ms |
| Croatia | `croatia_scraper.py` | Eurocontrol / AIP PDFs — Free | ~700–1,500 ms |
| Cuba | `cuba_scraper.py` | AIP links or PDFs — Free/verify | ~1,000–2,000 ms |
| Cyprus | `cyprus_scraper.py` | PDF links — Free | ~800–1,400 ms |
| Czech Republic | `czech_scraper.py` | Eurocontrol eAIP — Direct PDFs | ~600–1,200 ms |
| Denmark | `denmark_scraper.py` | Selenium (SPA) fallback available; slower | ~10,000–40,000 ms (Selenium)
| Djibouti | `djibouti_scraper.py` | Selenium helper for SPA — may require Selenium | ~5,000–30,000 ms (Selenium) |
| Dominican Republic | `dominican_republic_scraper.py` | AIP links / PDFs — Free | ~800–1,800 ms |
| Estonia | `estonia_scraper.py` | Eurocontrol eAIP — Direct PDFs | ~700–1,400 ms |
| FAA (USA) | `faa_scraper.py` | Direct PDFs via FAA pages — Free | ~500–1,500 ms |
| Finland | `finland_scraper.py` | Direct AIP PDFs — Moderate | ~3,000–12,000 ms |
| France | `france_scraper.py` | Direct PDF charts (eAIP media path) — Free | ~1,000–4,000 ms |
| Georgia | `georgia_scraper.py` | AIP links / PDFs — Free | ~700–1,500 ms |
| Germany | `germany_scraper.py` | Large set of PDFs; may be slower for full airport sets | ~5,000–25,000 ms |
| Haiti | `haiti_scraper.py` | AIP PDFs / links — Free/verify | ~800–1,800 ms |
| Hong Kong | `hongkong_scraper.py` | Direct PDFs — Free | ~800–1,600 ms |
| Hungary | `hungary_scraper.py` | Eurocontrol eAIP — Direct PDFs | ~600–1,300 ms |
| Iceland | `iceland_scraper.py` | AIP links / PDFs — Free | ~700–1,500 ms |
| India | `india_scraper.py` | Direct PDFs / AIP portal — Free | ~1,000–2,500 ms |
| Ireland | `ireland_scraper.py` | Direct PDF links — Free | ~600–900 ms |
| Israel | `israel_scraper.py` | AIP links / PDFs — Free | ~700–1,500 ms |
| Japan | `japan_scraper.py` | JSON/API / fast — Direct PDF links via API | ~10–500 ms |
| Kazakhstan | `kazakhstan_scraper.py` | Direct PDFs — Free | ~700–1,200 ms |
| Kosovo | `kosovo_scraper.py` | Eurocontrol eAIP — Direct PDFs | ~700–1,200 ms |
| Kuwait | `kuwait_scraper.py` | AIP PDFs / links — Free | ~800–1,800 ms |
| Kyrgyzstan | `kyrgyzstan_scraper.py` | Direct PDFs — Free | ~500–1,000 ms |
| Latvia | `latvia_scraper.py` | Eurocontrol eAIP — Direct PDFs | ~700–1,500 ms |
| Lithuania | `lithuania_scraper.py` | Selenium required (Cloudflare/SPA) — Slow | ~20,000–40,000 ms (Selenium)
| Malaysia | `malaysia_scraper.py` | Direct PDFs / AIP pages — Free | ~800–1,800 ms |
| Maldives | `maldives_scraper.py` | AIP PDFs / links — Free | ~800–1,500 ms |
| Malta | `malta_scraper.py` | AIP PDF / links — Free | ~800–1,600 ms |
| Mongolia | `mongolia_scraper.py` | AIP links / PDFs — Free/verify | ~800–1,800 ms |
| Morocco | `morocco_scraper.py` | AIP links — Free | ~800–2,000 ms |
| Myanmar | `myanmar_scraper.py` | Eurocontrol-like eAIP — Direct PDFs | ~800–1,800 ms |
| Nepal | `nepal_scraper.py` | AIP PDFs / links — Free | ~800–1,800 ms |
| Netherlands | `netherlands_scraper.py` | Direct PDFs (LVNL) — Free | ~800–2,400 ms |
| New Zealand | `new_zealand_scraper_json.py` | JSON API — Fast, direct chart URLs | ~50–500 ms |
| North Macedonia | `north_macedonia_scraper.py` | Eurocontrol eAIP — Direct PDFs | ~500–900 ms |
| Norway | `norway_scraper.py` | Direct PDFs — Free | ~800–2,300 ms |
| Oman | `oman_scraper.py` | AIP links/PDFs — Free | ~900–1,800 ms |
| Pakistan | `pakistan_scraper.py` | AIP links / PDFs — Free/verify | ~800–1,800 ms |
| Panama | `panama_scraper.py` | AIP links / PDFs — Free | ~800–1,800 ms |
| Poland | `poland_scraper.py` | Direct PDFs — Free | ~700–2,400 ms |
| Portugal | `portugal_scraper.py` | Direct PDFs — Free | ~600–900 ms |
| Qatar | `qatar_scraper.py` | AIP links / PDFs — Free | ~800–1,800 ms |
| Romania | `romania_scraper.py` | Eurocontrol eAIP — Direct PDFs | ~700–1,300 ms |
| Russia | `russia_scraper.py` | CAIGA AIP — Direct PDF links or menu parsing | ~1,000–6,500 ms |
| Saudi Arabia | `saudi_arabia_scraper.py` | AIP links / PDFs — Free/verify | ~800–1,800 ms |
| Serbia | `serbia_scraper.py` | Eurocontrol eAIP — Direct PDFs | ~600–1,200 ms |
| Singapore | `singapore_scraper.py` | Direct PDFs — Free | ~800–1,500 ms |
| Slovakia | `slovakia_scraper.py` | Eurocontrol eAIP — Direct PDFs | ~700–2,900 ms |
| Slovenia | `slovenia_scraper.py` | Eurocontrol eAIP — Direct PDFs | ~300–900 ms |
| Somalia | `somalia_scraper.py` | AIP pages / links — Free/verify | ~800–1,800 ms |
| South Africa | `south_africa_scraper.py` | AIP links / PDFs — Free | ~800–1,800 ms |
| South Korea | `south_korea_scraper.py` | Direct PDFs — Free | ~400–800 ms |
| South Sudan | `south_sudan_scraper.py` | AIP link — Free/verify | ~1,000–2,500 ms |
| Spain | `spain_scraper.py` | ENAIRE eAIP — Direct PDFs | ~700–1,400 ms |
| Sri Lanka | `sri_lanka_scraper.py` | AIP links/PDFs — Free | ~800–1,800 ms |
| Sweden | `sweden_scraper.py` | Direct PDFs — Moderate | ~2,000–8,500 ms |
| Taiwan | `taiwan_scraper.py` | API/JSON or PDF links — Moderate | ~1,000–9,000 ms |
| Tajikistan | `tajikistan_scraper.py` | AIP links — Free/verify | ~800–1,800 ms |
| Thailand | `thailand_scraper.py` | Direct PDFs — Free | ~1,000–2,500 ms |
| Turkey | `turkey_scraper.py` | AIP links / PDFs — Free | ~800–1,800 ms |
| Turkmenistan | `turkmenistan_scraper.py` | Links/PDFs — Free/verify | ~800–1,800 ms |
| UAE | `uae_scraper.py` | Direct PDFs / AIP pages — Free | ~800–1,800 ms |
| UK | `uk_scraper.py` | NATS eAIP / AD charts — Direct PDFs | ~600–1,800 ms |
| Uruguay | `uruguay_scraper.py` | AIP PDFs / links — Free | ~800–1,800 ms |
| Uzbekistan | `uzbekistan_scraper.py` | AIP links / PDFs — Free | ~800–1,800 ms |
| Venezuela | `venezuela_scraper.py` | AIP links / PDFs — Free/verify | ~800–1,800 ms |

Notes & Verification
--------------------

- The compatibility and time estimates above are conservative, inferred from each scraper's implementation pattern (requests/BeautifulSoup vs Selenium vs JSON API). They should be validated by real-world runs for exact timings.
- `Selenium`-based scrapers will require a working browser driver and will be significantly slower (tens of seconds) compared to `requests`-based scrapers.
- If a country is marked `AIP homepage` or `Paid/Restricted`, the scraper may intentionally return top-level AIP links due to site structure or legal restrictions; check that country's scraper file in `sources/` for implementation details.

World Map (legend + coloration)
--------------------------------

Below is a simplified embedded SVG that shows a legend and marks countries by compatibility class. This is a schematic; for production-quality maps replace this with a GeoJSON-based map (e.g., using `geojson` and `d3` or a static world SVG converted from naturalearth data).

Legend:

- Green: Direct PDF chart links (fast)
- Yellow: AIP PDF package (moderate)
- Orange: AIP homepage links / partial (manual)
- Red: Selenium / slow / SPA (requires browser)

Embedded schematic map (approximate)

```svg
<svg width="900" height="280" xmlns="http://www.w3.org/2000/svg">
   <!-- background -->
   <rect width="100%" height="100%" fill="#ffffff"/>
   <!-- legend -->
   <g font-family="Arial" font-size="12">
      <rect x="10" y="10" width="14" height="14" fill="#2ecc71" />
      <text x="30" y="22">Direct PDF chart links (fast)</text>
      <rect x="10" y="32" width="14" height="14" fill="#f1c40f" />
      <text x="30" y="44">AIP PDF package (moderate)</text>
      <rect x="10" y="54" width="14" height="14" fill="#e67e22" />
      <text x="30" y="66">AIP homepage / partial (manual)</text>
      <rect x="10" y="76" width="14" height="14" fill="#e74c3c" />
      <text x="30" y="88">Selenium / slow / SPA</text>
   </g>
   <!-- schematic world (very simplified rectangles to indicate regions) -->
   <g transform="translate(300,20)">
      <!-- Americas -->
      <rect x="-150" y="20" width="120" height="60" fill="#2ecc71" stroke="#000"/>
      <text x="-110" y="55" font-size="10">Americas (many: direct PDFs)</text>
      <!-- Europe -->
      <rect x="0" y="0" width="160" height="70" fill="#2ecc71" stroke="#000"/>
      <text x="20" y="40" font-size="10">Europe (eAIP — mostly direct)</text>
      <!-- Africa -->
      <rect x="30" y="90" width="140" height="70" fill="#f1c40f" stroke="#000"/>
      <text x="40" y="130" font-size="10">Africa (regional / mixed)</text>
      <!-- Asia -->
      <rect x="180" y="10" width="220" height="120" fill="#f1c40f" stroke="#000"/>
      <text x="200" y="70" font-size="10">Asia (mixed, includes Selenium cases)</text>
      <!-- Oceania -->
      <rect x="420" y="90" width="80" height="50" fill="#2ecc71" stroke="#000"/>
      <text x="410" y="130" font-size="10">Oceania (JSON/API fast)</text>
   </g>
</svg>
```

Developer notes
---------------

- To debug a country scraper, open `sources/<country>_scraper.py` and read the docstring — each file includes notes about site-specific workarounds (URL encoding, iframe handling, AIRAC structure, or Selenium requirements).
- If a scraper uses Selenium, install `selenium` and `webdriver-manager` and follow the platform-specific driver instructions.
- For contributions: keep new scrapers consistent with the repo's chart dictionary format: `{'name': str, 'url': str, 'type': str}` where `type` is optional but recommended.

License & Attribution
---------------------

Copyright (c) 2026 SkyLink API. All rights reserved.

This documentation and the `Aerodrome Charts CLI` project are published under the SkyLink API brand. Please contact SkyLink API for licensing or redistribution questions.

Appendix — quick reference
--------------------------

- Main entry: `aerodrome_charts_cli.py`
- Scrapers directory: `sources/` — one file per country/authority
- Chart dict format: `{'name': str, 'url': str, 'type': str}`

If you want, I can now:

 - run a verification pass that invokes each scraper for one example ICAO and records real response times, or
 - produce a GeoJSON-based world map with exact country coloring (requires mapping ISO names → scraper entries).

---

Generated: 2026-02-08

| 🟢 Low | < 3,000ms | Fast response, simple HTTP requests |
| 🟡 Medium | 3,000ms - 10,000ms | Moderate response, multiple requests or parsing |
| 🔴 High | > 10,000ms | Slow response, typically Selenium-based scrapers |

## Detailed Country Reports

### ✅ Working Scrapers (36 countries)

#### 🟢 Fast (< 3 seconds)

| Country | Test ICAO | Charts | Time | Notes |
|---------|-----------|--------|------|-------|
| Armenia | UDYZ | 36 | 727ms | Eurocontrol eAIP, fast HTML parsing |
| Slovenia | LJLJ | 32 | 341ms | Eurocontrol eAIP, efficient scraper |
| North Macedonia | LWSK | 12 | 532ms | Eurocontrol eAIP |
| Kyrgyzstan | UCFM | 17 | 588ms | Simple HTML structure |
| Bosnia | LQSA | 19 | 621ms | Eurocontrol eAIP |
| Ireland | EIDW | 43 | 645ms | Direct chart links |
| Czech Republic | LKPR | 34 | 780ms | Well-structured AIP |
| Portugal | LPPT | 28 | 783ms | NAV Portugal AIP |
| Serbia | LYBE | 28 | 886ms | Eurocontrol eAIP |
| Kazakhstan | UAAA | 58 | 883ms | Many charts, efficient parsing |
| Austria | LOWW | 35 | 1,038ms | Austrocontrol eAIP |
| FAA (USA) | KJFK | 39 | 1,109ms | Official FAA source |
| Kosovo | BKPR | 34 | 1,137ms | Eurocontrol eAIP |
| Belgium | EBBR | 62 | 1,175ms | Skeyes eAIP |
| Romania | LROP | 27 | 1,258ms | AISRO eAIP |
| Hungary | LHBP | 36 | 1,317ms | HungaroControl eAIP |
| Spain | LEMD | 50 | 1,391ms | ENAIRE eAIP |
| Estonia | EETN | 23 | 1,432ms | EANS eAIP |
| Latvia | EVRA | 29 | 1,516ms | LGS eAIP |
| UK | EGLL | 62 | 1,708ms | NATS Aurora eAIP |
| Belarus | UMMS | 27 | 2,206ms | BAN eAIP |
| Norway | ENGM | 93 | 2,289ms | Avinor eAIP, many charts |
| Netherlands | EHAM | 65 | 2,396ms | LVNL eAIP |
| Poland | EPWA | 37 | 2,467ms | PANSA eAIP |
| Slovakia | LZIB | 35 | 2,924ms | LPS eAIP |
| New Zealand | NZAA | 65 | 3ms | Pre-scraped JSON database |
| Japan | RJTT | 1 | 1ms | Pre-scraped JSON database |

#### 🟡 Medium (3-10 seconds)

| Country | Test ICAO | Charts | Time | Notes |
|---------|-----------|--------|------|-------|
| Albania | LATI | 18 | 3,359ms | Multiple page requests |
| Colombia | SKBO | 98 | 3,640ms | Large number of charts |
| Brazil | SBGR | 58 | 3,967ms | Multiple API calls |
| Australia | YSSY | 62 | 4,004ms | Airservices Australia |
| Russia | UUEE | 70 | 6,555ms | JSON backup or web scraping |
| Sweden | ESSA | 50 | 8,615ms | Multiple page parsing |
| Taiwan | RCTP | 62 | 8,841ms | CAA Taiwan API |

#### 🔴 Slow (> 10 seconds)

| Country | Test ICAO | Charts | Time | Notes |
|---------|-----------|--------|------|-------|
| Finland | EFHK | 48 | 10,710ms | Multiple PDF page downloads |
| Germany | EDDF | 301 | 19,865ms | Very large chart set, Selenium |
| Argentina | SAEZ | 10 | 21,062ms | Selenium-based, JavaScript SPA |
| China | ZBAA | 6 | 26,185ms | Selenium-based, Vue.js app |
| Lithuania | EYVI | 21 | 32,898ms | Complex navigation, slow server |

### ⚠️ No Charts Found (4 countries)

| Country | Test ICAO | Time | Issue |
|---------|-----------|------|-------|
| Aruba | TNCA | 937ms | Could not determine current AIP version |
| Cape Verde | GVAC | 1,802ms | Airport not found in AIP |
| Djibouti | HDAM | 413ms | Could not determine current AIP version |
| Kenya | HKJK | 2,062ms | Website structure may have changed |

### ❌ Errors (6 countries)

| Country | Test ICAO | Issue |
|---------|-----------|-------|
| Canada | CYYZ | Missing PyMuPDF dependency |
| India | VIDP | ✅ Working |
| Myanmar | VYYY | ✅ Working |
| South Korea | RKSI | ✅ Working |
| Thailand | VTBS | Import error - scraper needs update |

## Chart Categories

All charts are categorized into 5 types:

| Category | Description | Examples |
|----------|-------------|----------|
| **GEN** | General information | Procedures, requirements, minimums, legends |
| **GND** | Ground charts | Airport diagrams, taxi charts, parking |
| **SID** | Standard Instrument Departure | Departure procedures |
| **STAR** | Standard Terminal Arrival | Arrival procedures |
| **APP** | Approach procedures | ILS, RNAV, VOR, NDB approaches |

## Architecture

### Scraper Types

1. **Class-based scrapers**: FAA, Canada, Brazil, Argentina, Colombia, Russia, Kazakhstan, Kyrgyzstan, China, Australia, Germany
2. **Function-based scrapers**: All others use `get_aerodrome_charts(icao_code)` function

### Technology Stack

- **HTTP requests**: `requests` + `BeautifulSoup` for most scrapers
- **Selenium**: Argentina, Colombia, China, Germany, Myanmar (JavaScript-heavy sites)
- **JSON databases**: New Zealand, Japan, Russia (pre-scraped data)

## File Structure

```
aerodrome_charts_cli.py     # Main CLI entry point
sources/
├── faa_scraper.py          # USA (FAA)
├── canada_scraper.py       # Canada
├── brazil_scraper.py       # Brazil
├── argentina_scraper.py    # Argentina (Selenium)
├── ...                     # 40+ country scrapers
requirements.txt            # Python dependencies
AIP New Zealand.json        # Pre-scraped NZ data
AIP Russia.json             # Pre-scraped Russia data
```

## Requirements

- Python 3.8+
- requests >= 2.31.0
- beautifulsoup4 >= 4.12.0
- lxml >= 4.9.0
- selenium (optional, for JS-heavy sites)
- webdriver-manager (optional, for Selenium)
- pymupdf (optional, for Canada)

## Contributing

When adding a new country scraper:

1. Create `sources/{country}_scraper.py`
2. Implement either:
   - Class with `get_charts(icao_code)` method, or
   - Function `get_aerodrome_charts(icao_code)`
3. Return list of `{'name': str, 'url': str, 'type': str}`
4. Add ICAO prefix detection in `aerodrome_charts_cli.py`
5. Add import statement

## License

MIT License

## Last Tested

February 4, 2026

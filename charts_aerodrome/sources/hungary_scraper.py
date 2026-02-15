#!/usr/bin/env python3
"""
Hungary eAIP scraper (LH* prefixes)
- Always pulls the latest available AIRAC from https://ais-en.hungarocontrol.hu/aip/
- Parses AD 2.24 chart links from the airport page and resolves them to absolute URLs
"""

import re
from datetime import datetime
from typing import List, Dict, Tuple
from urllib.parse import urljoin, urlparse, urlunparse, quote

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://ais-en.hungarocontrol.hu/aip/"
HEADERS = {"User-Agent": "Mozilla/5.0 (charts-aerodrome scraper)"}


def _encode_url(url: str) -> str:
    """URL-encode each path segment to keep spaces/utf-8 safe."""
    parsed = urlparse(url)
    encoded_path = "/".join(quote(part, safe="") for part in parsed.path.split("/"))
    return urlunparse((parsed.scheme, parsed.netloc, encoded_path, "", "", ""))


def _get_airac_dates(session: requests.Session) -> List[str]:
    """Return AIRAC effective dates found on the site, newest-first."""
    resp = session.get(BASE_URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "lxml")
    candidates: List[Tuple[datetime, str, bool]] = []

    for tr in soup.find_all("tr"):
        text = " ".join(tr.stripped_strings)
        if not text:
            continue

        dates = re.findall(r"\d{4}-\d{2}-\d{2}", text)
        if not dates:
            continue

        effective_date = dates[-1]
        try:
            effective_dt = datetime.strptime(effective_date, "%Y-%m-%d")
        except ValueError:
            continue

        has_download = "download" in text.lower()
        candidates.append((effective_dt, effective_date, has_download))

    if not candidates:
        raise RuntimeError("Could not locate AIRAC dates on HungaroControl AIP page")

    # Sort newest first; prefer downloadable ones
    candidates.sort(key=lambda x: x[0], reverse=True)
    preferred = [c for c in candidates if c[2]]
    ordered = preferred + [c for c in candidates if c not in preferred]
    return [c[1] for c in ordered]


def _fetch_airport_html(icao: str, airac_dates: List[str], session: requests.Session) -> Tuple[str, str, str]:
    """Download the airport AD 2 page from the newest available AIRAC."""
    suffixes = ["en-HU", "en-GB", "en"]
    date_variants = [
        "{date}/{date}-AIRAC/html/eAIP/",  # frameset structure
        "{date}-AIRAC/html/eAIP/",        # direct
        "{date}/html/eAIP/",              # fallback
    ]
    errors = []

    for airac_date in airac_dates:
        for suffix in suffixes:
            for variant in date_variants:
                page_url = f"{BASE_URL}{variant.format(date=airac_date)}LH-AD-2.{icao}-{suffix}.html"
                resp = session.get(page_url, headers=HEADERS, timeout=30)
                if resp.status_code == 200:
                    return resp.text, page_url, airac_date
                errors.append((page_url, resp.status_code))

    debug_info = "; ".join(f"{u} -> {code}" for u, code in errors[:5])  # limit size
    raise RuntimeError(f"Could not fetch airport page for {icao}: {debug_info}")


def _categorize_chart(name: str) -> str:
    """Rough categorization for downstream CLI grouping."""
    upper = name.upper()

    if any(k in upper for k in ["SID", "DEPARTURE"]):
        return "SID"
    if any(k in upper for k in ["STAR", "ARRIVAL"]):
        return "STAR"
    if any(k in upper for k in ["ILS", "RNP", "RNAV", "VOR", "NDB", "APP", "IAC", "IAP", "LOC"]):
        return "Approach"
    if any(k in upper for k in ["ADC", "TAXI", "PDC", "PARKING", "DOCKING", "AERODROME CHART", "GROUND MOVEMENT", "AOCA"]):
        return "Airport Diagram"
    return "General"


def _derive_chart_name(link) -> str:
    """Find the best human-readable chart name near the link."""
    href = link.get("href", "")
    filename = href.split("/")[-1]

    # Prefer explicit anchor text
    name = link.get_text(strip=True)
    if name:
        return name

    # Try image alt inside the link
    img = link.find("img")
    if img and img.get("alt"):
        alt = img.get("alt", "").strip()
        if alt:
            return alt

    # Try the previous table row text (often holds the label)
    tr = link.find_parent("tr")
    if tr:
        prev_tr = tr.find_previous("tr")
        if prev_tr:
            prev_text = " ".join(prev_tr.stripped_strings)
            if prev_text:
                return prev_text

    # Fallback to filename without extension
    return re.sub(r"[_-]+", " ", filename.rsplit(".", 1)[0]).strip()


def get_aerodrome_charts(icao_code: str) -> List[Dict[str, str]]:
    """Return chart metadata for a Hungarian airport (LH**)."""
    icao = icao_code.upper()
    if not icao.startswith("LH") or len(icao) != 4:
        raise ValueError(f"Invalid Hungarian ICAO code: {icao_code}")

    session = requests.Session()
    airac_dates = _get_airac_dates(session)
    html, page_url, airac_date = _fetch_airport_html(icao, airac_dates, session)

    soup = BeautifulSoup(html, "lxml")
    charts: List[Dict[str, str]] = []
    seen = set()

    for link in soup.find_all("a", href=True):
        href = link["href"]
        href_lower = href.lower()

        if "graphics/eaip" not in href_lower:
            continue
        if not any(href_lower.endswith(ext) for ext in [".pdf", ".png", ".jpg", ".jpeg"]):
            continue

        filename = href.split("/")[-1]
        if icao not in filename.upper() and "LHBP" not in filename.upper():
            # Keep LHBP generics but otherwise require ICAO presence to avoid noise
            continue

        absolute_url = urljoin(page_url, href)
        absolute_url = _encode_url(absolute_url)
        if absolute_url in seen:
            continue

        name = _derive_chart_name(link)
        charts.append({
            "name": name,
            "url": absolute_url,
            "type": _categorize_chart(name)
        })
        seen.add(absolute_url)

    if not charts:
        raise RuntimeError(f"No charts found for {icao} (AIRAC {airac_date})")

    return charts


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python hungary_scraper.py LHBP")
        sys.exit(1)

    icao_cli = sys.argv[1].upper()
    print(f"Fetching charts for {icao_cli}...")
    try:
        result = get_aerodrome_charts(icao_cli)
        print(f"Found {len(result)} charts:\n")
        for chart in result:
            print(f"[{chart['type']}] {chart['name']}")
            print(f"  {chart['url']}")
    except Exception as exc:
        print(f"Error: {exc}")
        sys.exit(1)

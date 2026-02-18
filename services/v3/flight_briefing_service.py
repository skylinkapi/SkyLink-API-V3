"""
AI-powered flight briefing service.

Gathers METAR/TAF and NOTAM data for origin and destination airports,
then sends it to Cloudflare Workers AI (granite-4.0-h-micro) to produce
a structured pilot briefing (JSON or markdown).
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional

import httpx

from routers.weather import get_metar_async, get_taf_async
from services.airport_service import airport_service
from services.v3.notam_service import get_notams
from services.v3.pirep_service import get_pireps

logger = logging.getLogger(__name__)

# ── aviationweather.gov direct fallback (free, no auth) ──────────────
_AWG_BASE = "https://aviationweather.gov/api/data"


async def _fetch_metar_awg(icao: str) -> Optional[str]:
    """Fetch raw METAR from aviationweather.gov as fallback."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{_AWG_BASE}/metar", params={"ids": icao, "format": "raw"}
            )
            resp.raise_for_status()
            text = resp.text.strip()
            if text and not text.startswith("No data"):
                return text
    except Exception as e:
        logger.debug(f"aviationweather.gov METAR fallback failed for {icao}: {e}")
    return None


async def _fetch_taf_awg(icao: str) -> Optional[str]:
    """Fetch raw TAF from aviationweather.gov as fallback."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{_AWG_BASE}/taf", params={"ids": icao, "format": "raw"}
            )
            resp.raise_for_status()
            text = resp.text.strip()
            if text and not text.startswith("No data"):
                return text
    except Exception as e:
        logger.debug(f"aviationweather.gov TAF fallback failed for {icao}: {e}")
    return None

CF_API_BASE = "https://api.cloudflare.com/client/v4/accounts/4495a8ad4a4203b3c263cb87ebc12b4b/ai/run/"
CF_MODEL = "@cf/ibm-granite/granite-4.0-h-micro"

# Shared aviation knowledge block — used by JSON prompt (which keeps raw data)
_AVIATION_RULES_JSON = """\
INTERNAL RULES — these are instructions for YOU. Do NOT include them in the output.

AVIATION DECODING RULES:
- Airport names: use the EXACT airport names provided in the input data (e.g. "KJFK (John F Kennedy International Airport)"). NEVER guess or invent airport names.
- metar_raw / taf_raw: copy the raw METAR/TAF string verbatim. NEVER set to null if data was provided.
- Altimeter: US "A2977" = 29.77 inHg (NOT hPa/millibars). International "Q1013" = 1013 hPa. In the conditions field, always state the correct unit.
- Visibility: <1SM = LIFR, 1-3SM = IFR, 3-5SM = MVFR, >5SM = VFR.
- Ceiling: the 3-digit code is hundreds of feet. OVC003 = overcast 300ft, OVC070 = overcast 7,000ft, FEW039 = few clouds 3,900ft, BKN130 = broken 13,000ft.
- Wind: report in degrees and knots.
- FICON: 5/5/5 = good braking. 4 = wet but good. 3 = medium. 2 = poor. 1 = unreliable. 0 = NIL. Do NOT call good braking a hazard.
- Thunderstorms (-TSRA, TSRA, +TSRA): CRITICAL hazards — always highlight.
- NOTAMs: deduplicate by NOTAM ID. Max 10 per airport. Omit administrative NOTAMs.
- The "title" field for NOTAMs must be a SHORT plain-English label (e.g. "Taxiway A snow", "Runway 09 wet", "Traffic management program"). NEVER paste raw NOTAM text as the title.
- The "description" field for NOTAMs must be a full plain-English explanation of what the NOTAM means operationally (e.g. "Taxiway A has patchy compacted snow, plowed and swept to 40 feet wide with 30-inch berms on each side. The remainder is compacted snow. Valid until Feb 15 at 21:18 UTC."). NEVER just copy the raw NOTAM code.
- The "summary" field must be 3-5 sentences covering weather conditions, flight categories, key hazards, and notable NOTAMs at BOTH airports. NOT a generic one-liner.\
"""

_AVIATION_RULES_TEXT = """\
INTERNAL RULES — these are instructions for YOU. Do NOT include them in the output. NEVER output a section called "Aviation Interpretation Rules" or similar.

DECODING RULES:
- Airport names: use the EXACT airport names provided in the input data (e.g. "KJFK (John F Kennedy International Airport)"). NEVER guess or invent airport names.
- NEVER copy raw METAR, TAF, NOTAM, or PIREP codes. Translate EVERYTHING into plain English.
- Altimeter: US "A2977" = 29.77 inHg (NOT hPa). International "Q1013" = 1013 hPa. Always state value with correct unit.
- Visibility: state in statute miles. <1SM = LIFR, 1-3SM = IFR, 3-5SM = MVFR, >5SM = VFR. Flag IFR/LIFR as hazards.
- Ceiling: the 3-digit code is hundreds of feet. OVC003 = overcast 300ft, OVC070 = overcast 7,000ft, FEW039 = few clouds 3,900ft, BKN130 = broken 13,000ft.
- Wind: "from [degrees] at [knots]". Flag gusts >25kt.
- Temperature/dewpoint: state in Celsius (e.g. "Temperature 2°C, dewpoint -2°C").
- FICON: 5/5/5 = good braking. 4 = wet but good. 3 = medium. 2 = poor. 1 = unreliable. 0 = NIL. Do NOT call good braking a hazard.
- Thunderstorms (-TSRA, TSRA, +TSRA): CRITICAL hazards.
- TAF: describe timeline in plain language (e.g. "From 03:00 UTC, winds variable at 3 knots, visibility 2 miles in light snow and mist, overcast at 700 feet").
- NOTAMs: describe each one's operational meaning. NOT the raw code. Example: "Taxiway A is wet with good braking, observed Feb 14 21:27 UTC."
- NOTAMs: deduplicate — same restriction mentioned multiple times → describe once.
- PIREPs: plain language (altitude, location, conditions).
- Most significant items FIRST. Max 10 NOTAMs per airport. Omit administrative NOTAMs.\
"""

SYSTEM_PROMPT_MARKDOWN = f"""\
You are an aviation flight briefing generator. Output ONLY the briefing content in markdown. No extra commentary, no rules sections.
CRITICAL: Translate ALL raw METAR/TAF/NOTAM/PIREP codes into plain English. NEVER paste raw codes.
CRITICAL: Do NOT include any "Aviation Interpretation Rules" or "Decoding Rules" section in your output.

## Summary
3-5 sentences: flight categories at both airports, key weather (visibility, ceiling, wind, precipitation), significant NOTAMs (closures, surface conditions), and any hazards.

---

### Critical Operational Restrictions
Only items that could prevent or significantly alter the flight. If none: "No critical restrictions identified."
* **[ICAO]:** [Plain-English description]

---

### Origin: [ICAO]
#### Current Weather
Plain-English paragraph: flight category, visibility (miles), ceiling (feet AGL), wind (direction/speed), temperature, dewpoint, altimeter setting (correct units), significant weather.

#### Forecast
Plain-English paragraph: describe the TAF timeline — what changes when, visibility, ceiling, wind shifts, precipitation expected.

#### NOTAMs
* **[Affected element]** — [Plain-English: what is happening, validity period, operational impact]

#### PIREPs
Plain-English descriptions. If none: "No pilot reports available."

---

### Destination: [ICAO]
Same structure as origin.

{_AVIATION_RULES_TEXT}

- Use ONLY the provided data. Do NOT invent anything.
- Your output must end after the destination section. Do NOT append rules, notes, or disclaimers.\
"""

SYSTEM_PROMPT_PLAIN_TEXT = f"""\
You are an aviation flight briefing generator. Output ONLY plain text. No markdown, no HTML, no special symbols.
CRITICAL: Translate ALL raw METAR/TAF/NOTAM/PIREP codes into plain English. NEVER paste raw codes.
CRITICAL: Do NOT include any "Aviation Interpretation Rules" or "Decoding Rules" section in your output.

SUMMARY
3-5 sentences: flight categories at both airports, key weather (visibility, ceiling, wind, precipitation), significant NOTAMs (closures, surface conditions), and any hazards.

========================================

CRITICAL OPERATIONAL RESTRICTIONS
Only items that could prevent or significantly alter the flight. If none: "No critical restrictions identified."
  [ICAO]: [Plain-English description]

========================================

ORIGIN: [ICAO]

CURRENT WEATHER
Plain-English paragraph: flight category, visibility (miles), ceiling (feet AGL), wind (direction/speed), temperature, dewpoint, altimeter setting (correct units), significant weather.

FORECAST
Plain-English paragraph: describe the TAF timeline. What changes when, visibility, ceiling, wind shifts, precipitation expected.

NOTAMS
  [Affected element]: [Plain-English: what is happening, validity period, operational impact]

PIREPS
Plain-English descriptions. If none: "No pilot reports available."

========================================

DESTINATION: [ICAO]
Same structure as origin.

{_AVIATION_RULES_TEXT}

- Use ONLY the provided data. Do NOT invent anything.
- Output ONLY plain text. No markdown, no HTML.
- Your output must end after the destination section. Do NOT append rules, notes, or disclaimers.\
"""

SYSTEM_PROMPT_HTML = f"""\
You are an aviation flight briefing generator. Output ONLY an HTML fragment (no <html>/<head>/<body> wrappers).
CRITICAL: Translate ALL raw METAR/TAF/NOTAM/PIREP codes into plain English. NEVER paste raw codes.
CRITICAL: Do NOT include any "Aviation Interpretation Rules" or "Decoding Rules" section in your output.

<h2>Summary</h2>
<p>3-5 sentences: flight categories at both airports, key weather, significant NOTAMs, hazards.</p>

<hr>

<h3>Critical Operational Restrictions</h3>
<p>If none: "No critical restrictions identified."</p>
<ul>
  <li><strong>[ICAO]:</strong> [Plain-English description]</li>
</ul>

<hr>

<h3>Origin: [ICAO]</h3>
<h4>Current Weather</h4>
<p>Plain-English: flight category, visibility (miles), ceiling (feet AGL), wind, temp, dewpoint, altimeter (correct units), significant wx.</p>

<h4>Forecast</h4>
<p>Plain-English: TAF timeline, what changes when, visibility, ceiling, wind shifts, precipitation.</p>

<h4>NOTAMs</h4>
<ul>
  <li><strong>[Affected element]</strong> &mdash; [Plain-English: what, when, operational impact]</li>
</ul>

<h4>PIREPs</h4>
<ul>
  <li>Plain-English. If none: "No pilot reports available."</li>
</ul>

<hr>

<h3>Destination: [ICAO]</h3>
Same structure as origin.

{_AVIATION_RULES_TEXT}

- Use ONLY the provided data. Do NOT invent anything.
- Output ONLY an HTML fragment. No markdown.
- Your output must end after the destination section. Do NOT append rules, notes, or disclaimers.\
"""

SYSTEM_PROMPT = f"""\
You are an aviation briefing generator. Output ONLY valid JSON, no markdown, no extra text.

JSON schema:
{{"summary":"3-5 sentence overview","critical_restrictions":[{{"icao":"XXXX","description":"plain-English impact","affected":"element","notam_id":"ID or null"}}],"origin_briefing":{{"weather":{{"metar_raw":"COPY RAW METAR VERBATIM","taf_raw":"COPY RAW TAF VERBATIM","conditions":"plain-English weather summary"}},"notams":[{{"title":"short plain-English label","description":"full plain-English explanation","affected":"element","notam_id":"ID"}}],"pireps":[{{"raw":"raw text","summary":"plain summary"}}]}},"destination_briefing":{{"weather":...,"notams":...,"pireps":...}}}}

{_AVIATION_RULES_JSON}

CRITICAL JSON RULES:
- Output ONLY valid JSON. No markdown fences, no commentary.
- "summary": 3-5 sentences covering flight categories at both airports, key weather (visibility, ceiling, wind, precipitation), significant NOTAMs, and hazards. NOT a generic one-liner.
- metar_raw / taf_raw: copy EXACTLY from input. NEVER drop provided data. Set to null ONLY if not provided.
- "conditions": plain-English paragraph. Start with flight category (VFR/MVFR/IFR/LIFR). State visibility in miles, ceiling in feet AGL, wind direction/speed, temp/dewpoint in °C, altimeter with correct units (inHg for US, hPa for international). Decode ALL values — never write "039ft", write "3,900 feet".
- NOTAM "title": SHORT plain-English label like "Taxiway A snow" or "Runway 09 wet". NEVER paste raw NOTAM code as title.
- NOTAM "description": full plain-English explanation of operational impact and validity period. NEVER paste raw NOTAM code.
- critical_restrictions: only runway closures, airspace restrictions, severe wx, low vis. Empty array if none.
- Set notams/pireps to null ONLY if that data type was NOT provided in the input.\
"""


def _deduplicate_notams(notam_list: List) -> List:
    """Remove duplicate NOTAMs by notam_id, keeping the latest."""
    seen: Dict[str, Any] = {}
    for n in notam_list:
        if isinstance(n, dict):
            nid = n.get("notam_id")
            raw = n.get("raw", "")
        else:
            nid = getattr(n, "notam_id", None)
            raw = getattr(n, "raw", "")
        key = nid or raw
        if key:
            seen[key] = n
    return list(seen.values())


async def _gather_data(
    origin: str,
    destination: str,
    include_weather: bool,
    include_notams: bool,
    include_pireps: bool,
) -> tuple[str, List[str]]:
    """Gather raw aviation data and build a prompt for the AI model.

    Returns (user_prompt, data_included).
    """
    data_included: List[str] = []
    sections: List[str] = []

    # Look up real airport names to prevent hallucination
    origin_airport = await airport_service.find_airport_by_code(origin)
    dest_airport = await airport_service.find_airport_by_code(destination)
    origin_name = origin_airport.get("name", origin) if origin_airport else origin
    dest_name = dest_airport.get("name", destination) if dest_airport else destination

    sections.append(f"FLIGHT: {origin} ({origin_name}) -> {destination} ({dest_name})")
    sections.append("")

    airport_names = {origin: origin_name, destination: dest_name}

    for label, icao in [("ORIGIN", origin), ("DESTINATION", destination)]:
        sections.append(f"=== {label}: {icao} ({airport_names[icao]}) ===")

        if include_weather:
            # Try avwx first, fall back to aviationweather.gov
            metar = await get_metar_async(icao)
            metar_raw = metar.get("raw") if "error" not in metar else None
            if not metar_raw:
                logger.info(f"avwx METAR failed for {icao}, trying aviationweather.gov")
                metar_raw = await _fetch_metar_awg(icao)

            taf = await get_taf_async(icao)
            taf_raw = taf.get("raw") if "error" not in taf else None
            if not taf_raw:
                logger.info(f"avwx TAF failed for {icao}, trying aviationweather.gov")
                taf_raw = await _fetch_taf_awg(icao)

            sections.append(f"METAR: {metar_raw or 'Not available'}")
            sections.append(f"TAF: {taf_raw or 'Not available'}")

            if "metar" not in data_included and metar_raw:
                data_included.append("metar")
            if "taf" not in data_included and taf_raw:
                data_included.append("taf")

        if include_notams:
            try:
                notam_data = await get_notams(icao)
                notam_list = _deduplicate_notams(notam_data.get("notams", []))
                if notam_list:
                    sections.append(f"NOTAMs ({len(notam_list)} unique):")
                    for n in notam_list:
                        raw = n.get("raw", "") if isinstance(n, dict) else getattr(n, "raw", "")
                        sections.append(f"  - {raw}")
                    if "notams" not in data_included:
                        data_included.append("notams")
                else:
                    sections.append("NOTAMs: None active")
            except Exception as e:
                logger.warning(f"Failed to fetch NOTAMs for {icao}: {e}")
                sections.append("NOTAMs: Unavailable")

        if include_pireps:
            airport = await airport_service.find_airport_by_code(icao)
            if airport:
                lat = airport.get("latitude_deg")
                lon = airport.get("longitude_deg")
                if lat is not None and lon is not None:
                    pirep_data = await get_pireps(icao, float(lat), float(lon), radius_nm=100, hours=3)
                    pirep_list = pirep_data.get("reports", [])
                    if pirep_list:
                        sections.append(f"PIREPs ({len(pirep_list)} reports within 100nm, last 3h):")
                        for p in pirep_list:
                            raw = p.get("raw", "") if isinstance(p, dict) else getattr(p, "raw", "")
                            sections.append(f"  - {raw}")
                        if "pireps" not in data_included:
                            data_included.append("pireps")
                    else:
                        sections.append("PIREPs: None reported")

        sections.append("")

    return "\n".join(sections), data_included


async def _call_cf_ai(system: str, user: str) -> str:
    """Call Cloudflare Workers AI granite model."""
    token = os.getenv("CLOUDFLARE_AI_TOKEN")
    if not token:
        raise RuntimeError("CLOUDFLARE_AI_TOKEN not configured")

    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": 4096,
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{CF_API_BASE}{CF_MODEL}",
            headers=headers,
            json=payload,
        )
        resp.raise_for_status()

    data = resp.json()

    # Cloudflare AI uses OpenAI-compatible chat completion format:
    # {"result": {"choices": [{"message": {"content": "..."}}]}}
    result = data.get("result", {})
    choices = result.get("choices")
    if choices and len(choices) > 0:
        return choices[0].get("message", {}).get("content", "")
    # Fallback for older response format
    return result.get("response", "")


def _try_repair_json(text: str) -> str:
    """Attempt to repair truncated JSON by closing open structures."""
    open_braces = 0
    open_brackets = 0
    in_string = False
    escape = False

    for ch in text:
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"' and not escape:
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            open_braces += 1
        elif ch == "}":
            open_braces -= 1
        elif ch == "[":
            open_brackets += 1
        elif ch == "]":
            open_brackets -= 1

    if in_string:
        text += '"'

    text = text.rstrip().rstrip(",")

    text += "]" * max(open_brackets, 0)
    text += "}" * max(open_braces, 0)

    return text


def _parse_ai_response(raw: str, origin: str, destination: str) -> Dict[str, Any]:
    """Parse AI JSON response, stripping code fences if present."""
    text = raw.strip()
    if text.startswith("```"):
        first_newline = text.index("\n")
        text = text[first_newline + 1:]
    if text.endswith("```"):
        text = text[:-3].rstrip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        repaired = _try_repair_json(text)
        parsed = json.loads(repaired)

    # Build origin briefing
    origin_raw = parsed.get("origin_briefing") or {}
    origin_briefing = {"icao": origin}
    origin_briefing["weather"] = origin_raw.get("weather")
    origin_briefing["notams"] = origin_raw.get("notams")
    origin_briefing["pireps"] = origin_raw.get("pireps")

    # Build destination briefing
    dest_raw = parsed.get("destination_briefing") or {}
    dest_briefing = {"icao": destination}
    dest_briefing["weather"] = dest_raw.get("weather")
    dest_briefing["notams"] = dest_raw.get("notams")
    dest_briefing["pireps"] = dest_raw.get("pireps")

    return {
        "summary": parsed.get("summary", ""),
        "critical_restrictions": parsed.get("critical_restrictions", []),
        "origin_briefing": origin_briefing,
        "destination_briefing": dest_briefing,
    }


def _clean_briefing_text(text: str, fmt: str) -> str:
    """Remove newlines from briefing text so the JSON value has no \\n.

    - html: newlines are meaningless — HTML tags handle all structure.
    - markdown: convert to HTML-like structure so it renders without newlines.
    - plain_text: use spaces between sections; the content is still readable.
    """
    import re

    if fmt == "html":
        # Remove all newlines — HTML tags provide structure
        text = re.sub(r"\n\s*", "", text)
        return text.strip()

    if fmt == "markdown":
        # Convert markdown headings to HTML equivalents so rendering
        # doesn't depend on newlines being at the start of a line.
        # ## Heading -> <h2>Heading</h2>   ### Heading -> <h3>Heading</h3>  etc.
        text = re.sub(r"^#{4}\s+(.+)$", r"<h4>\1</h4>", text, flags=re.MULTILINE)
        text = re.sub(r"^#{3}\s+(.+)$", r"<h3>\1</h3>", text, flags=re.MULTILINE)
        text = re.sub(r"^#{2}\s+(.+)$", r"<h2>\1</h2>", text, flags=re.MULTILINE)
        # --- horizontal rules -> <hr>
        text = re.sub(r"^-{3,}$", "<hr>", text, flags=re.MULTILINE)
        # * **bold** -> <li><strong>bold</strong>
        text = re.sub(r"^\*\s+\*\*(.+?)\*\*", r"<li><strong>\1</strong>", text, flags=re.MULTILINE)
        # remaining **bold** -> <strong>
        text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
        # Strip newlines
        text = re.sub(r"\n\s*", " ", text)
        return text.strip()

    # plain_text: collapse multiple newlines, then replace remaining with spaces
    text = re.sub(r"\n{2,}", " | ", text)   # section breaks -> pipe separator
    text = re.sub(r"\n", " ", text)          # remaining newlines -> space
    return text.strip()


async def generate_flight_briefing(
    origin: str,
    destination: str,
    include_weather: bool = True,
    include_notams: bool = True,
    include_pireps: bool = False,
    output_format: str = "json",
) -> Dict:
    """Generate an AI-powered flight briefing.

    Args:
        output_format: 'json' for structured JSON, 'markdown' for formatted text.

    Returns dict ready for FlightBriefingResponse or FlightBriefingMarkdownResponse.
    """
    origin = origin.upper().strip()
    destination = destination.upper().strip()

    if not include_weather and not include_notams and not include_pireps:
        raise ValueError("At least one data source must be included")

    user_prompt, data_included = await _gather_data(
        origin, destination, include_weather, include_notams, include_pireps
    )

    text_prompts = {
        "markdown": SYSTEM_PROMPT_MARKDOWN,
        "plain_text": SYSTEM_PROMPT_PLAIN_TEXT,
        "html": SYSTEM_PROMPT_HTML,
    }

    if output_format in text_prompts:
        raw_response = await _call_cf_ai(text_prompts[output_format], user_prompt)
        if not raw_response:
            raise RuntimeError("AI model returned empty response")

        briefing_text = _clean_briefing_text(raw_response.strip(), output_format)

        return {
            "origin": origin,
            "destination": destination,
            "format": output_format,
            "briefing": briefing_text,
            "data_included": data_included,
        }

    raw_response = await _call_cf_ai(SYSTEM_PROMPT, user_prompt)

    if not raw_response:
        raise RuntimeError("AI model returned empty response")

    briefing = _parse_ai_response(raw_response, origin, destination)

    return {
        "origin": origin,
        "destination": destination,
        "data_included": data_included,
        **briefing,
    }

"""
v3 Flight Briefing router.

AI-powered flight briefings combining METAR/TAF weather, NOTAM, and PIREP data
into a structured, pilot-friendly briefing.

Output formats:
- json: structured JSON (default)
- markdown: JSON with briefing field containing markdown text
- plain_text: JSON with briefing field containing plain text
- html: JSON with briefing field containing HTML fragment
"""

import logging

from fastapi import APIRouter, HTTPException, Query, status
from typing import Union

from models.v3.flight_briefing import FlightBriefingResponse, FlightBriefingTextResponse
from services.airport_service import airport_service
from services.v3.flight_briefing_service import generate_flight_briefing

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/briefing",
    tags=["Flight Briefing"],
)


@router.get(
    "/flight",
    response_model=Union[FlightBriefingResponse, FlightBriefingTextResponse],
    summary="Generate an AI-powered flight briefing",
    description=(
        "Generates a structured flight briefing for a route between two airports.\n\n"
        "The briefing aggregates real-time METAR/TAF weather data, active NOTAMs, "
        "and PIREPs for both origin and destination, then uses AI to produce a concise, "
        "operationally-focused briefing.\n\n"
        "Users can choose which data to include:\n"
        "- **Weather** (METAR + TAF) — current conditions and terminal forecast\n"
        "- **NOTAMs** — active notices to air missions\n"
        "- **PIREPs** — pilot reports of turbulence, icing, and weather (100nm radius, last 3h)\n\n"
        "At least one data source must be selected.\n\n"
        "**Output formats:**\n"
        "- `json` (default) — structured JSON with summary, restrictions, weather, NOTAMs, PIREPs\n"
        "- `markdown` — JSON response with `briefing` field containing markdown text\n"
        "- `plain_text` — JSON response with `briefing` field containing plain text\n"
        "- `html` — JSON response with `briefing` field containing an HTML fragment\n\n"
        "**Disclaimer:** This briefing is AI-generated and for informational purposes only. "
        "Always verify with official sources before flight operations."
    ),
    responses={
        200: {
            "description": "Flight briefing generated successfully",
            "content": {
                "application/json": {
                    "examples": {
                        "json": {
                            "summary": "Structured JSON (format=json)",
                            "value": {
                                "origin": "KJFK",
                                "destination": "EGLL",
                                "summary": "VFR conditions at KJFK with clear skies and light winds. EGLL is MVFR with broken clouds at 3,000 feet and visibility 4 statute miles in light rain. No critical restrictions at either airport. Expect minor delays at EGLL due to wet runway conditions.",
                                "critical_restrictions": [],
                                "origin_briefing": {
                                    "icao": "KJFK",
                                    "weather": {
                                        "metar_raw": "KJFK 151856Z 31008KT 10SM FEW250 08/M06 A3012 RMK AO2 SLP204",
                                        "taf_raw": "TAF KJFK 151730Z 1518/1624 31010KT P6SM FEW250",
                                        "conditions": "VFR. Visibility 10 statute miles. Few clouds at 25,000 feet. Wind from 310 degrees at 8 knots. Temperature 8°C, dewpoint -6°C. Altimeter 30.12 inHg."
                                    },
                                    "notams": [
                                        {
                                            "title": "Taxiway B closed",
                                            "description": "Taxiway B between A and C is closed for maintenance. Use Taxiway D as alternate. Valid until Feb 20 at 18:00 UTC.",
                                            "affected": "TWY B",
                                            "notam_id": "01/234"
                                        }
                                    ],
                                    "pireps": None
                                },
                                "destination_briefing": {
                                    "icao": "EGLL",
                                    "weather": {
                                        "metar_raw": "EGLL 151850Z AUTO 24012KT 4000 -RA BKN030 06/04 Q1023",
                                        "taf_raw": "TAF EGLL 151700Z 1518/1624 24015KT 5000 -RA BKN025",
                                        "conditions": "MVFR. Visibility 4,000 meters (2.5 statute miles) in light rain. Broken clouds at 3,000 feet. Wind from 240 degrees at 12 knots. Temperature 6°C, dewpoint 4°C. Altimeter 1023 hPa."
                                    },
                                    "notams": [],
                                    "pireps": None
                                },
                                "data_included": ["metar", "taf", "notams"],
                                "disclaimer": "This briefing is AI-generated and for informational purposes only. Always verify with official sources before flight operations."
                            },
                        },
                        "markdown": {
                            "summary": "Markdown format (format=markdown)",
                            "value": {
                                "origin": "KJFK",
                                "destination": "EGLL",
                                "format": "markdown",
                                "briefing": "<h2>Summary</h2> VFR conditions at KJFK (John F Kennedy International Airport) with clear skies, visibility 10 statute miles, and light winds from the northwest at 8 knots. EGLL (London Heathrow Airport) is reporting MVFR with broken clouds at 3,000 feet and visibility 2.5 statute miles in light rain. No critical restrictions at either airport. Winds aloft favor a standard North Atlantic track routing. <hr> <h3>Critical Operational Restrictions</h3> No critical restrictions identified. <hr> <h3>Origin: KJFK</h3> <h4>Current Weather</h4> VFR. Visibility 10 statute miles. Few clouds at 25,000 feet. Wind from 310 degrees at 8 knots. Temperature 8°C, dewpoint -6°C. Altimeter 30.12 inHg. No significant weather. <h4>Forecast</h4> Winds remaining from the northwest at 10 knots through the forecast period. Visibility greater than 6 statute miles. Few high clouds. No precipitation expected. <h4>NOTAMs</h4> <li><strong>TWY B:</strong> Taxiway B between A and C closed for maintenance. Use Taxiway D as alternate. Valid until Feb 20 at 18:00 UTC. <hr> <h3>Destination: EGLL</h3> <h4>Current Weather</h4> MVFR. Visibility 4,000 meters (2.5 statute miles) in light rain. Broken clouds at 3,000 feet. Wind from 240 degrees at 12 knots. Temperature 6°C, dewpoint 4°C. Altimeter 1023 hPa. <h4>Forecast</h4> Winds from 240 degrees at 15 knots. Visibility 5,000 meters in light rain. Broken clouds at 2,500 feet. Conditions expected to remain MVFR through the period. <h4>NOTAMs</h4> No active NOTAMs.",
                                "data_included": ["metar", "taf", "notams"],
                                "disclaimer": "This briefing is AI-generated and for informational purposes only. Always verify with official sources before flight operations."
                            },
                        },
                        "plain_text": {
                            "summary": "Plain text format (format=plain_text)",
                            "value": {
                                "origin": "KJFK",
                                "destination": "EGLL",
                                "format": "plain_text",
                                "briefing": "SUMMARY | VFR conditions at KJFK (John F Kennedy International Airport) with clear skies, visibility 10 statute miles, and light winds from the northwest at 8 knots. EGLL (London Heathrow Airport) is reporting MVFR with broken clouds at 3,000 feet and visibility 2.5 statute miles in light rain. No critical restrictions at either airport. | CRITICAL OPERATIONAL RESTRICTIONS | No critical restrictions identified. | ORIGIN: KJFK | CURRENT WEATHER | VFR. Visibility 10 statute miles. Few clouds at 25,000 feet. Wind from 310 degrees at 8 knots. Temperature 8C, dewpoint -6C. Altimeter 30.12 inHg. No significant weather. | FORECAST | Winds remaining from the northwest at 10 knots through the forecast period. Visibility greater than 6 statute miles. Few high clouds. No precipitation expected. | NOTAMS | TWY B: Taxiway B between A and C closed for maintenance. Use Taxiway D as alternate. Valid until Feb 20 at 18:00 UTC. | DESTINATION: EGLL | CURRENT WEATHER | MVFR. Visibility 4,000 meters (2.5 statute miles) in light rain. Broken clouds at 3,000 feet. Wind from 240 degrees at 12 knots. Temperature 6C, dewpoint 4C. Altimeter 1023 hPa. | FORECAST | Winds from 240 degrees at 15 knots. Visibility 5,000 meters in light rain. Broken clouds at 2,500 feet. Conditions expected to remain MVFR through the period. | NOTAMS | No active NOTAMs.",
                                "data_included": ["metar", "taf", "notams"],
                                "disclaimer": "This briefing is AI-generated and for informational purposes only. Always verify with official sources before flight operations."
                            },
                        },
                        "html": {
                            "summary": "HTML fragment format (format=html)",
                            "value": {
                                "origin": "KJFK",
                                "destination": "EGLL",
                                "format": "html",
                                "briefing": "<h2>Summary</h2><p>VFR conditions at KJFK (John F Kennedy International Airport) with clear skies, visibility 10 statute miles, and light winds from the northwest at 8 knots. EGLL (London Heathrow Airport) is reporting MVFR with broken clouds at 3,000 feet and visibility 2.5 statute miles in light rain. No critical restrictions at either airport.</p><hr><h3>Critical Operational Restrictions</h3><p>No critical restrictions identified.</p><hr><h3>Origin: KJFK</h3><h4>Current Weather</h4><p>VFR. Visibility 10 statute miles. Few clouds at 25,000 feet. Wind from 310 degrees at 8 knots. Temperature 8&deg;C, dewpoint -6&deg;C. Altimeter 30.12 inHg. No significant weather.</p><h4>Forecast</h4><p>Winds remaining from the northwest at 10 knots through the forecast period. Visibility greater than 6 statute miles. Few high clouds. No precipitation expected.</p><h4>NOTAMs</h4><ul><li><strong>TWY B</strong> &mdash; Taxiway B between A and C closed for maintenance. Use Taxiway D as alternate. Valid until Feb 20 at 18:00 UTC.</li></ul><hr><h3>Destination: EGLL</h3><h4>Current Weather</h4><p>MVFR. Visibility 4,000 meters (2.5 statute miles) in light rain. Broken clouds at 3,000 feet. Wind from 240 degrees at 12 knots. Temperature 6&deg;C, dewpoint 4&deg;C. Altimeter 1023 hPa.</p><h4>Forecast</h4><p>Winds from 240 degrees at 15 knots. Visibility 5,000 meters in light rain. Broken clouds at 2,500 feet. Conditions expected to remain MVFR through the period.</p><h4>NOTAMs</h4><p>No active NOTAMs.</p>",
                                "data_included": ["metar", "taf", "notams"],
                                "disclaimer": "This briefing is AI-generated and for informational purposes only. Always verify with official sources before flight operations."
                            },
                        },
                    },
                },
            },
        },
        400: {"description": "Invalid parameters"},
        404: {"description": "Airport not found"},
        503: {"description": "Briefing service temporarily unavailable"},
    },
)
async def get_flight_briefing(
    origin: str = Query(
        ..., description="Origin ICAO airport code (e.g. KJFK)", min_length=4, max_length=4
    ),
    destination: str = Query(
        ..., description="Destination ICAO airport code (e.g. EGLL)", min_length=4, max_length=4
    ),
    include_weather: bool = Query(
        True, description="Include METAR/TAF weather data"
    ),
    include_notams: bool = Query(
        True, description="Include NOTAMs"
    ),
    include_pireps: bool = Query(
        False, description="Include PIREPs (pilot reports)"
    ),
    format: str = Query(
        "json", description="Output format: 'json' (structured), 'markdown', 'plain_text', or 'html'",
        pattern="^(json|markdown|plain_text|html)$",
    ),
):
    """Generate an AI-powered flight briefing for a route."""
    origin = origin.upper().strip()
    destination = destination.upper().strip()

    if not include_weather and not include_notams and not include_pireps:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one data source (weather, NOTAMs, or PIREPs) must be included",
        )

    # Validate both airports exist
    origin_airport = await airport_service.find_airport_by_code(origin)
    if not origin_airport:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Origin airport not found for ICAO code: {origin}",
        )

    dest_airport = await airport_service.find_airport_by_code(destination)
    if not dest_airport:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Destination airport not found for ICAO code: {destination}",
        )

    try:
        data = await generate_flight_briefing(
            origin=origin,
            destination=destination,
            include_weather=include_weather,
            include_notams=include_notams,
            include_pireps=include_pireps,
            output_format=format,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error generating flight briefing {origin}->{destination}: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Flight briefing service temporarily unavailable",
        )

    # Text formats: JSON with briefing field
    if format in ("markdown", "plain_text", "html"):
        return FlightBriefingTextResponse(**data)

    # JSON format: structured response
    return FlightBriefingResponse(**data)

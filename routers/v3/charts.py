"""
v3 Aerodrome Charts API router.

Provides endpoints to fetch categorized aerodrome chart PDF links
for airports worldwide, powered by 90+ country-specific scrapers.
"""

from fastapi import APIRouter, Path, Query, HTTPException, status
from typing import Optional

from models.v3.charts import ChartCategory, ChartsResponse, SourceInfo, SourcesResponse
from services.v3.charts_service import charts_service

router = APIRouter(
    prefix="/charts",
    tags=["Aerodrome Charts"],
)


@router.get(
    "/sources",
    response_model=SourcesResponse,
    summary="List supported chart sources",
    description="Returns all supported aerodrome chart sources and the ICAO prefixes they cover.",
)
async def list_sources():
    """List all supported chart data sources."""
    sources_raw = charts_service.get_supported_sources()
    sources = [
        SourceInfo(
            source_id=s['source_id'],
            name=s['name'],
            icao_prefixes=s['icao_prefixes'],
        )
        for s in sources_raw
    ]
    return SourcesResponse(sources=sources, total_count=len(sources))


@router.get(
    "/{icao_code}",
    response_model=ChartsResponse,
    summary="Get aerodrome charts for an airport",
    description=(
        "Fetch categorized aerodrome chart PDF links for a given ICAO airport code. "
        "Charts are organized into categories: GEN (general), GND (ground/taxi), "
        "SID (departure), STAR (arrival), APP (approach). "
        "The chart source is auto-detected from the ICAO prefix."
    ),
    responses={
        200: {
            "description": "Charts found and categorized",
            "content": {
                "application/json": {
                    "example": {
                        "icao_code": "KJFK",
                        "source": "faa",
                        "charts": {
                            "GND": [{"name": "KJFK - Airport Diagram", "url": "https://...", "category": "GND"}],
                            "SID": [{"name": "KENNEDY TWO", "url": "https://...", "category": "SID"}],
                        },
                        "total_count": 42,
                        "fetched_at": "2026-02-11T12:00:00Z"
                    }
                }
            }
        },
        404: {"description": "No charts found for the given airport"},
    }
)
async def get_charts(
    icao_code: str = Path(
        ...,
        min_length=3,
        max_length=4,
        description="ICAO airport code (e.g., KJFK, EGLL, LFPG)",
    ),
    source: Optional[str] = Query(
        None,
        description="Override auto-detected chart source (e.g., faa, france, uk)",
    ),
):
    """Fetch all aerodrome charts for an airport, organized by category."""
    icao = icao_code.upper().strip()

    try:
        result = await charts_service.get_charts(icao, source=source)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Charts for {icao} are not currently available. This airport may not be covered by our chart sources.",
        )

    if result.total_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Charts for {icao} are not currently available. This airport may not be covered by our chart sources.",
        )

    return result


@router.get(
    "/{icao_code}/{category}",
    response_model=ChartsResponse,
    summary="Get charts for a specific category",
    description="Fetch aerodrome charts filtered to a single category (GEN, GND, SID, STAR, APP).",
    responses={
        404: {"description": "No charts found for the given airport/category"},
    }
)
async def get_charts_by_category(
    icao_code: str = Path(
        ...,
        min_length=3,
        max_length=4,
        description="ICAO airport code",
    ),
    category: ChartCategory = Path(
        ...,
        description="Chart category to filter by",
    ),
    source: Optional[str] = Query(
        None,
        description="Override auto-detected chart source",
    ),
):
    """Fetch charts for a specific category only."""
    icao = icao_code.upper().strip()

    try:
        result = await charts_service.get_charts(icao, source=source)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Charts for {icao} are not currently available. This airport may not be covered by our chart sources.",
        )

    # Filter to requested category
    filtered_charts = {category: result.charts.get(category, [])}
    filtered_count = len(filtered_charts.get(category, []))

    if filtered_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No {category.value} charts found for {icao}",
        )

    result.charts = {k: v for k, v in filtered_charts.items() if v}
    result.total_count = filtered_count
    return result

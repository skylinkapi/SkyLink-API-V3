import os
import logging
from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from dotenv import load_dotenv

# v2 routers
from routers.weather import router as weather_router
from routers.schedules import router as schedules_router
from routers.flight_status import router as flight_status_router
from routers.airports import router as airports_router
from routers.airlines import router as airlines_router
from routers.adsb_aircraft import router as adsb_router

# v3 routers (upgraded versions + v3-only features)
from routers.v3.charts import router as charts_router_v3
from routers.v3.distance import router as distance_router_v3
from routers.v3.aircraft import router as aircraft_router_v3
from routers.v3.airports import router as airports_search_router_v3
from routers.v3.flight_status import router as flight_status_router_v3
from routers.v3.schedules import router as schedules_router_v3
from routers.v3.adsb_aircraft import router as adsb_router_v3
from routers.v3.delays import router as delays_router_v3
from routers.v3.pireps import router as pireps_router_v3
from routers.v3.notams import router as notams_router_v3
from routers.v3.winds_aloft import router as winds_aloft_router_v3
from routers.v3.flight_time import router as flight_time_router_v3
from routers.v3.airsigmet import router as airsigmet_router_v3
from routers.v3.flight_briefing import router as flight_briefing_router_v3

from data_ingestion.adsb_client import get_adsb_client
from data_ingestion.v3.swim_notam_client import get_swim_notam_client

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("data_ingestion.schedules").setLevel(logging.WARNING)
logging.getLogger("services.aircraft_db_service").setLevel(logging.WARNING)
logging.getLogger("data_ingestion.weather").setLevel(logging.WARNING)
logging.getLogger("routers.weather").setLevel(logging.WARNING)

adsb_logger = logging.getLogger("data_ingestion.adsb_client")
adsb_logger.setLevel(logging.INFO)

swim_logger = logging.getLogger("data_ingestion.v3.swim_notam_client")
swim_logger.setLevel(logging.INFO)

# Configuration
DEBUG = os.getenv("DEBUG", "false").lower() == "true"


# ── API key middleware (disabled for development) ─────────────────────────────

class APIKeyMiddleware(BaseHTTPMiddleware):
    """API key validation middleware for SkyLink API"""

    ACME_CHALLENGE_PREFIX = "/.well-known/acme-challenge/"
    PUBLIC_PATHS = {"/", "/docs", "/redoc", "/openapi.json", "/health"}

    async def dispatch(self, request: Request, call_next):
        # Public endpoints bypass auth
        if request.url.path in self.PUBLIC_PATHS:
            return await call_next(request)

        # ACME challenges always pass
        if request.url.path.startswith(self.ACME_CHALLENGE_PREFIX):
            return await call_next(request)

        # ── RapidAPI ──────────────────────────────────────────────────────────
        rapidapi_secret = request.headers.get("X-RapidAPI-Proxy-Secret")
        if rapidapi_secret:
            expected = os.getenv("X_RAPIDAPI_PROXY_SECRET")
            if expected and rapidapi_secret == expected:
                return await call_next(request)
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "error": "Unauthorized",
                    "message": "Invalid RapidAPI proxy secret.",
                    "code": "INVALID_RAPIDAPI_SECRET"
                }
            )

        # ── api.market ────────────────────────────────────────────────────────
        api_market_key = request.headers.get("X-API-Key") or request.headers.get("X_API_KEY")
        if api_market_key:
            expected = os.getenv("X_API_KEY")
            if expected and api_market_key == expected:
                return await call_next(request)
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "error": "Unauthorized",
                    "message": "Invalid api.market key.",
                    "code": "INVALID_API_MARKET_KEY"
                }
            )

        # ── No marketplace credentials → block ────────────────────────────────
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "error": "Unauthorized",
                "message": "Access to SkyLink API is available exclusively through api.market and RapidAPI.",
                "code": "MARKETPLACE_ACCESS_REQUIRED"
            }
        )


def _add_cors(application: FastAPI):
    """Add CORS middleware to an app."""
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def _add_auth(application: FastAPI):
    """Add API key auth middleware. Comment out this call to disable auth."""
    application.add_middleware(APIKeyMiddleware)


# ── v2 sub-application ───────────────────────────────────────────────────────

v2_app = FastAPI(
    title="SkyLink API v2",
    description=(
        "## SkyLink API v2\n\n"
        "Stable production endpoints for aviation data:\n\n"
        "- **Airport Information** — Detailed data with runways, frequencies, and navaids\n"
        "- **Airlines** — Airline information lookup\n"
        "- **Weather** — METAR and TAF reports by ICAO code\n"
        "- **Schedules** — Departure and arrival schedules\n"
        "- **Flight Status** — Real-time flight tracking by flight number\n"
        "- **ADS-B Tracking** — Live aircraft positions with filtering\n\n"
        "For advanced features (charts, distance, aircraft lookup, airport search), use [v3](/v3/docs)."
    ),
    version="2.0.0",
    openapi_version="3.0.2",
)
_add_cors(v2_app)
_add_auth(v2_app)

v2_app.include_router(airports_router)
v2_app.include_router(airlines_router)
v2_app.include_router(weather_router)
v2_app.include_router(schedules_router)
v2_app.include_router(flight_status_router)
v2_app.include_router(adsb_router)


# ── v3 sub-application ───────────────────────────────────────────────────────

v3_app = FastAPI(
    title="SkyLink API v3",
    description=(
        "## SkyLink API v3\n\n"
        "Professional aviation data service. Includes all v2 endpoints plus:\n\n"
        "- **Aerodrome Charts** — Chart PDFs for 91 countries by ICAO code\n"
        "- **Distance & Bearing** — Great-circle distance and bearing between airports\n"
        "- **Aircraft Lookup** — Registration / ICAO24 lookup with photos from 615K+ aircraft database\n"
        "- **Airport Search** — Find airports by coordinates, IP geolocation, or free-text query\n"
        "- **Flight Status** — Real-time status with ICAO↔IATA flight number conversion\n"
        "- **Winds Aloft** — FB winds forecasts at standard altitude levels (US airports)\n"
        "- **PIREPs** — Pilot reports of turbulence, icing, and weather conditions\n"
        "- **NOTAMs** — Notices to Air Missions for any airport worldwide\n"
        "- **FAA Delays** — Real-time NAS ground delays, ground stops, and closures\n"
        "- **ML Flight Time** — ML-predicted gate-to-gate flight times by route and aircraft\n"
        "- **AIRMET/SIGMET** — Active aviation weather advisories worldwide\n"
        "- **Flight Briefing** — AI-generated structured flight briefings with weather and NOTAMs\n"
    ),
    version="3.0.0",
    openapi_version="3.0.2",
    openapi_tags=[
        # ── Weather & Forecasts ──
        {
            "name": "Weather",
            "description": "Aviation weather reports — METAR and TAF by ICAO code.",
        },
        {
            "name": "Winds Aloft",
            "description": "FB Winds (Winds and Temperatures Aloft) forecasts at standard altitude levels. "
                           "Wind direction, speed, and temperature from 3,000 to 45,000 ft. US airports only.",
        },
        {
            "name": "PIREPs",
            "description": "Pilot Reports (PIREPs) of in-flight weather conditions including turbulence, "
                           "icing, sky conditions, temperature, and wind. Search by radius and time window.",
        },
        # ── Airport Data ──
        {
            "name": "Airport Search",
            "description": "Search airports by geographic coordinates, IP geolocation, or free-text query. "
                           "Supports filtering by airport type and configurable result limits.",
        },
        {
            "name": "Airports",
            "description": "Detailed airport data including runways, frequencies, navaids, and country/region info.",
        },
        {
            "name": "Airlines",
            "description": "Airline information lookup.",
        },
        # ── Flight Operations ──
        {
            "name": "Flight Status",
            "description": "Real-time flight status by flight number. Supports both IATA (BA123) and ICAO (BAW123) formats.",
        },
        {
            "name": "Schedules",
            "description": "Airport departure and arrival schedules with pagination support.",
        },
        {
            "name": "Distance & Bearing",
            "description": "Calculate great-circle distance, initial bearing, and midpoint between airports or coordinates.",
        },
        # ── Aircraft ──
        {
            "name": "Aircraft Lookup",
            "description": "Look up aircraft details by registration (tail number) or ICAO24 hex address. "
                           "Includes aircraft type, operator, and optional photos.",
        },
        {
            "name": "ADS-B Aircraft Tracking",
            "description": "Real-time aircraft tracking via ADS-B data feed. Filter by location, callsign, "
                           "altitude, speed, registration, or airline. Optional aircraft photos.",
        },
        # ── Charts ──
        {
            "name": "Aerodrome Charts",
            "description": "Retrieve aerodrome chart PDF links by ICAO code. Covers 91 countries with "
                           "categories: GEN (general), GND (ground), SID (departure), STAR (arrival), APP (approach).",
        },
        {
            "name": "AIRMET/SIGMET",
            "description": "Active AIRMET and SIGMET weather advisories. Includes convective SIGMETs, "
                           "turbulence, icing, IFR conditions, and other hazardous weather. "
                           "Filter by airport location or advisory type.",
        },
        # ── Flight Briefing ──
        {
            "name": "Flight Briefing",
            "description": "AI-powered flight briefings combining METAR/TAF weather, NOTAMs, and PIREPs "
                           "into a structured, pilot-friendly briefing document.",
        },
        # ── Alerts & Advisories ──
        {
            "name": "NOTAMs",
            "description": "Notices to Air Missions (NOTAMs) for any airport worldwide. Includes runway closures, "
                           "airspace restrictions, navigation aid outages, and other operational notices.",
        },
        {
            "name": "FAA Delays",
            "description": "Real-time FAA National Airspace System delay information including ground delay programs, "
                           "ground stops, airport closures, and airspace flow programs. US airports only.",
        },
        # ── ML Predictions ──
        {
            "name": "ML Predictions",
            "description": "Machine-learning-powered predictions including flight time estimation.",
        },
    ],
)
_add_cors(v3_app)
_add_auth(v3_app)

# v2 routers shared with v3 (unchanged endpoints)
v3_app.include_router(airports_router)
v3_app.include_router(airlines_router)
v3_app.include_router(weather_router)

# v3 upgraded versions (replace v2 routers with v3 equivalents)
v3_app.include_router(schedules_router_v3)
v3_app.include_router(flight_status_router_v3)
v3_app.include_router(adsb_router_v3)

# v3-only routers
v3_app.include_router(charts_router_v3)
v3_app.include_router(distance_router_v3)
v3_app.include_router(aircraft_router_v3)
v3_app.include_router(airports_search_router_v3)
v3_app.include_router(winds_aloft_router_v3)
v3_app.include_router(pireps_router_v3)
v3_app.include_router(notams_router_v3)
v3_app.include_router(delays_router_v3)
v3_app.include_router(flight_time_router_v3)
v3_app.include_router(airsigmet_router_v3)
v3_app.include_router(flight_briefing_router_v3)


# ── Main application (root + mounting) ────────────────────────────────────────

@asynccontextmanager
async def lifespan(main_app: FastAPI):
    """Application lifespan events"""
    print("SkyLink API starting up...")

    adsb_client = get_adsb_client()
    adsb_client.start()
    print("ADS-B client started, connecting to data.adsbhub.org:5002")

    swim_client = get_swim_notam_client()
    swim_client.start()
    if swim_client.configured:
        print("SWIM FNS NOTAM client started, connecting to Solace")
    else:
        print("SWIM FNS NOTAM client not configured (set SWIM_FNS_* env vars)")

    import asyncio
    await asyncio.sleep(5)
    aircraft_count = len(adsb_client.get_aircraft(clean_old=False))
    if aircraft_count == 0:
        print("ADS-B client connected - waiting for aircraft data (this is normal)")
    else:
        print(f"ADS-B connection active, tracking {aircraft_count} aircraft")

    yield

    print("SkyLink API shutting down...")
    swim_client.stop()
    print("SWIM FNS NOTAM client stopped")
    adsb_client.stop()
    print("ADS-B client stopped")


app = FastAPI(
    title="SkyLink API",
    description=(
        "## SkyLink API\n\n"
        "Professional aviation data service.\n\n"
        "| Version | Status | Documentation |\n"
        "|---------|--------|---------------|\n"
        "| **v2** | Stable | [/v2/docs](/v2/docs) |\n"
        "| **v3** | Stable | [/v3/docs](/v3/docs) |\n"
    ),
    version="3.0.0",
    lifespan=lifespan,
    debug=DEBUG,
    openapi_version="3.0.2",
)
_add_cors(app)

# Mount versioned sub-applications
app.mount("/v2", v2_app)
app.mount("/v3", v3_app)


# ── Root-level endpoints ──────────────────────────────────────────────────────

@app.get("/")
async def root() -> Dict[str, Any]:
    """API information and version overview"""
    return {
        "name": "SkyLink API",
        "version": "3.0.0",
        "status": "operational",
        "description": "Professional aviation data service with real-time aircraft tracking and advanced aviation features",
        "versions": {
            "v2": {
                "status": "stable",
                "base_url": "/v2",
                "documentation": "/v2/docs",
            },
            "v3": {
                "status": "stable",
                "base_url": "/v3",
                "documentation": "/v3/docs",
            }
        },
    }


@app.get("/health")
async def health_check() -> Dict[str, str]:
    """Simple health check endpoint"""
    return {"status": "healthy", "version": "3.0.0"}


# Application entry point
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=DEBUG,
        access_log=DEBUG
    )

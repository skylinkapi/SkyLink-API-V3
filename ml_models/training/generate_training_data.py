"""
Generate synthetic flight time training data using xAI Grok API.

Sends batched prompts asking Grok for realistic flight times across diverse
routes and aircraft types.  Outputs a CSV ready for model training.

Usage:
    XAI_API_KEY=xai-... python ml_models/training/generate_training_data.py
"""

import csv
import itertools
import json
import math
import os
import random
import sys
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()

# ── Configuration ───────────────────────────────────────────────────────────

XAI_API_KEY = os.getenv("XAI_API_KEY")
XAI_BASE_URL = "https://api.x.ai/v1"
MODEL = "grok-4-1-fast-reasoning"
TARGET_SAMPLES = 5000
BATCH_SIZE = 50  # rows per Grok request
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "training_data"
OUTPUT_FILE = OUTPUT_DIR / "flight_times.csv"

# ── Airport pool (~100 major airports with coordinates) ─────────────────────

AIRPORTS: dict[str, tuple[float, float]] = {
    # North America
    "KJFK": (40.6413, -73.7781), "KLAX": (33.9425, -118.4081),
    "KORD": (41.9742, -87.9073), "KATL": (33.6407, -84.4277),
    "KDFW": (32.8998, -97.0403), "KDEN": (39.8561, -104.6737),
    "KSFO": (37.6213, -122.3790), "KSEA": (47.4502, -122.3088),
    "KMIA": (25.7959, -80.2870), "KBOS": (42.3656, -71.0096),
    "KLAS": (36.0840, -115.1537), "KMSP": (44.8848, -93.2223),
    "KPHX": (33.4373, -112.0078), "KDTW": (42.2124, -83.3534),
    "KEWR": (40.6895, -74.1745), "KIAH": (29.9902, -95.3368),
    "KMCO": (28.4312, -81.3081), "KBWI": (39.1774, -76.6684),
    "KDCA": (38.8512, -77.0402), "KSAN": (32.7338, -117.1933),
    "KTPA": (27.9755, -82.5332), "KSTL": (38.7487, -90.3700),
    "KSLC": (40.7884, -111.9778), "KPDX": (45.5898, -122.5951),
    "KHNL": (21.3187, -157.9225), "PANC": (61.1743, -149.9962),
    "CYYZ": (43.6777, -79.6248), "CYVR": (49.1947, -123.1839),
    "MMEX": (19.4363, -99.0721), "MMMX": (19.4363, -99.0721),
    # Europe
    "EGLL": (51.4700, -0.4543), "LFPG": (49.0097, 2.5479),
    "EDDF": (50.0379, 8.5622), "EHAM": (52.3105, 4.7683),
    "LEMD": (40.4983, -3.5676), "LIRF": (41.8003, 12.2389),
    "LSZH": (47.4647, 8.5492), "LOWW": (48.1103, 16.5697),
    "EKCH": (55.6180, 12.6508), "ENGM": (60.1939, 11.1004),
    "ESSA": (59.6519, 17.9186), "EFHK": (60.3172, 24.9633),
    "EIDW": (53.4213, -6.2701), "EPWA": (52.1657, 20.9671),
    "LPPT": (38.7756, -9.1354), "LGAV": (37.9364, 23.9445),
    "LTFM": (41.2753, 28.7519), "UUEE": (55.9726, 37.4146),
    "LKPR": (50.1008, 14.2600), "EBBR": (50.9014, 4.4844),
    # Asia
    "RJTT": (35.5494, 139.7798), "RJAA": (35.7647, 140.3864),
    "RKSI": (37.4602, 126.4407), "VHHH": (22.3080, 113.9185),
    "WSSS": (1.3502, 103.9944), "VTBS": (13.6900, 100.7501),
    "RPLL": (14.5086, 121.0198), "WIII": (6.1256, 106.6558),
    "VABB": (19.0896, 72.8656), "VIDP": (28.5562, 77.1000),
    "OMDB": (25.2528, 55.3644), "OEJN": (21.6702, 39.1566),
    "OTHH": (25.2731, 51.6081), "OERK": (24.9576, 46.6988),
    "ZLXY": (34.4471, 108.7516), "ZSPD": (31.1443, 121.8083),
    "ZGGG": (23.3924, 113.2988), "ZUUU": (30.5785, 103.9471),
    "ZBAA": (40.0799, 116.6031), "RCTP": (25.0777, 121.2325),
    # Oceania
    "YSSY": (33.9461, 151.1772), "YMML": (-37.6733, 144.8433),
    "NZAA": (-37.0082, 174.7917), "YBBN": (-27.3842, 153.1175),
    # South America
    "SBGR": (-23.4356, -46.4731), "SCEL": (-33.3930, -70.7858),
    "SKBO": (4.7016, -74.1469), "SEQM": (-0.1292, -78.3575),
    "SABE": (-34.5592, -58.4156), "SPJC": (-12.0219, -77.1143),
    # Africa
    "FAOR": (-26.1392, 28.2460), "HECA": (30.1219, 31.4056),
    "GMMN": (33.3675, -7.5898), "DNMM": (6.5774, 3.3212),
    "HKJK": (-1.3192, 36.9278), "FALE": (-29.6144, 31.1197),
}

AIRCRAFT_TYPES = [
    "B738", "A320", "B77W", "A388", "E175",
    "CRJ9", "B789", "A321", "B752", "C172",
    "A359", "B763", "E190", "B744", "A332",
]


# ── Helpers ─────────────────────────────────────────────────────────────────

def haversine_nm(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in nautical miles."""
    R_NM = 3440.065
    lat1_r, lon1_r = math.radians(lat1), math.radians(lon1)
    lat2_r, lon2_r = math.radians(lat2), math.radians(lon2)
    dlat = lat2_r - lat1_r
    dlon = lon2_r - lon1_r
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2
    return R_NM * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def generate_route_batches(n_total: int, batch_size: int):
    """Yield batches of (origin, dest, aircraft, distance_nm) tuples."""
    icao_list = list(AIRPORTS.keys())
    batch: list[tuple] = []

    while len(batch) < n_total:
        orig = random.choice(icao_list)
        dest = random.choice(icao_list)
        if orig == dest:
            continue
        acft = random.choice(AIRCRAFT_TYPES)
        dist = round(haversine_nm(*AIRPORTS[orig], *AIRPORTS[dest]), 1)
        if dist < 50:
            continue  # skip very short distances
        batch.append((orig, dest, acft, dist))

    # split into chunks
    for i in range(0, len(batch), batch_size):
        yield batch[i : i + batch_size]


def build_prompt(routes: list[tuple]) -> str:
    """Build a Grok prompt for a batch of routes."""
    route_lines = "\n".join(
        f"- {orig} → {dest}, aircraft={acft}, distance_nm={dist}"
        for orig, dest, acft, dist in routes
    )
    return (
        "You are an aviation expert. For each route below, provide a realistic "
        "estimate of:\n"
        "- flight_time_minutes (block time, gate-to-gate)\n"
        "- cruise_altitude_ft (typical cruise altitude in feet)\n"
        "- cruise_speed_kts (typical cruise speed in knots TAS)\n"
        "- route_deviation_factor (ratio of actual flown distance to great-circle "
        "distance, e.g. 1.0 = direct, 1.3 = 30% longer due to routing)\n\n"
        "IMPORTANT: Use CURRENT real-world routing as of 2024-2025. Account for:\n"
        "- Russian airspace closure to EU/US/allied carriers (routes between "
        "Europe and East Asia now fly polar or southern detours)\n"
        "- Conflict zone avoidance (Ukraine, parts of Middle East)\n"
        "- Standard oceanic tracks (NAT, PACOTS)\n"
        "- Typical ATC routing and jet stream positioning\n"
        "The distance_nm provided is great-circle; your flight_time_minutes should "
        "reflect the ACTUAL expected routing, not the great-circle shortcut.\n\n"
        "Consider the aircraft type's performance (jet vs turboprop vs piston), "
        "actual route distance, typical winds, and climb/descent phases.\n\n"
        f"Routes:\n{route_lines}\n\n"
        "Respond ONLY with a JSON array of objects. Each object must have exactly "
        "these keys: origin, destination, aircraft_type, distance_nm, "
        "flight_time_minutes, cruise_altitude_ft, cruise_speed_kts, "
        "route_deviation_factor.\n"
        "No markdown, no explanation — just the JSON array."
    )


def call_grok(prompt: str, retries: int = 3) -> list[dict]:
    """Call xAI Grok API and parse JSON response."""
    headers = {
        "Authorization": f"Bearer {XAI_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.4,
        "max_tokens": 8000,
    }

    for attempt in range(retries):
        try:
            with httpx.Client(timeout=120.0) as client:
                resp = client.post(
                    f"{XAI_BASE_URL}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                resp.raise_for_status()

            content = resp.json()["choices"][0]["message"]["content"]
            # Strip markdown fences if present
            content = content.strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1]
            if content.endswith("```"):
                content = content.rsplit("```", 1)[0]
            content = content.strip()

            data = json.loads(content)
            if isinstance(data, list):
                return data
            print(f"  [warn] Grok returned non-list, retrying...")
        except (json.JSONDecodeError, KeyError, httpx.HTTPError) as e:
            print(f"  [warn] Attempt {attempt + 1} failed: {e}")
            time.sleep(2 ** attempt)

    return []


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    if not XAI_API_KEY:
        print("ERROR: Set XAI_API_KEY environment variable")
        print("  export XAI_API_KEY=xai-...")
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Generating ~{TARGET_SAMPLES} flight time samples...")
    print(f"Airport pool: {len(AIRPORTS)} airports")
    print(f"Aircraft types: {len(AIRCRAFT_TYPES)}")
    print(f"Output: {OUTPUT_FILE}")
    print()

    all_rows: list[dict] = []
    batches = list(generate_route_batches(TARGET_SAMPLES, BATCH_SIZE))
    total_batches = len(batches)

    for i, batch in enumerate(batches, 1):
        print(f"Batch {i}/{total_batches} ({len(batch)} routes)...", end=" ", flush=True)
        prompt = build_prompt(batch)
        results = call_grok(prompt)

        if results:
            all_rows.extend(results)
            print(f"got {len(results)} rows (total: {len(all_rows)})")
        else:
            print("FAILED — skipping batch")

        # Rate limiting
        if i < total_batches:
            time.sleep(1)

    if not all_rows:
        print("ERROR: No data generated!")
        sys.exit(1)

    # Write CSV
    fieldnames = [
        "origin", "destination", "aircraft_type", "distance_nm",
        "flight_time_minutes", "cruise_altitude_ft", "cruise_speed_kts",
        "route_deviation_factor",
    ]
    with open(OUTPUT_FILE, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in all_rows:
            # Ensure all fields present and numeric values are valid
            try:
                deviation = float(row.get("route_deviation_factor", 1.0))
                if deviation < 0.9 or deviation > 3.0:
                    deviation = 1.0  # clamp unreasonable values
                clean = {
                    "origin": str(row.get("origin", "")).strip().upper(),
                    "destination": str(row.get("destination", "")).strip().upper(),
                    "aircraft_type": str(row.get("aircraft_type", "")).strip().upper(),
                    "distance_nm": float(row.get("distance_nm", 0)),
                    "flight_time_minutes": int(float(row.get("flight_time_minutes", 0))),
                    "cruise_altitude_ft": int(float(row.get("cruise_altitude_ft", 0))),
                    "cruise_speed_kts": int(float(row.get("cruise_speed_kts", 0))),
                    "route_deviation_factor": round(deviation, 2),
                }
                if clean["distance_nm"] > 0 and clean["flight_time_minutes"] > 0:
                    writer.writerow(clean)
            except (ValueError, TypeError):
                continue

    # Count valid rows
    with open(OUTPUT_FILE) as f:
        valid = sum(1 for _ in f) - 1  # minus header

    print(f"\nDone! Wrote {valid} valid samples to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()

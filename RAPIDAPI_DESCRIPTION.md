# ✈️ SkyLink Aviation API — v3

> **The most complete aviation data API on the market.**
> One subscription. Every aviation data point you need.

---

## 🚀 Why SkyLink V3?

Stop stitching together 5 different APIs with inconsistent schemas and unpredictable uptime. SkyLink V3 is a single, production-ready aviation platform built for developers who ship fast and need data they can trust.

---

## 📦 What's Included

| Feature | Description |
|---|---|
| ✈️ **Live Flight Status** | Real-time status + 12-hour schedules for airports worldwide |
| 🗺️ **Aerodrome Charts** | Official approach, SID, STAR & taxi charts — 91 countries |
| 🌤️ **METAR & TAF** | Current conditions and terminal forecasts |
| 💨 **Winds Aloft** | FB wind forecasts at 9 altitudes (3,000–45,000 ft) |
| 🧑‍✈️ **PIREPs** | Pilot-reported turbulence, icing & sky conditions by radius |
| 📋 **NOTAMs** | Live notices via FAA SWIM real-time feed |
| ⚡ **AIRMETs & SIGMETs** | Hazardous weather advisories, globally |
| 🔍 **Airport Search** | Search 74,000+ airports by location, IP, or text |
| 🛩️ **Aircraft Lookup** | Registration & ICAO24 hex → full aircraft profile + photos |
| 📐 **Distance Calculator** | Great-circle distance, bearing & midpoint between any airports |
| 🤖 **ML Flight Time** | AI-predicted block times factoring aircraft type & route |
| 📝 **AI Flight Briefing** | Structured pilot briefings powered by AI — weather, NOTAMs & PIREPs |
| 🚦 **FAA Ground Delays** | Live ground delays, ground stops & airspace flow programs |

---

## ⚡ Built for Production

- 🔴 **Sub-second responses** — Redis caching on all endpoints
- 📐 **Clean, consistent JSON** — no schema surprises across endpoints
- 🔒 **Stable versioning** — v2 endpoints untouched, v3 adds new power
- 📖 **Full OpenAPI docs** — every parameter documented

---

## 🛠️ Quick Example

```http
GET /v3/weather/winds-aloft/KJFK?forecast=12&level=high
GET /v3/charts/EGLL/approach
GET /v3/ml/flight-time?from=KJFK&to=EGLL&aircraft=B738
GET /v3/briefing/flight?origin=KJFK&destination=EGLL
```

---

## 🌍 Coverage

| Data Type | Coverage |
|---|---|
| Aerodrome Charts | 91 countries |
| Airport Database | 74,000+ airports |
| Aircraft Database | 615,000+ registrations |
| Weather (METAR/TAF) | Global |
| Winds Aloft / NOTAMs | USA (FAA) |
| AIRMETs & SIGMETs | Global |

---

> 🌐 **Website:** [skylinkapi.com](https://skylinkapi.com) &nbsp;|&nbsp; 📚 **Full Docs:** [skylinkapi.com/docs](https://skylinkapi.com/docs)

---

*Made with ❤️ by aviation enthusiasts, for developers who build the future of flight.*

# FLOODGUARD AI — Predict. Warn. Reroute.

**Urban flood nowcasting & decision support for Chennai, 0–180 minutes ahead.**
A full-stack prototype that couples a hydrologic flood model with a live
weather provider, machine-learned depth correction, flood-aware routing, and a
real-time decision-support dashboard.

![Stack](https://img.shields.io/badge/stack-FastAPI%20·%20React%20·%20MapLibre%20·%20XGBoost-lightblue)
![Status](https://img.shields.io/badge/status-prototype-blue)

---

## What it does

| Flow | Details |
| --- | --- |
| 🌧 **Nowcast** | Open-Meteo live weather + rolling rainfall nowcast at 15-min steps (0→180 min) |
| 🏞 **Runoff** | Per-cell runoff from rainfall, infiltration & depression storage (500 m grid, 1,517 cells) |
| 🌊 **Surface flow** | D8 steepest-descent routing with relax-to-equalize head transfer |
| 🕳 **Drainage** | Manning-equation pipe capacity, blockage-aware effective capacity, overload → **surcharge** |
| 🔄 **Coupling** | Capacity-limited inlet capture both ways: surface → drain (capture) and drain → surface (surcharge) |
| 🛣 **Street risk** | Per-road depth timeline + arrival time + duration for **34,328 real OSM roads** in Chennai |
| 🤖 **ML** | XGBoost depth-correction trained on synthetic calibration data + confidence score |
| 🚗 **Routing** | Flood-aware Dijkstra (NetworkX over the OSM graph) with mode lambdas; OSRM as live baseline |
| 🔔 **Alerts** | Severity-sorted warnings with arrival time; browser-push-style notification queue |
| 🎮 **Scenario** | Run NORMAL / HEAVY STORM / EXTREME FLOOD / custom scenarios interactively |

The `Time Machine` slider, hotspot list, drainage telemetry, safe-route panel,
weather window and source-status panel all read live from the REST API.

> ⚠️ **Scientific transparency** — terrain and some rainfall/radar inputs are
> **clearly labelled simulation data**. Depth figures are model estimates for
> decision support, *not* certified engineering forecasts. A real DEM GeoTIFF in
> `data/*dem*.tif` is auto-loaded by the terrain loader when present.

---

## Repository layout

```
backend/          FastAPI service
  app/
    api/routers/        REST endpoints (prefix /api)
    simulation/         rainfall → runoff → surface → drainage → coupling → risk
    ml/inference/       XGBoost correction + confidence
    routing/            flood-aware routing + OSRM client
    services/           alerts, notifications, pipeline worker
    external/           Open-Meteo, NASA, Google Flood, Radar providers
    db/                 InMemory (default) + PostGIS adapters
  tests/                unit + end-to-end pipeline tests (51 tests)
frontend/         React + TypeScript + Vite + MapLibre GL JS
  src/map/              MapView with flood/rain/wind/hotspot/route layers
  src/webanim/          WebGL rain/lightning animation + wind particles
  src/components/       dashboard panels (street, hotspots, alerts, …)
data/             Real OSM roads + generated terrain / drainage (JSON, PostGIS-ready)
database/         PostGIS SQL schema
scripts/          data generation (Overpass fetch, synthetic DEM)
docker-compose.yml  backend + frontend + PostGIS + Redis + OSRM
```

---

## Quick start

### 1. Backend (no Docker required for the prototype)

```bash
python -m venv backend/.venv
backend/.venv/Scripts/pip install -r backend/requirements.txt   # Windows
# backend/.venv/bin/pip install -r backend/requirements.txt     # Linux/macOS

# optional: copy secrets template
cp .env.example .env

# run the API (first boot trains the XGBoost model + runs a baseline sim)
cd backend
PYTHONPATH=. .venv/Scripts/python -m uvicorn app.main:app --port 8000
```

Open http://127.0.0.1:8000/docs for the interactive API.

### 2. Frontend

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173  (proxies /api → :8000)
```

### 3. Tests

```bash
cd backend
PYTHONPATH=. .venv/Scripts/python -m pytest        # 51 tests
```

### 4. Docker (PostGIS persistence + Redis + OSRM)

```bash
docker compose up --build
# backend :8000 · frontend :5173 · postgis :5433 · redis :6380 · osrm :5000
```

---

## Configuration

Server-side secrets live only in `.env` (never committed):

| Variable | Meaning |
| --- | --- |
| `OPEN_METEO_API_KEY` | optional — Open-Meteo works without a key |
| `GOOGLE_FLOOD_API_KEY` | optional — Google Flood Hub overlay context |
| `NASA_EARTHDATA_TOKEN` | optional — NASA GPM rainfall |
| `OSRM_URL` | routing engine (demo server default) |
| `DATABASE_URL` | PostGIS DSN; empty → in-memory storage |
| `REDIS_URL` | optional cache fan-out |
| `CITY_*/STUDY_AREA_*` | study area (default Chennai) |
| `LOG_LEVEL` | INFO/DEBUG |

The grid resolution, forecast steps, runoff coefficients and flood-distance
levels (`5 / 15 / 30 / 50 cm`) are all configurable in `backend/app/config.py`.

---

## API overview

```
GET  /api/health
GET  /api/system/status
GET  /api/weather/current | /api/weather/forecast
GET  /api/rainfall/current | /api/rainfall/nowcast | /api/rainfall/forecast
GET  /api/flood/forecast | /api/flood/grid | /api/flood/hotspots | /api/flood/street/{road_id}
GET  /api/roads/geojson?major=true
GET  /api/drainage/status | /api/drainage/nodes | /api/drainage/edges
GET  /api/alerts | /api/alerts/user-location
GET  /api/route/safe
GET  /api/simulation/start | /api/simulation/stop
```

---

## Data pipeline

`scripts/fetch_osm_data.py` pulls **real OpenStreetMap roads** for Chennai via
Overpass (`data/chennai_roads.geojson`: 34,328 ways). `scripts/generate_terrain.py`
builds the synthetic basin-structured DEM and drainage network. The pipeline
worker (`services/pipeline.py`) re-ingests, re-runs the model and refreshes
alerts every 240 s.

## Repo

Maintained at <https://github.com/palspalani07-max/FloodGuardAI>.
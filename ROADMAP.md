# ROADMAP — FloodGuard AI

## Shipped (v0.1 prototype)

- [x] Full coupled model chain: rainfall → runoff → surface flow → drainage →
      overload → surcharge → flood depth → street risk → alerts → diversion
- [x] Real OSM Chennai road network (34,328 ways) + synthetic DEM / drainage
      placed in a basin structure
- [x] XGBoost depth correction + confidence on top of the physical model
- [x] Flood-aware routing (NetworkX + severity penalties + mode lambdas) and
      OSRM baseline provider
- [x] 21+ REST endpoints (nowcast, forecast, grid, hotspots, street, drainage,
      alerts, route/safe, simulation) + PostGIS SQL schema
- [x] React dashboard: MapLibre flood/rain/wind/hotspot/route layers, Time
      Machine slider, street timeline, drainage telemetry, scenario runner,
      Command Center + Public modes
- [x] WebGL animated rain / lightning / water background + wind particle field
- [x] Live Open-Meteo ingestion; NASA / Google / Radar providers degrade
      gracefully without keys
- [x] 51 automated tests (unit + end-to-end pipeline + API layer)
- [x] Docker Compose (backend, frontend, PostGIS, Redis, OSRM) + README

## Next (v0.2)

- [ ] Real SRTM/ALOS DEM ingestion (OpenTopoData key) replacing synthetic terrain
- [ ] Google Flood Hub overlay integration with live API key
- [ ] NASA GPM IMERG rainfall assimilation when token is configured
- [ ] Time-series evaluation backend: compare forecasted vs observed depth curves
      (metric: RMSE / critical-detection-rate per hotspot)
- [ ] Webhook / Firebase push notifications out of the notification queue
- [ ] PostGIS storage adapter E2E tests against the Compose stack

## Later (v1.0)

- [ ] Multi-city configuration (study-area aware)
- [ ] Probabilistic ensemble (Monte-Carlo over rainfall scenarios) + exceedance maps
- [ ] 2D shallow-water solver upgrade for the surface-flow kernel
- [ ] ML retraining pipeline from historical flood reports
- [ ] Mobile PWA with background geolocation alerting
- [ ] Municipal dashboards: asset view (manholes, pumps), work-order auto-check

## Guard rails

- Never present model output as 100% accurate; simulated inputs stay labelled.
- Production requires validated terrain + observed calibration data.
- Forecast confidence must always be shown next to depth figures.
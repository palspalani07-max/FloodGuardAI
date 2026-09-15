"""Flood API routers — all endpoints."""
from fastapi import APIRouter, Query
from typing import Optional
from datetime import datetime, timezone

from ...config import settings
from ...flood_engine import engine
from ...external.provider_registry import registry
from ...services.alert_service import alert_service
from ...services.notification import notification_service
from ...services.pipeline import get_pipeline
from ...routing.flood_aware import provider as flood_aware_provider
from ...routing.osrm import provider as osrm_provider
from ...models import Severity, RoutingMode

router = APIRouter(prefix="/api", tags=["api"])


@router.get("/health")
def health():
    return {"status": "ok", "version": "0.1.0", "time": datetime.now(timezone.utc).isoformat()}


@router.get("/system/status")
def system_status():
    pipeline = get_pipeline(engine)
    return {
        "version": "0.1.0",
        "city": settings.city_name,
        "is_live": pipeline._running if pipeline else False,
        "last_ingestion": pipeline.last_run.isoformat() if pipeline and pipeline.last_run else None,
        "last_forecast": engine.last_run.isoformat() if engine.last_run else None,
        "last_simulation": engine.simulation_status(),
        "providers": registry.status_list(),
        "data_freshness_seconds": pipeline.data_freshness_seconds,
        "db_health": engine.storage.health(),
    }


@router.get("/weather/current")
def weather_current():
    weather = registry.open_meteo().get_current_weather(settings.city_lat, settings.city_lon)
    return weather.model_dump()


@router.get("/weather/forecast")
def weather_forecast():
    forecast = registry.open_meteo().get_forecast(settings.city_lat, settings.city_lon)
    return {
        "hourly_times": forecast.hourly_times,
        "hourly_precipitation": forecast.hourly_precipitation,
        "hourly_temperature": forecast.hourly_temperature,
        "hourly_wind_speed": forecast.hourly_wind_speed,
        "hourly_wind_direction": forecast.hourly_wind_direction,
        "hourly_probability": forecast.hourly_probability,
        "source": forecast.source,
    }


@router.get("/rainfall/current")
def rainfall_current():
    rain = registry.open_meteo().get_rainfall_nowcast(settings.city_lat, settings.city_lon)
    return {"cells": [c.model_dump() for c in rain], "source": "OPEN_METEO"}


@router.get("/rainfall/nowcast")
def rainfall_nowcast():
    return _rainfall_payload()


@router.get("/rainfall/forecast")
def rainfall_forecast():
    return _rainfall_payload()


def _rainfall_payload():
    nowcast = engine.nowcast.generate(settings.city_lat, settings.city_lon)
    return {
        "timesteps": nowcast.timesteps,
        "rainfall_mm_hr": nowcast.rainfall_mm_hr,
        "confidence": nowcast.confidence,
        "source": nowcast.source,
    }


@router.get("/flood/forecast")
def flood_forecast(minutes: Optional[int] = Query(None, ge=0, le=180)):
    if minutes is None:
        return engine.storage.get_flood_predictions()
    preds = engine.storage.get_flood_predictions()
    result = []
    for p in preds:
        key = f"depth_{minutes}min"
        curve = p.get("depth_curve", {})
        depth_at = float(curve.get(str(minutes), p.get("max_depth_cm", 0)))
        result.append({**p, "max_depth_cm": depth_at, "forecast_minutes": minutes})
    return result


@router.get("/flood/hotspots")
def flood_hotspots(minutes: int = Query(180, ge=0, le=180)):
    preds = engine.storage.get_flood_predictions()
    if not preds:
        preds = engine.flood_predictions.get(0, []) or engine.flood_predictions.get(180, [])
    depth_curve = {}
    for p in preds:
        cid = f"T_{p['lat']:.4f}_{p['lon']:.4f}"
        curve = p.get("depth_curve", {})
        depth_curve[p["road_id"]] = float(curve.get(str(minutes), p.get("max_depth_cm", 0)))
    hotspots = []
    for p in sorted(preds, key=lambda p: p.get("max_depth_cm", 0), reverse=True):
        if p.get("max_depth_cm", 0) < 10:
            break
        hotspots.append({
            "rank": len(hotspots) + 1,
            "lat": p["lat"],
            "lon": p["lon"],
            "area_name": p.get("road_name", "Unknown"),
            "depth_cm": round(p.get("max_depth_cm", 0), 1),
            "severity": Severity(p.get("risk", "SAFE")).value,
            "arrival_minutes": p.get("arrival_time_min"),
            "road_id": p.get("road_id"),
            "road_name": p.get("road_name"),
        })
    return hotspots[:15]


@router.get("/flood/street/{road_id}")
def flood_street(road_id: str):
    preds = engine.storage.get_flood_predictions()
    for p in preds:
        if p.get("road_id") == road_id:
            return p
    return {"error": "Road not found"}


@router.get("/roads/geojson")
def roads_geojson(major: bool = Query(False)):
    """Road network as GeoJSON with current flood risk overlays (for the vector map)."""
    preds = engine.storage.get_flood_predictions()
    pred_by_road = {p["road_id"]: p for p in preds}
    features = []
    for road in engine.storage.load_roads():
        if major and road.get("highway") not in ("trunk", "primary", "secondary", "tertiary"):
            continue
        pred = pred_by_road.get(road["road_id"], {})
        risk = pred.get("risk", "SAFE")
        depth = pred.get("max_depth_cm", 0)
        if depth <= 0 and pred and pred.get("depth_curve"):
            depth = float(list(pred["depth_curve"].values())[-1])
        features.append({
            "type": "Feature",
            "properties": {
                "road_id": road["road_id"],
                "name": road.get("name", ""),
                "highway": road.get("highway", ""),
                "risk": risk,
                "depth_cm": round(depth, 1),
                "arrival_min": pred.get("arrival_time_min"),
                "max_depth_cm": pred.get("max_depth_cm", round(depth, 1)),
            },
            "geometry": road.get("geometry"),
        })
    return {"type": "FeatureCollection", "features": features}


@router.get("/flood/grid")
def flood_grid(minutes: int = Query(60, ge=0, le=180)):
    preds = engine.storage.get_flood_predictions()
    curve = [0, 15, 30, 45, 60, 90, 120, 150, 180]
    idx = min(curve, key=lambda c: abs(c - minutes))
    cells = {}
    for p in preds:
        key = (round(p["lat"], 4), round(p["lon"], 4))
        dc = p.get("depth_curve", {})
        d = float(dc.get(str(idx), p.get("max_depth_cm", 0))) if dc else p.get("max_depth_cm", 0)
        if key not in cells or d > cells[key]:
            cells[key] = d
    out = [
        {"lat": k[0], "lon": k[1], "depth_cm": round(v, 2),
         "risk": engine.classifier.classify(v).value}
        for k, v in cells.items()
    ]
    return out


@router.get("/rainfall/grid")
def rainfall_grid():
    nowcast = engine.nowcast.generate(settings.city_lat, settings.city_lon)
    from ...geospatial.earth import meters_to_deg_lat, meters_to_deg_lon
    lat_d = meters_to_deg_lat(settings.grid_resolution_m)
    lon_d = meters_to_deg_lon(settings.grid_resolution_m, settings.city_lat)
    out = []
    lat = settings.study_area_south
    while lat <= settings.study_area_north:
        lon = settings.study_area_west
        while lon <= settings.study_area_east:
            rain = nowcast.rainfall_mm_hr.get(0, 0)
            jitter = 0.7 + ((hash(f"{round(lat,3)}_{round(lon,3)}") % 1000) / 1000.0) * 0.6
            out.append({"lat": round(lat, 4), "lon": round(lon, 4),
                        "rainfall_mm_hr": round(rain * jitter, 1)})
            lon += lon_d
        lat += lat_d
    return out


@router.get("/wind/grid")
def wind_grid():
    weather = registry.open_meteo().get_current_weather(settings.city_lat, settings.city_lon)
    from ...geospatial.earth import meters_to_deg_lat, meters_to_deg_lon
    import math
    lat_d = meters_to_deg_lat(settings.grid_resolution_m * 2)
    lon_d = meters_to_deg_lon(settings.grid_resolution_m * 2, settings.city_lat)
    speed = weather.wind_speed_kmh / 3.6  # m/s
    dir_rad = math.radians(weather.wind_direction_deg)
    out = []
    lat = settings.study_area_south
    while lat <= settings.study_area_north:
        lon = settings.study_area_west
        while lon <= settings.study_area_east:
            j = 0.8 + abs(math.sin(lat * 3) * 0.4)
            u = -speed * math.sin(dir_rad) * j
            v = -speed * math.cos(dir_rad) * j
            out.append({"lat": round(lat, 4), "lon": round(lon, 4), "u_ms": round(u, 2), "v_ms": round(v, 2)})
            lon += lon_d
        lat += lat_d
    return out


@router.get("/drainage/status")
def drainage_status():
    return engine.drainage_status()


@router.get("/drainage/nodes")
def drainage_nodes():
    return engine.drainage_nodes[:500]


@router.get("/drainage/edges")
def drainage_edges():
    return engine.drainage_edges[:500]


@router.get("/route/safe")
def route_safe(
    origin_lat: float, origin_lon: float, dest_lat: float, dest_lon: float,
    mode: str = Query("NORMAL"), forecast_minutes: int = Query(60),
    use_osrm: bool = Query(False),
):
    routing_mode = RoutingMode(mode.upper())
    if use_osrm:
        return osrm_provider.get_route(origin_lat, origin_lon, dest_lat, dest_lon)
    preds = engine.storage.get_flood_predictions()
    pred_map = {p["road_id"]: p for p in preds}
    return flood_aware_provider.get_route(
        origin_lat, origin_lon, dest_lat, dest_lon,
        mode=routing_mode, predictions_by_road=pred_map,
    )


@router.get("/alerts")
def alerts():
    return engine.storage.get_active_alerts()


@router.get("/alerts/user-location")
def alerts_user_location(lat: float, lon: float):
    preds = engine.storage.get_flood_predictions()
    return alert_service.check_user_location(lat, lon, preds)


@router.get("/routing/health")
def routing_health():
    return flood_aware_provider.health()


@router.post("/simulation/start")
def simulation_start(scenario: dict):
    result = engine.start_simulation(scenario)
    return result


@router.post("/simulation/stop")
def simulation_stop():
    return engine.stop_simulation()


@router.post("/simulation/scenario")
def simulation_scenario(scenario: dict):
    result = engine.start_simulation(scenario)
    return result
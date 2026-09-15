-- FloodGuard AI — PostgreSQL / PostGIS schema (optional persistence layer)
-- Used when DATABASE_URL is configured; the prototype falls back to in-memory storage.

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ---------------------------------------------------------------------------
-- Weather & providers
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS weather_observations (
    id            BIGSERIAL PRIMARY KEY,
    observed_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    lat           DOUBLE PRECISION NOT NULL,
    lon           DOUBLE PRECISION NOT NULL,
    temperature_c DOUBLE PRECISION,
    wind_speed_kmh DOUBLE PRECISION,
    wind_direction_deg DOUBLE PRECISION,
    precipitation_mm DOUBLE PRECISION,
    humidity_percent DOUBLE PRECISION,
    conditions    TEXT,
    source        TEXT
);

CREATE TABLE IF NOT EXISTS provider_health (
    name           TEXT PRIMARY KEY,
    data_type      TEXT,
    status         TEXT NOT NULL DEFAULT 'UNKNOWN',
    last_updated   TIMESTAMPTZ,
    raw_payload    JSONB
);

-- ---------------------------------------------------------------------------
-- Study-area reference data
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS roads (
    road_id    TEXT PRIMARY KEY,
    name       TEXT,
    highway    TEXT,
    surface    TEXT,
    lanes      INT,
    length_m   DOUBLE PRECISION,
    width_m    DOUBLE PRECISION,
    geom       GEOMETRY(LineString, 4326) NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_roads_geom ON roads USING GIST (geom);

CREATE TABLE IF NOT EXISTS terrain_cells (
    cell_id        TEXT PRIMARY KEY,
    lat            DOUBLE PRECISION NOT NULL,
    lon            DOUBLE PRECISION NOT NULL,
    elevation_m    DOUBLE PRECISION NOT NULL,
    slope          DOUBLE PRECISION DEFAULT 0,
    imperviousness DOUBLE PRECISION DEFAULT 0.5,
    land_cover     TEXT DEFAULT 'mixed',
    geom           GEOMETRY(POINT, 4326)
);
CREATE INDEX IF NOT EXISTS idx_terrain_geom ON terrain_cells USING GIST (geom);

CREATE TABLE IF NOT EXISTS drainage_nodes (
    node_id            TEXT PRIMARY KEY,
    lat                DOUBLE PRECISION NOT NULL,
    lon                DOUBLE PRECISION NOT NULL,
    elevation_m        DOUBLE PRECISION,
    inlet_capacity     DOUBLE PRECISION DEFAULT 1.0,
    blocked            BOOLEAN DEFAULT FALSE,
    geom               GEOMETRY(POINT, 4326)
);
CREATE INDEX IF NOT EXISTS idx_drain_nodes_geom ON drainage_nodes USING GIST (geom);

CREATE TABLE IF NOT EXISTS drainage_edges (
    edge_id          TEXT PRIMARY KEY,
    from_node        TEXT REFERENCES drainage_nodes(node_id),
    to_node          TEXT REFERENCES drainage_nodes(node_id),
    length_m         DOUBLE PRECISION,
    slope            DOUBLE PRECISION,
    diameter_m       DOUBLE PRECISION,
    roughness        DOUBLE PRECISION DEFAULT 0.013,
    capacity_m3s     DOUBLE PRECISION,
    blockage_percent DOUBLE PRECISION DEFAULT 0,
    geom             GEOMETRY(LineString, 4326)
);
CREATE INDEX IF NOT EXISTS idx_drain_edges_geom ON drainage_edges USING GIST (geom);

-- ---------------------------------------------------------------------------
-- Model outputs
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS flood_predictions (
    id            BIGSERIAL PRIMARY KEY,
    road_id       TEXT REFERENCES roads(road_id),
    forecast_time TIMESTAMPTZ NOT NULL,
    forecast_minutes INT,
    lat           DOUBLE PRECISION,
    lon           DOUBLE PRECISION,
    depth_curve   JSONB NOT NULL,
    max_depth_cm  DOUBLE PRECISION,
    arrival_time_min INT,
    duration_min  INT,
    velocity_ms   DOUBLE PRECISION,
    risk          TEXT,
    confidence    TEXT,
    model_version TEXT
);
CREATE INDEX IF NOT EXISTS idx_predictions_time ON flood_predictions (forecast_time DESC);

CREATE TABLE IF NOT EXISTS hotspots (
    id             BIGSERIAL PRIMARY KEY,
    forecast_time  TIMESTAMPTZ NOT NULL,
    lat            DOUBLE PRECISION NOT NULL,
    lon            DOUBLE PRECISION NOT NULL,
    area_name      TEXT,
    depth_cm       DOUBLE PRECISION,
    severity       TEXT,
    arrival_minutes INT,
    rank           INT
);

CREATE TABLE IF NOT EXISTS alerts (
    alert_id       TEXT PRIMARY KEY,
    lat            DOUBLE PRECISION,
    lon            DOUBLE PRECISION,
    severity       TEXT,
    message        TEXT,
    road_id        TEXT,
    road_name      TEXT,
    max_depth_cm   DOUBLE PRECISION,
    arrival_time_min INT,
    status         TEXT DEFAULT 'active',
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at     TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_alerts_active ON alerts (status) WHERE status = 'active';

-- ---------------------------------------------------------------------------
-- Scenario / simulation audit log
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS simulation_runs (
    id                BIGSERIAL PRIMARY KEY,
    started_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at       TIMESTAMPTZ,
    scenario_name     TEXT,
    rainfall_mm_hr    DOUBLE PRECISION,
    blockage_percent  DOUBLE PRECISION,
    cells_simulated   INT,
    elapsed_s         DOUBLE PRECISION,
    hotspot_count     INT
);

-- ---------------------------------------------------------------------------
-- App notifications
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS notifications (
    id         BIGSERIAL PRIMARY KEY,
    alert_id   TEXT,
    target     TEXT DEFAULT 'browser',
    status     TEXT DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    sent_at    TIMESTAMPTZ
);
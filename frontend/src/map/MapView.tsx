import { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";
import { useStore, CHENNAI } from "../stores/appStore";
import WindParticles from "../webanim/WindParticles";

const STYLE = "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json";

const RISK_COLOR: Record<string, string> = {
  SAFE: "#2e9e53",
  MINOR: "#f0c419",
  HIGH: "#f2961c",
  SEVERE: "#e64a45",
  CRITICAL: "#b01245",
};
const RISK_ORDER = ["SAFE", "MINOR", "HIGH", "SEVERE", "CRITICAL"];

interface Props {
  onRoadClick?: (id: string) => void;
}

export default function MapView({ onRoadClick }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const clickRoadRef = useRef(onRoadClick);
  clickRoadRef.current = onRoadClick;

  const floodGrid = useStore((s) => s.floodGrid);
  const rainGrid = useStore((s) => s.rainGrid);
  const windGrid = useStore((s) => s.windGrid);
  const hotspots = useStore((s) => s.hotspots);
  const alerts = useStore((s) => s.alerts);
  const roads = useStore((s) => s.roads);
  const activeLayers = useStore((s) => s.activeLayers);
  const selectedMinute = useStore((s) => s.selectedMinute);
  const route = useStore((s) => s.route);

  // ---- init map once ----
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: STYLE,
      center: [CHENNAI.lon, CHENNAI.lat],
      zoom: CHENNAI.zoom,
      attributionControl: {
        compact: true,
        customAttribution: "© OpenStreetMap contributors | FloodGuard AI",
      },
    });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "bottom-right");
    mapRef.current = map;
    return () => { map.remove(); mapRef.current = null; };
  }, []);

  // ---- ensure sources/layers exist ----
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const ensure = (id: string, geo: unknown) => {
      const src = map.getSource(id) as maplibregl.GeoJSONSource | undefined;
      if (src) { (src as maplibregl.GeoJSONSource).setData(geo as Parameters<maplibregl.GeoJSONSource["setData"]>[0]); }
      else { map.addSource(id, { type: "geojson", data: geo as never }); }
    };
    if (!map.getSource("roads")) {
      map.addSource("roads", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
      map.addLayer({
        id: "roads-lines", type: "line", source: "roads",
        paint: {
          "line-color": [
            "match", ["get", "risk"], "MINOR", "#f0c419", "HIGH", "#f2961c",
            "SEVERE", "#e64a45", "CRITICAL", "#b01245", "#2e9e53",
          ],
          "line-width": ["coalesce", ["case", ["==", ["get", "highway"], "trunk"], 4.5, ["==", ["get", "highway"], "primary"], 3.5, ["==", ["get", "highway"], "secondary"], 2.6, 1.6], 1.6],
          "line-opacity": 0.92,
        },
      });
      map.on("click", "roads-lines", (e) => {
        const f = e.features?.[0];
        if (f?.properties?.road_id) clickRoadRef.current?.(String(f.properties.road_id));
      });
      map.on("mouseenter", "roads-lines", () => map.getCanvas().style.cursor = "pointer");
      map.on("mouseleave", "roads-lines", () => map.getCanvas().style.cursor = "");
    }
    if (!map.getSource("flood")) {
      map.addSource("flood", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
      map.addLayer({
        id: "flood-cells", type: "circle", source: "flood",
        paint: {
          "circle-radius": 26,
          "circle-color": [
            "match", ["get", "risk"], "MINOR", "#f0c419", "HIGH", "#f2961c",
            "SEVERE", "#e64a45", "CRITICAL", "#b01245", "#2e9e53",
          ],
          "circle-opacity": 0.3,
          "circle-stroke-color": "#ffffff",
          "circle-stroke-opacity": 0.25,
          "circle-stroke-width": 1,
        },
      });
    }
    if (!map.getSource("rain")) {
      map.addSource("rain", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
      map.addLayer({
        id: "rain-cells", type: "circle", source: "rain",
        paint: {
          "circle-radius": 16,
          "circle-color": ["interpolate", ["linear"], ["get", "rain"],
            0, "#3b82f6", 10, "#22d3ee", 30, "#38bdf8", 60, "#1d4ed8"],
          "circle-opacity": 0.55,
        },
      });
    }
    if (!map.getSource("hotspots")) {
      map.addSource("hotspots", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
      map.addLayer({
        id: "hotspots-circles", type: "circle", source: "hotspots",
        paint: {
          "circle-radius": ["-", 26, ["*", ["get", "rank"], 1.3]],
          "circle-color": "#e64a45", "circle-opacity": 0.85,
          "circle-stroke-color": "#b01245", "circle-stroke-width": 2,
        },
      });
      map.addLayer({
        id: "hotspots-labels", type: "symbol", source: "hotspots",
        layout: {
          "text-field": ["get", "rank"],
          "text-size": 12,
          "text-font": ["Open Sans Bold", "Arial Unicode MS Bold"],
          "text-offset": [0, 0.6],
        },
        paint: { "text-color": "#ffffff" },
      });
    }
    if (!map.getSource("alerts")) {
      map.addSource("alerts", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
      map.addLayer({
        id: "alerts-markers", type: "circle", source: "alerts",
        paint: {
          "circle-radius": 7,
          "circle-color": ["match", ["get", "severity"], "SEVERE", "#e64a45", "CRITICAL", "#b01245", "#f2961c"],
          "circle-stroke-width": 2,
          "circle-stroke-color": "#ffffff",
        },
      });
    }
    if (!map.getSource("route")) {
      map.addSource("route", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
      map.addLayer({
        id: "route-line", type: "line", source: "route",
        paint: { "line-color": "#1677d3", "line-width": 4, "line-opacity": 0.9, "line-dasharray": [1, 1] },
      });
      map.addLayer({
        id: "route-line-accent", type: "line", source: "route",
        paint: { "line-color": "#35c3ff", "line-width": 2.2, "line-opacity": 0.9 },
      });
    }
  }, []);

  // ---- push data to sources ----
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;
    const fcs = (arr: unknown[], coords: (x: any) => [number, number], props: (x: any, i: number) => Record<string, unknown>) => ({
      type: "FeatureCollection",
      features: arr.map((a, i) => ({ type: "Feature", properties: props(a, i), geometry: { type: "Point", coordinates: coords(a) } })),
    }) as never;
    try {
      const roadsSrc = map.getSource("roads") as maplibregl.GeoJSONSource;
      if (roads && activeLayers.includes("flood") && roadsSrc) roadsSrc.setData(roads as never);

      const floodSrc = map.getSource("flood") as maplibregl.GeoJSONSource;
      if (floodSrc && activeLayers.includes("flood")) {
        floodSrc.setData(fcs(floodGrid, (c) => [c.lon, c.lat], (c) => ({ risk: c.risk, depth: c.depth_cm })));
      }
      const rainSrc = map.getSource("rain") as maplibregl.GeoJSONSource;
      if (rainSrc && activeLayers.includes("rain")) {
        rainSrc.setData(fcs(rainGrid, (c) => [c.lon, c.lat], (c) => ({ rain: c.rainfall_mm_hr ?? 0 })));
      }
      const hotSrc = map.getSource("hotspots") as maplibregl.GeoJSONSource;
      if (hotSrc && activeLayers.includes("hotspots")) {
        hotSrc.setData(fcs(hotspots, (h) => [h.lon, h.lat], (h, i) => ({ rank: i + 1, name: h.area_name })));
      }
      const alertSrc = map.getSource("alerts") as maplibregl.GeoJSONSource;
      if (alertSrc && activeLayers.includes("alerts")) {
        alertSrc.setData(fcs(alerts, (a) => [a.lon, a.lat], (a) => ({ severity: a.severity, msg: a.message })));
      }
      const routeSrc = map.getSource("route") as maplibregl.GeoJSONSource;
      if (routeSrc && activeLayers.includes("routes") && route?.route?.length) {
        routeSrc.setData({
          type: "FeatureCollection",
          features: [{ type: "Feature", properties: {}, geometry: { type: "LineString", coordinates: route.route.map((r) => [r.lon, r.lat]) } }],
        } as never);
      }
    } catch {
      // style may still be loading; next poll fills data
    }
  }, [roads, floodGrid, rainGrid, hotspots, alerts, route, activeLayers, selectedMinute]);

  // ---- layer visibility ----
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const vis: Record<string, boolean> = {
      "roads-lines": activeLayers.includes("roads"),
      "flood-cells": activeLayers.includes("flood"),
      "rain-cells": activeLayers.includes("rain"),
      "hotspots-circles": activeLayers.includes("hotspots"),
      "hotspots-labels": activeLayers.includes("hotspots"),
      "alerts-markers": activeLayers.includes("alerts"),
      "route-line": activeLayers.includes("routes"),
      "route-line-accent": activeLayers.includes("routes"),
    };
    for (const [id, on] of Object.entries(vis)) {
      if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", on ? "visible" : "none");
    }
  }, [activeLayers]);

  // ---- fit to hotspots on first load ----
  useEffect(() => {
    const map = mapRef.current;
    if (!map || hotspots.length === 0) return;
    const b = new maplibregl.LngLatBounds();
    hotspots.slice(0, 8).forEach((h) => b.extend([h.lon, h.lat]));
    map.fitBounds(b, { padding: 60, maxZoom: 12.6, duration: 900 });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hotspots.length]);

  return (
    <div ref={containerRef} className="map-wrap">
      <WindParticles grid={windGrid} active={activeLayers.includes("wind")} />
    </div>
  );
}
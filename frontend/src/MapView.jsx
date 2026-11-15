import React, { useEffect, useRef, useState, useMemo } from "react";
import * as maplibregl from "maplibre-gl";
import maplibreWorkerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?url";
import "maplibre-gl/dist/maplibre-gl.css";

if (typeof maplibregl.setWorkerUrl === "function") {
  maplibregl.setWorkerUrl(maplibreWorkerUrl);
}
import {
  Plus,
  Minus,
  LocateFixed,
  Layers3,
  Compass,
} from "lucide-react";

function createStyle() {
  return {
    version: 8,
    sources: {
      satellite: {
        type: "raster",
        tiles: [
          "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        ],
        tileSize: 256,
        attribution: "Imagery © Esri, Maxar, Earthstar Geographics",
      },
      terrain: {
        type: "raster-dem",
        tiles: [
          "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png",
        ],
        tileSize: 256,
        encoding: "terrarium",
        maxzoom: 15,
        attribution: "Terrain: AWS Open Data / Mapzen",
      },
    },
    layers: [
      {
        id: "satellite",
        type: "raster",
        source: "satellite",
        paint: {
          "raster-saturation": -0.55,
          "raster-brightness-max": 0.65,
        },
      },
    ],
  };
}

// Helper: Generate exact spherical geodesic circle coordinates around center
function generateCircleCoordinates(center, radiusKm, points = 120) {
  const coords = [];
  const rEarth = 6371.0; // Earth radius in km
  // Add 25m margin to match 20m raster grid pixel edges perfectly
  const adjustedRadiusKm = Number(radiusKm) + 0.025;
  const latRad = (center.lat * Math.PI) / 180;
  const lngRad = (center.lng * Math.PI) / 180;
  const dByR = adjustedRadiusKm / rEarth;

  for (let i = 0; i <= points; i++) {
    const bearing = (i / points) * 2 * Math.PI;
    const ptLatRad = Math.asin(
      Math.sin(latRad) * Math.cos(dByR) +
        Math.cos(latRad) * Math.sin(dByR) * Math.cos(bearing)
    );
    const ptLngRad =
      lngRad +
      Math.atan2(
        Math.sin(bearing) * Math.sin(dByR) * Math.cos(latRad),
        Math.cos(dByR) - Math.sin(latRad) * Math.sin(ptLatRad)
      );
    coords.push([(ptLngRad * 180) / Math.PI, (ptLatRad * 180) / Math.PI]);
  }
  return coords;
}

export default function MapView({
  layer,
  radar,
  opacity,
  showRadar,
  is3D = true,
  focusKey,
  compare,
  onInspect,
  layerType = "water",
  swipeMode = false,
  swipeLeftLayer,
  swipeRightLayer,
  swipeLeftLabel = "Before",
  swipeRightLabel = "After",
  cloudCurtain = false,
  onExitCloudCurtain,
  droneWaypoints = null,
  showDroneWaypoints = false,
  onCloseDroneMission,
  onOpenDroneModal,
  centerCoordinates = null,
  radiusKm = 3,
}) {
  const container = useRef(null);
  const container2 = useRef(null);
  const map = useRef(null);
  const map2 = useRef(null);
  const [ready, setReady] = useState(false);
  const [ready2, setReady2] = useState(false);
  const [failed, setFailed] = useState(false);
  const [swipePos, setSwipePos] = useState(50);
  const isDragging = useRef(false);
  const droneMarkersRef = useRef([]);

  const current = useRef({ layer, onInspect });
  current.current = { layer, onInspect };

  // Calculate study area center
  const computedCenter = useMemo(() => {
    if (centerCoordinates?.lat && centerCoordinates?.lng) {
      return { lat: centerCoordinates.lat, lng: centerCoordinates.lng };
    }
    if (layer?.coordinates && layer.coordinates.length >= 4) {
      const c = layer.coordinates;
      return {
        lat: (c[0][1] + c[2][1]) / 2,
        lng: (c[0][0] + c[2][0]) / 2,
      };
    }
    // Default to Mansar Lake, J&K
    return { lat: 32.69799, lng: 75.14451 };
  }, [centerCoordinates, layer]);

  // Calculate effective research detection radius in km
  const computedRadiusKm = useMemo(() => {
    if (radiusKm && !isNaN(radiusKm) && Number(radiusKm) > 0) {
      return Number(radiusKm);
    }
    if (layer?.coordinates && layer.coordinates.length >= 4) {
      const c = layer.coordinates;
      const dLatKm = (Math.abs(c[0][1] - c[2][1]) * 111.32) / 2;
      return Math.max(0.5, Math.round(dLatKm * 10) / 10);
    }
    return 3;
  }, [radiusKm, layer]);

  // ====================================================
  // MAPLIBRE ENGINE LIFECYCLE
  // ====================================================

  // Initialize Primary Map (Left / Base)
  useEffect(() => {
    let m;
    try {
      m = new maplibregl.Map({
        container: container.current,
        center: [computedCenter.lng, computedCenter.lat],
        zoom: 12,
        pitch: is3D ? 52 : 0,
        bearing: -18,
        maxPitch: 70,
        attributionControl: true,
        style: createStyle(),
      });
      map.current = m;
      m.on("load", () => {
        if (is3D) m.setTerrain({ source: "terrain", exaggeration: 1.5 });
        setReady(true);
      });
      m.on("error", (e) => {
        if (e.error?.message?.includes("WebGL")) setFailed(true);
      });
      m.on("click", (e) =>
        current.current.onInspect({ lng: e.lngLat.lng, lat: e.lngLat.lat })
      );
      m.addControl(
        new maplibregl.ScaleControl({ maxWidth: 100, unit: "metric" }),
        "bottom-left"
      );
    } catch {
      setFailed(true);
    }
    return () => {
      m?.remove();
      map.current = null;
    };
  }, []);

  // Initialize Secondary Map (Right / Overlay for Swipe Mode)
  useEffect(() => {
    if (!swipeMode) {
      if (map2.current) {
        map2.current.remove();
        map2.current = null;
        setReady2(false);
      }
      return;
    }
    if (!container2.current || !map.current) return;

    let m2;
    try {
      m2 = new maplibregl.Map({
        container: container2.current,
        center: map.current.getCenter(),
        zoom: map.current.getZoom(),
        pitch: map.current.getPitch(),
        bearing: map.current.getBearing(),
        interactive: false,
        attributionControl: false,
        style: createStyle(),
      });
      map2.current = m2;
      m2.on("load", () => {
        if (is3D) m2.setTerrain({ source: "terrain", exaggeration: 1.5 });
        setReady2(true);
      });
    } catch (e) {
      console.error("Secondary map initialization failed:", e);
    }

    return () => {
      m2?.remove();
      map2.current = null;
      setReady2(false);
    };
  }, [swipeMode]);

  // Synchronize Movement between Map 1 and Map 2
  useEffect(() => {
    if (!ready || !ready2 || !map.current || !map2.current) return;
    const m1 = map.current;
    const m2 = map2.current;
    const sync = () => {
      m2.jumpTo({
        center: m1.getCenter(),
        zoom: m1.getZoom(),
        pitch: m1.getPitch(),
        bearing: m1.getBearing(),
      });
    };
    m1.on("move", sync);
    return () => m1.off("move", sync);
  }, [ready, ready2]);

  // Update Left Layer, Outlines & Contours on Map 1
  useEffect(() => {
    if (!ready || !map.current) return;
    const m = map.current;
    const activeLayer = swipeMode && swipeLeftLayer ? swipeLeftLayer : layer;
    if (!activeLayer) return;

    const update = (id, item) => {
      if (!item) return;
      if (m.getSource(id))
        m.getSource(id).updateImage({
          url: item.url,
          coordinates: item.coordinates,
        });
      else {
        m.addSource(id, {
          type: "image",
          url: item.url,
          coordinates: item.coordinates,
        });
        m.addLayer({
          id,
          type: "raster",
          source: id,
          paint: { "raster-fade-duration": 0, "raster-resampling": "nearest" },
        });
      }
    };

    update("radar", radar);
    update("science", activeLayer);

    const c = activeLayer.coordinates;
    const geo = {
      type: "Feature",
      properties: {},
      geometry: { type: "Polygon", coordinates: [[...c, c[0]]] },
    };
    if (m.getSource("extent")) m.getSource("extent").setData(geo);
    else {
      m.addSource("extent", { type: "geojson", data: geo });
      m.addLayer({
        id: "extent",
        type: "line",
        source: "extent",
        paint: {
          "line-color": "#8ce9dc",
          "line-width": 1.2,
          "line-dasharray": [3, 3],
          "line-opacity": 0.45,
        },
      });
    }

    // Render Research AOI Coverage Outline (Solid neon border + glowing halo + subtle disc)
    const circleCoords = generateCircleCoordinates(
      computedCenter,
      computedRadiusKm,
      96
    );
    const circleGeo = {
      type: "Feature",
      properties: {},
      geometry: { type: "Polygon", coordinates: [circleCoords] },
    };
    if (m.getSource("research-circle")) {
      m.getSource("research-circle").setData(circleGeo);
    } else {
      m.addSource("research-circle", { type: "geojson", data: circleGeo });
      m.addLayer({
        id: "research-circle-fill",
        type: "fill",
        source: "research-circle",
        paint: {
          "fill-color": "#48e5c2",
          "fill-opacity": 0.045,
        },
      });
      m.addLayer({
        id: "research-circle-glow",
        type: "line",
        source: "research-circle",
        paint: {
          "line-color": "#48e5c2",
          "line-width": 8,
          "line-opacity": 0.35,
          "line-blur": 4,
        },
      });
      m.addLayer({
        id: "research-circle-line",
        type: "line",
        source: "research-circle",
        paint: {
          "line-color": "#48e5c2",
          "line-width": 3.2,
          "line-opacity": 0.95,
        },
      });
    }

    // Render Vector Classification Outlines on MapLibre
    const renderVectorOutlines = (polygonsMap) => {
      if (!m) return;
      if (!polygonsMap || Object.keys(polygonsMap).length === 0) {
        if (m.getSource("feature-outlines")) {
          m.getSource("feature-outlines").setData({ type: "FeatureCollection", features: [] });
        }
        return;
      }

      const getOutlineColor = (cls) => {
        const v = Number(cls);
        if (layerType === "moisture") {
          if (v === 1) return "#48e5c2";
          if (v === 2) return "#ffd166";
          return "#22c55e";
        }
        if (layerType === "vegetation") {
          if (v === 1) return "#22c55e";
          if (v === 2) return "#a3e635";
          return "#ef4444";
        }
        if (layerType === "agriculture") {
          if (v === 1) return "#10b981";
          if (v === 2) return "#f59e0b";
          if (v === 3) return "#a87850";
          return "#38bdf8";
        }
        if (layerType === "subsidence") {
          if (v === 1) return "#64748b";
          if (v === 2) return "#eab308";
          if (v === 3) return "#f97316";
          return "#e11d48";
        }
        // Default / Water
        if (v === 1) return "#48e5c2"; // Persistent water
        if (v === 2) return "#ff7f36"; // Candidate new flood surge
        return "#9f8bff"; // Receded
      };

      const features = [];
      [1, 2, 3, 4].forEach((cls) => {
        const rings = polygonsMap[cls] || polygonsMap[String(cls)] || [];
        const strokeColor = getOutlineColor(cls);
        rings.forEach((ring) => {
          if (ring && ring.length >= 4) {
            features.push({
              type: "Feature",
              properties: { strokeColor, cls },
              geometry: { type: "Polygon", coordinates: [ring] },
            });
          }
        });
      });

      const fc = { type: "FeatureCollection", features };

      if (m.getSource("feature-outlines")) {
        m.getSource("feature-outlines").setData(fc);
      } else {
        m.addSource("feature-outlines", { type: "geojson", data: fc });
        m.addLayer({
          id: "feature-outlines-fill",
          type: "fill",
          source: "feature-outlines",
          paint: {
            "fill-color": ["get", "strokeColor"],
            "fill-opacity": 0.45,
          },
        });
        m.addLayer({
          id: "feature-outlines-glow",
          type: "line",
          source: "feature-outlines",
          paint: {
            "line-color": ["get", "strokeColor"],
            "line-width": 6,
            "line-opacity": 0.45,
            "line-blur": 3,
          },
        });
        m.addLayer({
          id: "feature-outlines-stroke",
          type: "line",
          source: "feature-outlines",
          paint: {
            "line-color": ["get", "strokeColor"],
            "line-width": 2.5,
            "line-opacity": 0.95,
          },
        });
      }
    };

    if (activeLayer?.polygons && Object.keys(activeLayer.polygons).length > 0) {
      renderVectorOutlines(activeLayer.polygons);
    } else {
      renderVectorOutlines(null);
    }
  }, [
    ready,
    layer,
    radar,
    swipeMode,
    swipeLeftLayer,
    layerType,
    computedCenter,
    computedRadiusKm,
  ]);

  // Update Right Layer on Map 2
  useEffect(() => {
    if (!ready2 || !map2.current) return;
    const m2 = map2.current;
    const targetLayer = swipeRightLayer || layer;
    if (!targetLayer) return;

    if (m2.getSource("science2")) {
      m2.getSource("science2").updateImage({
        url: targetLayer.url,
        coordinates: targetLayer.coordinates,
      });
      m2.setPaintProperty("science2", "raster-opacity", 1);
    } else {
      m2.addSource("science2", {
        type: "image",
        url: targetLayer.url,
        coordinates: targetLayer.coordinates,
      });
      m2.addLayer({
        id: "science2",
        type: "raster",
        source: "science2",
        paint: {
          "raster-fade-duration": 0,
          "raster-resampling": "nearest",
          "raster-opacity": 1,
        },
      });
    }

    // Add research circle to Map 2
    const circleCoords = generateCircleCoordinates(
      computedCenter,
      computedRadiusKm,
      96
    );
    const circleGeo = {
      type: "Feature",
      properties: {},
      geometry: { type: "Polygon", coordinates: [circleCoords] },
    };
    if (m2.getSource("research-circle2")) {
      m2.getSource("research-circle2").setData(circleGeo);
    } else {
      m2.addSource("research-circle2", { type: "geojson", data: circleGeo });
      m2.addLayer({
        id: "research-circle2-line",
        type: "line",
        source: "research-circle2",
        paint: {
          "line-color": "#48e5c2",
          "line-width": 3,
          "line-opacity": 0.95,
        },
      });
    }
  }, [ready2, swipeRightLayer, layer, opacity, computedCenter, computedRadiusKm]);

  // Map 1 Layer Opacity Controls
  useEffect(() => {
    if (ready && map.current) {
      if (cloudCurtain) {
        // In cloud penetration curtain mode, Left map shows optical base imagery (radar off)
        map.current.setPaintProperty("science", "raster-opacity", 0);
        map.current.setPaintProperty("radar", "raster-opacity", 0);
      } else {
        map.current.setPaintProperty(
          "science",
          "raster-opacity",
          compare ? 0 : opacity
        );
        map.current.setPaintProperty(
          "radar",
          "raster-opacity",
          showRadar ? 0.8 : 0
        );
      }
    }
  }, [ready, opacity, showRadar, compare, cloudCurtain]);

  // Render Tactical Drone Waypoints and Flightpath (MapLibre mode)
  useEffect(() => {
    if (!ready || !map.current) return;
    const m = map.current;

    // Clean up existing markers
    droneMarkersRef.current.forEach((marker) => {
      try {
        marker.remove();
      } catch (err) {}
    });
    droneMarkersRef.current = [];

    if (!showDroneWaypoints || !droneWaypoints || droneWaypoints.length === 0) {
      if (m.getSource("drone-flightpath")) {
        if (m.getLayer("drone-flightpath-line")) m.removeLayer("drone-flightpath-line");
        if (m.getLayer("drone-flightpath-glow")) m.removeLayer("drone-flightpath-glow");
        m.removeSource("drone-flightpath");
      }
      return;
    }

    // Connect waypoints into a closed tactical flight loop
    const coords = [
      ...droneWaypoints.map((w) => [w.lng, w.lat]),
      [droneWaypoints[0].lng, droneWaypoints[0].lat],
    ];

    const flightGeo = {
      type: "Feature",
      properties: {},
      geometry: {
        type: "LineString",
        coordinates: coords,
      },
    };

    if (m.getSource("drone-flightpath")) {
      m.getSource("drone-flightpath").setData(flightGeo);
    } else {
      m.addSource("drone-flightpath", { type: "geojson", data: flightGeo });
      m.addLayer({
        id: "drone-flightpath-glow",
        type: "line",
        source: "drone-flightpath",
        paint: {
          "line-color": "#ff9f5d",
          "line-width": 6,
          "line-opacity": 0.4,
          "line-blur": 3,
        },
      });
      m.addLayer({
        id: "drone-flightpath-line",
        type: "line",
        source: "drone-flightpath",
        paint: {
          "line-color": "#48e5c2",
          "line-width": 2.5,
          "line-dasharray": [3, 2],
          "line-opacity": 0.95,
        },
      });
    }

    // Spawn tactical HTML markers
    droneWaypoints.forEach((wp) => {
      const el = document.createElement("div");
      el.className = `tactical-drone-marker ${wp.type || "wp"}`;
      const icon =
        wp.type === "landing_zone"
          ? "🚁"
          : wp.type === "marooned_cluster"
            ? "🆘"
            : wp.type === "perimeter"
              ? "⚠️"
              : "📍";

      el.innerHTML = `
        <div class="tactical-marker-pin ${wp.priority === "CRITICAL_SOS" ? "pulse-sos" : ""}">
          <span class="marker-icon">${icon}</span>
          <span class="marker-id">${wp.id}</span>
        </div>
        <div class="tactical-marker-tooltip">
          <strong>${wp.name}</strong>
          <span>${wp.action || "Tactical Action"}</span>
          <small>Priority: ${wp.priority} · Alt: ${wp.altitude_agl_m || 45}m AGL</small>
        </div>
      `;

      try {
        const marker = new maplibregl.Marker({ element: el })
          .setLngLat([wp.lng, wp.lat])
          .addTo(m);
        droneMarkersRef.current.push(marker);
      } catch (e) {
        console.error("Failed adding drone marker:", e);
      }
    });

    return () => {
      droneMarkersRef.current.forEach((marker) => {
        try {
          marker.remove();
        } catch (err) {}
      });
      droneMarkersRef.current = [];
    };
  }, [ready, droneWaypoints, showDroneWaypoints]);

  // Drag handling for swipe divider
  const startDrag = (e) => {
    e.preventDefault();
    isDragging.current = true;
  };

  useEffect(() => {
    const handleMove = (e) => {
      if (!isDragging.current || !container.current) return;
      const clientX = e.touches ? e.touches[0].clientX : e.clientX;
      const rect = container.current.getBoundingClientRect();
      const x = clientX - rect.left;
      const pct = Math.max(5, Math.min(95, (x / rect.width) * 100));
      setSwipePos(pct);
    };
    const handleUp = () => {
      isDragging.current = false;
    };
    window.addEventListener("mousemove", handleMove);
    window.addEventListener("mouseup", handleUp);
    window.addEventListener("touchmove", handleMove);
    window.addEventListener("touchend", handleUp);
    return () => {
      window.removeEventListener("mousemove", handleMove);
      window.removeEventListener("mouseup", handleUp);
      window.removeEventListener("touchmove", handleMove);
      window.removeEventListener("touchend", handleUp);
    };
  }, []);

  const fit = () => {
    if (!map.current || !layer) return;
    const c = layer.coordinates;
    map.current.fitBounds([c[3], c[1]], {
      padding: 55,
      pitch: is3D ? 52 : 0,
      bearing: is3D ? -18 : 0,
      duration: 1100,
    });
  };

  const lastFitLocation = useRef("");
  // Auto-fit bounds ONLY on initial map load or when navigating to a new place
  useEffect(() => {
    if (!ready || !layer?.coordinates) return;
    const locKey = `${computedCenter.lat.toFixed(4)},${computedCenter.lng.toFixed(4)}`;
    if (lastFitLocation.current === locKey) return;
    lastFitLocation.current = locKey;
    fit();
  }, [ready, computedCenter]);

  useEffect(() => {
    if (ready && map.current) {
      map.current.easeTo({
        pitch: is3D ? 52 : 0,
        bearing: is3D ? -18 : 0,
        duration: 900,
      });
      map.current.setTerrain(
        is3D ? { source: "terrain", exaggeration: 1.5 } : null
      );
    }
    if (ready2 && map2.current) {
      map2.current.easeTo({
        pitch: is3D ? 52 : 0,
        bearing: is3D ? -18 : 0,
        duration: 900,
      });
      map2.current.setTerrain(
        is3D ? { source: "terrain", exaggeration: 1.5 } : null
      );
    }
  }, [is3D, ready, ready2]);

  const handleZoomIn = () => {
    map.current?.zoomIn();
  };

  const handleZoomOut = () => {
    map.current?.zoomOut();
  };

  const handleResetNorth = () => {
    map.current?.resetNorth();
  };

  const handleFit = () => {
    fit();
  };

  return (
    <>
      {/* MapLibre 2D / 3D Canvas */}
      <div
        className="map"
        ref={container}
        style={{
          display: "block",
          position: "absolute",
          inset: 0,
          width: "100%",
          height: "100%",
        }}
      />

      {/* Swipe Overlay (MapLibre mode) */}
      {swipeMode && (
        <div
          className="map map-swipe-overlay"
          ref={container2}
          style={{
            position: "absolute",
            inset: 0,
            pointerEvents: "none",
            clipPath: `polygon(${swipePos}% 0, 100% 0, 100% 100%, ${swipePos}% 100%)`,
          }}
        />
      )}

      {/* Cloud Curtain Atmospheric Canopy (Left Side of Divider) */}
      {cloudCurtain && (
        <div
          className="cloud-curtain-canopy"
          style={{
            position: "absolute",
            inset: 0,
            pointerEvents: "none",
            clipPath: `polygon(0 0, ${swipePos}% 0, ${swipePos}% 100%, 0 100%)`,
            zIndex: 8,
          }}
        >
          <div className="cloud-storm-sky" />
          <div className="cloud-storm-rain" />
        </div>
      )}

      {/* Cloud Penetration Banner & HUD */}
      {cloudCurtain && (
        <div className="cloud-penetration-banner">
          <div className="banner-left">
            <span className="cloud-anim-dot" />
            <strong className="banner-title">Cloud Penetration Curtain Active</strong>
            <span className="banner-divider">|</span>
            <span className="banner-subtitle">
              Optical spectrum blinded by storm clouds ⟷ Drag divider to reveal NISAR 24cm L-Band Radar penetration
            </span>
          </div>
          {onExitCloudCurtain && (
            <button
              type="button"
              className="btn-exit-curtain"
              onClick={onExitCloudCurtain}
              title="Return to standard map view"
            >
              ✕ Exit Curtain
            </button>
          )}
        </div>
      )}

      {/* Drone Mission Flight HUD indicator on Map */}
      {showDroneWaypoints && droneWaypoints && droneWaypoints.length > 0 && (
        <div className="drone-mission-map-hud">
          <div className="drone-hud-header">
            <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
              <span className="drone-live-dot" />
              <strong>🚁 FIRST-RESPONDER FLIGHT CORRIDOR</strong>
            </div>
            {onCloseDroneMission && (
              <button
                type="button"
                className="btn-drone-hud-close"
                onClick={onCloseDroneMission}
                title="Exit Rescue Dispatch & clear flight corridor from map"
                aria-label="Close rescue flight corridor"
              >
                ✕
              </button>
            )}
          </div>
          <div className="drone-hud-chips">
            <span>{droneWaypoints.length} Tactical Waypoints</span>
            <span>Closed Loop</span>
            <span className="badge-sos">1 SOS Cluster</span>
            {onOpenDroneModal && (
              <button
                type="button"
                className="btn-drone-hud-view-pkg"
                onClick={onOpenDroneModal}
                title="View full waypoint roster & export package"
              >
                View Roster ↗
              </button>
            )}
          </div>
        </div>
      )}

      {swipeMode && (
        <>
          <div
            className="swipe-divider"
            style={{ left: `${swipePos}%` }}
            onMouseDown={startDrag}
            onTouchStart={startDrag}
          >
            <div className="swipe-line" />
            <div className="swipe-handle">
              <span className="arrow-left">◀</span>
              <span className="divider-grip" />
              <span className="arrow-right">▶</span>
            </div>
          </div>
          <div className="swipe-labels">
            <div className="swipe-badge left">
              <span className="tag">◀ {cloudCurtain ? "OPTICAL (CLOUD-BLIND)" : "BEFORE"}</span>
              <strong>{swipeLeftLabel}</strong>
            </div>
            <div className="swipe-badge right">
              <strong>{swipeRightLabel}</strong>
              <span className="tag">{cloudCurtain ? "NISAR RADAR (PENETRATING) ▶" : "AFTER ▶"}</span>
            </div>
          </div>
        </>
      )}

      {failed && (
        <div className="map-error">
          3D rendering is unavailable in this browser. Your scientific layers
          and report remain available below.
          <img src={layer.url} alt="Selected scientific map layer" />
        </div>
      )}

      {/* Map Tools HUD */}
      <div className="map-tools">
        <button
          aria-label="Zoom in"
          title="Zoom in"
          onClick={handleZoomIn}
        >
          <Plus size={18} />
        </button>
        <button
          aria-label="Zoom out"
          title="Zoom out"
          onClick={handleZoomOut}
        >
          <Minus size={18} />
        </button>
        <button
          aria-label="Reset North"
          title="Reset North / Orientation"
          onClick={handleResetNorth}
        >
          <Compass size={18} />
        </button>
        <span />
        <button
          aria-label="Fit study area"
          title="Fit study area (Focus)"
          onClick={handleFit}
        >
          <LocateFixed size={18} />
        </button>
      </div>

      {/* Research AOI Coverage Perimeter Indicator */}
      <div className="research-aoi-indicator">
        <span className="aoi-beacon" />
        <span>Research Study Perimeter · {computedRadiusKm} km Radius</span>
      </div>

      {/* Map Hint Footer */}
      <div className="map-hint">
        <Layers3 size={13} style={{ color: "#48e5c2" }} />
        <strong style={{ color: "#48e5c2" }}>
          {is3D ? "MapLibre 3D Terrain Relief (1.5×)" : "MapLibre 2D Topo & Satellite"}
        </strong>
        <span>
          {swipeMode
            ? "Drag slider to compare Before vs After · Drag map to pan"
            : is3D
              ? "Drag to pan · Ctrl+Drag or Right-click to tilt & rotate"
              : "Drag to pan · Double-click to zoom"}
        </span>
      </div>
    </>
  );
}

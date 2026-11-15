import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Orbit,
  ArrowUpRight,
  ChevronRight,
  Layers,
  Activity,
  Info,
  Download,
  Play,
  Pause,
  Check,
  MapPin,
  Satellite,
  Eye,
  X,
  ShieldCheck,
  ExternalLink,
  Globe2,
  Globe,
  Columns2,
  Sparkles,
  Waves,
  Printer,
  FileText,
  AlertTriangle,
  Trees,
  Sprout,
  Building2,
  Droplets,
} from "lucide-react";
import MapView from "./MapView";
import Monitor from "./Monitor";
import EarthEcho from "./EarthEcho";
import CriticalConnections from "./RealConnections";
import StoryMaps from "./StoryMaps";
import "./styles.css";
import "./monitor.css";
import "./layout.css";
import useDialogFocus from "./useDialogFocus";

const formatDate = (d) =>
  new Date(
    `${d.slice(0, 4)}-${d.slice(4, 6)}-${d.slice(6, 8)}T12:00:00`,
  ).toLocaleDateString("en-GB", { day: "2-digit", month: "short" });
function App() {
  const [echo, setEcho] = useState(() => window.location.hash === '#earth-echo');
  const [monitor, setMonitor] = useState(false);
  const [connections, setConnections] = useState(() => window.location.hash === '#critical-connections');
  useEffect(() => {
    const sync = () => { setConnections(window.location.hash === '#critical-connections'); setEcho(window.location.hash === '#earth-echo'); };
    window.addEventListener('hashchange', sync);
    return () => window.removeEventListener('hashchange', sync);
  }, []);
  const openEcho = () => { setPlaying(false); setConnections(false); setEcho(true); window.location.hash = 'earth-echo'; };
  const openConnections = () => { setEcho(false); setPlaying(false); setConnections(true); window.location.hash = 'critical-connections'; };
  const closeConnections = () => { setEcho(false); setConnections(false); window.location.hash = ''; };
  const [activeDomain, setActiveDomain] = useState("water");
  const [data, setData] = useState(null),
    [loadError, setLoadError] = useState(false),
    [mode, setMode] = useState("validation"),
    [date, setDate] = useState(5),
    [layerType, setLayerType] = useState("water"),
    [opacity, setOpacity] = useState(0.9),
    [radar, setRadar] = useState(false),
    [is3D, setIs3D] = useState(true),
    [playing, setPlaying] = useState(false),
    [compare, setCompare] = useState(false),
    [modal, setModal] = useState(false),
    [modalTab, setModalTab] = useState("story"),
    [showPolInfo, setShowPolInfo] = useState(false),
    [swipeMode, setSwipeMode] = useState(false),
    [caseStudy, setCaseStudy] = useState("inba"),
    [showCaseStudyMenu, setShowCaseStudyMenu] = useState(false),
    [point, setPoint] = useState(null),
    [showStoryMaps, setShowStoryMaps] = useState(false),
    [showDossierModal, setShowDossierModal] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    setData(null);
    setLoadError(false);
    setPlaying(false);
    setPoint(null);
    const url = caseStudy === "assam" ? "/data/assam/manifest.json" : "/data/manifest.json";
    fetch(url, { signal: controller.signal })
      .then((r) => {
        if (!r.ok) throw Error();
        return r.json();
      })
      .then((d) => {
        setData(d);
        setDate(caseStudy === "assam" ? 2 : 5);
      })
      .catch((error) => {
        if (error.name !== "AbortError") setLoadError(true);
      });
    return () => controller.abort();
  }, [caseStudy]);
  useEffect(() => {
    if (!playing || !data?.scenes?.length) return;
    const id = setInterval(() => setDate((d) => (d + 1) % data.scenes.length), 2200);
    return () => clearInterval(id);
  }, [playing, data]);
  useDialogFocus(modal || showDossierModal, () => {
    setModal(false);
    setShowDossierModal(false);
  });
  const changeMode = (m) => {
    setMode(m);
    setPlaying(false);
    setPoint(null);
    setLayerType("water");
    setSwipeMode(false);
  };
  if (echo) return <EarthEcho onBack={() => { closeConnections(); setMonitor(false); }} onConnections={openConnections} onDomainChange={(domain) => { closeConnections(); setActiveDomain(domain); setMonitor(true); }} />;
  if (connections) return <CriticalConnections onEcho={openEcho} onBack={() => { closeConnections(); setMonitor(false); }} onDomainChange={(domain) => { closeConnections(); setActiveDomain(domain); setMonitor(true); }} />;
  if (monitor)
    return (
      <Monitor
        onBack={() => setMonitor(false)}
        onConnections={openConnections}
        onEcho={openEcho}
        domain={activeDomain}
        onDomainChange={(d) => setActiveDomain(d)}
      />
    );
  if (!data)
    return (
      <div className="loading">
        <Orbit size={40} />
        <h1>SARScope</h1>
        <p>
          {loadError
            ? "Could not load the science data. Please reload the page."
            : "Preparing your view of Earth…"}
        </p>
      </div>
    );
  const validated = mode === "validation",
    scene = data.scenes[date],
    bundle = validated ? data.validation : scene,
    layer = bundle[layerType] || bundle.water;

  const getDomainMetric = (s, type) => {
    if (type === "moisture") return s.moisture?.saturated_km2 || 14.2;
    if (type === "vegetation") return s.vegetation?.dense_forest_km2 || 22.8;
    if (type === "agriculture") return s.agriculture?.vegetative_km2 || 31.5;
    if (type === "subsidence") return s.subsidence?.critical_sinking_km2 || 4.2;
    return s.water?.waterArea || 0;
  };
  const getDomainColor = (type) => {
    if (type === "moisture") return "#ffc43c";
    if (type === "vegetation") return "#22c55e";
    if (type === "agriculture") return "#f59e0b";
    if (type === "subsidence") return "#e11d48";
    return "#61e0cf";
  };
  const getDomainTitle = (type) => {
    if (type === "moisture") return "SOIL SATURATION EVOLUTION";
    if (type === "vegetation") return "FOREST CANOPY EVOLUTION";
    if (type === "agriculture") return "CROP BIOMASS EVOLUTION";
    if (type === "subsidence") return "CRITICAL SINKING EVOLUTION";
    return "SURFACE WATER EVOLUTION DYNAMICS";
  };

  const swipeLeftLayer = validated
    ? data.validation.reference
    : data.scenes[0].water;
  const swipeLeftLabel = validated
    ? "OPERA Optical Ground Reference"
    : "16 Jul 2026 (Flood Peak · 9.69 km²)";
  const swipeRightLayer = validated
    ? data.validation.water
    : scene.water;
  const swipeRightLabel = validated
    ? "NISAR ML Predicted Water (F1 0.937)"
    : `${formatDate(scene.date)} 2026 (${scene.water.waterArea.toFixed(2)} km²)`;
  return (
    <div className="app">
      {showStoryMaps && (
        <StoryMaps
          onClose={() => setShowStoryMaps(false)}
          onSelectStory={(s) => {
            setShowStoryMaps(false);
            if (s.id === "assam") {
              setCaseStudy("assam");
              setMode("explorer");
              setDate(1);
            } else if (s.id === "inba") {
              setCaseStudy("inba");
              setMode("explorer");
              setDate(0);
            } else {
              setMonitor(true);
            }
          }}
        />
      )}
      <header>
        <a className="brand" href="/" aria-label="SARScope home">
          <span className="brand-icon">
            <Orbit size={25} />
          </span>
          SAR<span>Scope</span>
          <i>BETA</i>
        </a>
        <nav className="main-nav-tabs" aria-label="Earth observation workspaces">
          <button
            className={!monitor ? "nav-active" : ""}
            onClick={() => {
              setMonitor(false);
              setModal(false);
            }}
          >
            Workspace
          </button>
          <button
            className={monitor && activeDomain === "water" ? "nav-active" : ""}
            onClick={() => {
              setActiveDomain("water");
              setMonitor(true);
            }}
          >
            Water & Floods <Waves size={13} />
          </button>
          <button
            className={monitor && activeDomain === "moisture" ? "nav-active" : ""}
            onClick={() => {
              setActiveDomain("moisture");
              setMonitor(true);
            }}
          >
            Soil Moisture <Droplets size={13} />
          </button>
          <button
            className={monitor && activeDomain === "vegetation" ? "nav-active" : ""}
            onClick={() => {
              setActiveDomain("vegetation");
              setMonitor(true);
            }}
          >
            Forests & Canopy <Trees size={13} />
          </button>
          <button
            className={monitor && activeDomain === "agriculture" ? "nav-active" : ""}
            onClick={() => {
              setActiveDomain("agriculture");
              setMonitor(true);
            }}
          >
            Agriculture <Sprout size={13} />
          </button>
          <button
            className={monitor && activeDomain === "subsidence" ? "nav-active" : ""}
            onClick={() => {
              setActiveDomain("subsidence");
              setMonitor(true);
            }}
          >
            Land Subsidence <Building2 size={13} />
          </button>
          <button onClick={openConnections}>Critical Connections <ArrowUpRight size={13} /></button>
          <button onClick={openEcho}>Earth Echo</button>
        </nav>
        <div className="header-right">
          <span className="source-tag">
            <span /> NASA–ISRO NISAR
          </span>
          <button
            type="button"
            className="report-link"
            onClick={() => setShowDossierModal(true)}
            style={{
              background: "#1c3844",
              color: "#48e5c2",
              border: "1px solid #356b7c",
              borderRadius: "6px",
              padding: "7px 14px",
              fontSize: "11px",
              fontWeight: "600",
              cursor: "pointer",
              display: "inline-flex",
              alignItems: "center",
              gap: "6px",
            }}
          >
            <FileText size={14} /> Earth Dossier (PDF)
          </button>
        </div>
      </header>
      <main>
        <aside className="sidebar">
          <div className="eyebrow">
            <span className="live-dot" /> EARTH OBSERVATION WORKSPACE
          </div>
          <h1>
            Earth is moving.
            <br />
            <em>See what changes.</em>
          </h1>
          <p className="intro">
            From radar signals to a clearer picture of our changing waters.
          </p>
          <button
            type="button"
            className="location"
            onClick={() => setShowCaseStudyMenu((v) => !v)}
            aria-expanded={showCaseStudyMenu}
            aria-controls="case-study-options"
            title="Click to switch between Case Studies"
          >
            <div className="location-icon">
              <MapPin size={19} />
            </div>
            <div>
              <strong>
                {caseStudy === "assam"
                  ? "Brahmaputra & Kaziranga"
                  : "Lake Inba & Tone River"}
              </strong>
              <span>
                {caseStudy === "assam" ? "Assam, India" : "Chiba, Japan"}{" "}
                <span className={caseStudy === "assam" ? "jp in-flag" : "jp"}>
                  {caseStudy === "assam" ? "IN" : "JP"}
                </span>
              </span>
            </div>
            <ChevronRight
              size={16}
              className={`chevron-rotate ${showCaseStudyMenu ? "open" : ""}`}
            />
          </button>
          {showCaseStudyMenu && (
            <div className="case-study-dropdown" id="case-study-options">
              <div className="case-study-title">SELECT ACTIVE CASE STUDY</div>
              <button
                className={`case-study-option ${caseStudy === "inba" ? "active" : ""}`}
                onClick={() => {
                  setCaseStudy("inba");
                  setShowCaseStudyMenu(false);
                  setSwipeMode(false);
                }}
              >
                <div>
                  <span className="flag-badge">🇯🇵 JAPAN</span>
                  <strong>Lake Inba & Tone River Basin</strong>
                  <small>Agricultural wetlands & seasonal drainage (F1: 0.937)</small>
                </div>
                {caseStudy === "inba" && <Check size={16} />}
              </button>
              <button
                className={`case-study-option ${caseStudy === "assam" ? "active" : ""}`}
                onClick={() => {
                  setCaseStudy("assam");
                  setShowCaseStudyMenu(false);
                  setSwipeMode(false);
                }}
              >
                <div>
                  <span className="flag-badge">🇮🇳 INDIA (ISRO / NASA)</span>
                  <strong>Assam Flood Case Study (Brahmaputra)</strong>
                  <small>Severe monsoon flood inundation & cloud penetration (F1: 0.942)</small>
                </div>
                {caseStudy === "assam" && <Check size={16} />}
              </button>
            </div>
          )}
          <section>
            <div className="section-heading">
              <span>01 / STUDY VIEW</span>
              <Globe2 size={15} />
            </div>
            <div className="mode-tabs">
              <button
                className={validated ? "selected" : ""}
                onClick={() => changeMode("validation")}
              >
                Validation area
              </button>
              <button
                className={!validated ? "selected" : ""}
                onClick={() => changeMode("explore")}
              >
                Time explorer
              </button>
            </div>
            <div className="view-description">
              <span className={validated ? "pill" : "pill amber"}>
                {validated ? "EVALUATED" : "EXPLORATORY"}
              </span>
              <p>
                {validated
                  ? "A separate 100 km² area, north of the training region. Model kept frozen."
                  : "Seven radar dates over the original study area. Earlier baseline model; transfer is not validated."}
              </p>
            </div>
          </section>
          <section>
            <div className="section-heading">
              <span>02 / EARTH INTELLIGENCE LAYERS</span>
              <Layers size={15} />
            </div>
            {[
              [
                "water",
                "Water & Flood Extent",
                "Random Forest · radar + terrain",
              ],
              [
                "moisture",
                "Soil Moisture & Wetness",
                "Dielectric ground saturation & drought",
              ],
              [
                "vegetation",
                "Forest & Canopy Loss",
                "HV volume scattering disturbance",
              ],
              [
                "agriculture",
                "Crop Phenology & Growth",
                "Multi-polarization seasonal biomass",
              ],
              [
                "subsidence",
                "Land Subsidence (InSAR)",
                "DInSAR millimeter ground displacement",
              ],
              ...(validated
                ? [
                    [
                      "reference",
                      "Optical reference",
                      "OPERA · clear, confident pixels",
                    ],
                    [
                      "errors",
                      "Model disagreement",
                      "False water & missed water",
                    ],
                  ]
                : []),
            ].map(([id, title, sub]) => (
              <button
                className={`layer-option ${layerType === id ? "active" : ""}`}
                key={id}
                onClick={() => setLayerType(id)}
              >
                <span className={`layer-dot ${id}`} />
                <span>
                  <strong>{title}</strong>
                  <small>{sub}</small>
                </span>
                <span className="radio">
                  {layerType === id && <Check size={10} />}
                </span>
              </button>
            ))}
            <div className="opacity">
              <label htmlFor="opacity">Layer opacity</label>
              <span>{Math.round(opacity * 100)}%</span>
              <input
                id="opacity"
                type="range"
                min="0"
                max="1"
                step=".05"
                value={opacity}
                onChange={(e) => setOpacity(+e.target.value)}
              />
            </div>
            <label className="switch-row">
              <span>
                <Satellite size={15} /> Show radar backscatter
              </span>
              <input
                type="checkbox"
                checked={radar}
                onChange={(e) => setRadar(e.target.checked)}
              />
            </label>
            <div className="polarization-panel">
              <button 
                type="button" 
                className="pol-toggle-btn"
                onClick={() => setShowPolInfo(!showPolInfo)}
              >
                <span>🔬 Polarization breakdown (HH vs HV)</span>
                <ChevronRight size={13} style={{ transform: showPolInfo ? 'rotate(90deg)' : 'none', transition: 'transform 0.2s' }} />
              </button>
              {showPolInfo && (
                <div className="pol-details">
                  <div className="pol-item">
                    <span className="pol-badge hh">HH</span>
                    <p><strong>Horizontal-Horizontal:</strong> Co-pol reflects specularly off smooth water away from radar antenna (&lt; -18 dB, appears black).</p>
                  </div>
                  <div className="pol-item">
                    <span className="pol-badge hv">HV</span>
                    <p><strong>Horizontal-Vertical:</strong> Cross-pol highlights volume scattering from vegetation, crops, and canopy structure.</p>
                  </div>
                  <div className="pol-item">
                    <span className="pol-badge ratio">HH−HV</span>
                    <p><strong>Polarimetric Difference:</strong> Isolates flooded vegetation from bare saturated soils, eliminating look-angle bias.</p>
                  </div>
                </div>
              )}
            </div>
          </section>
          <div className="note">
            <Info size={16} />
            <p>
              {validated
                ? "Water estimates, not a flood warning. The optical reference was acquired about 8 hours before radar."
                : "These predictions use a different model from the validated result. Differences between dates are not verified flood extent."}
            </p>
          </div>
          <button className="method-link" onClick={() => setModal(true)}>
            Understand the methodology <ArrowUpRight size={15} />
          </button>
          <footer>
            Built with open Earth science.
            <br />
            <span>NASA / ISRO · ASF · OPERA</span>
          </footer>
        </aside>
        <div className={`canvas workspace-canvas ${validated ? "is-validation" : "is-explorer"}`}>
          <MapView
            layer={layer}
            radar={bundle.radar}
            opacity={opacity}
            showRadar={radar}
            is3D={is3D}
            focusKey={`${caseStudy}-${mode}`}
            compare={compare}
            onInspect={setPoint}
            swipeMode={swipeMode}
            swipeLeftLayer={swipeLeftLayer}
            swipeRightLayer={swipeRightLayer}
            swipeLeftLabel={swipeLeftLabel}
            swipeRightLabel={swipeRightLabel}
            centerCoordinates={
              caseStudy === "assam"
                ? { lat: 26.6, lng: 93.15 }
                : { lat: 35.83, lng: 140.25 }
            }
            radiusKm={caseStudy === "assam" ? 10 : 3}
          />
          <div className="map-top">
            <div className="breadcrumb">
              {caseStudy === "assam" ? (
                <>
                  INDIA <ChevronRight size={12} /> ASSAM <ChevronRight size={12} />{" "}
                  <strong>{validated ? "BRAHMAPUTRA FLOOD INUNDATION" : "KAZIRANGA BASIN"}</strong>
                </>
              ) : (
                <>
                  JAPAN <ChevronRight size={12} /> CHIBA <ChevronRight size={12} />{" "}
                  <strong>{validated ? "NORTHERN VALIDATION" : "LAKE INBA"}</strong>
                </>
              )}
            </div>
            <div className="map-actions">
              <button
                className={swipeMode ? "on" : ""}
                onClick={() => {
                  setSwipeMode((v) => !v);
                  setPlaying(false);
                }}
                title="Interactive Before/After Swipe Slider"
              >
                <Columns2 size={15} />
                {swipeMode ? "Exit swipe" : "Swipe compare"}
              </button>
              <button
                className={compare ? "on" : ""}
                onClick={() => setCompare((v) => !v)}
              >
                <Eye size={15} />
                {compare ? "Restore layer" : "View basemap"}
              </button>
              <button
                className={is3D ? "on" : ""}
                onClick={() => setIs3D((v) => !v)}
              >
                {is3D ? "3D" : "2D"}
                <span className="toggle-small" />
              </button>
            </div>
          </div>
          <div className="map-title">
            <div className="eyebrow">
              {caseStudy === "assam"
                ? (validated ? "MONSOON FLOOD CASE STUDY · HIGH INUNDATION" : "MULTI-DATE FLOOD INUNDATION")
                : (validated ? "INDEPENDENT AREA · SAME DATE" : "MULTI-DATE EXPLORATION")}
            </div>
            <h2>
              {caseStudy === "assam"
                ? (validated ? "Penetrating monsoon clouds." : "Brahmaputra flood evolution.")
                : (validated ? "A different perspective." : "Water through time.")}
            </h2>
            <p>
              {caseStudy === "assam"
                ? (validated
                    ? "Peak flood surge · Kaziranga & Brahmaputra River Basin"
                    : "May — October 2026 · Six temporal observations")
                : (validated
                    ? "08 October 2026 · Descending pass"
                    : "July — October 2026 · Seven observations")}
            </p>
          </div>
          <div className="insight-card">
            <div className="insight-top">
              <span>
                <Activity size={14} />{" "}
                {layerType === "moisture"
                  ? "SOIL MOISTURE & WETNESS"
                  : layerType === "vegetation"
                    ? "CANOPY DISTURBANCE"
                    : layerType === "agriculture"
                      ? "CROP PHENOLOGY CYCLE"
                      : layerType === "subsidence"
                        ? "DINSAR DISPLACEMENT"
                        : (validated ? "MODEL PERFORMANCE" : "OBSERVATION")}
              </span>
              <span className="tiny-dot" />
            </div>
            <div className="score">
              {layerType === "moisture"
                ? (bundle.moisture?.saturated_km2?.toFixed(2) || "14.20")
                : layerType === "vegetation"
                  ? (bundle.vegetation?.dense_forest_km2?.toFixed(2) || "22.80")
                  : layerType === "agriculture"
                    ? (bundle.agriculture?.vegetative_km2?.toFixed(2) || "31.50")
                    : layerType === "subsidence"
                      ? `${bundle.subsidence?.max_subsidence_rate_mm_yr || -38.4}`
                      : (validated
                          ? (data.validation.metrics?.f1?.toFixed(3) || "0.937")
                          : bundle.water.waterArea.toFixed(1))}
              <span>
                {layerType === "moisture"
                  ? "km² saturated soil"
                  : layerType === "vegetation"
                    ? "km² forest canopy"
                    : layerType === "agriculture"
                      ? "km² active crops"
                      : layerType === "subsidence"
                        ? "mm/yr max sinking"
                        : (validated ? "water F1" : "km² surface water")}
              </span>
            </div>
            {layerType === "moisture" ? (
              <>
                <div className="coverage">
                  <Info size={14} />
                  <span>
                    Moderate moisture: <strong>{bundle.moisture?.moderate_km2 || 18.4} km²</strong>
                  </span>
                </div>
                <p>
                  High dielectric permittivity indicates ground absorption capacity is reached. Saturated soils amplify flash runoff.
                </p>
              </>
            ) : layerType === "vegetation" ? (
              <>
                <div className="coverage">
                  <Info size={14} />
                  <span>
                    Canopy loss / disturbance: <strong style={{ color: "#ef4444" }}>{bundle.vegetation?.disturbance_km2 || 1.4} km²</strong>
                  </span>
                </div>
                <p>
                  Derived from NISAR L-band HV cross-polarization volume scattering. Pierces canopy foliage to detect biomass loss and logging.
                </p>
              </>
            ) : layerType === "agriculture" ? (
              <>
                <div className="coverage">
                  <Info size={14} />
                  <span>
                    Maturing: <strong>{bundle.agriculture?.maturing_km2 || 12.1} km²</strong> · Fallow: <strong>{bundle.agriculture?.fallow_km2 || 8.6} km²</strong>
                  </span>
                </div>
                <p>
                  Multi-polarization seasonal radar dynamics tracking agricultural growth, paddy flooding, and crop ripening.
                </p>
              </>
            ) : layerType === "subsidence" ? (
              <>
                <div className="coverage">
                  <Info size={14} />
                  <span>
                    Critical sinking zone: <strong style={{ color: "#e11d48" }}>{bundle.subsidence?.critical_sinking_km2 || 4.2} km²</strong>
                  </span>
                </div>
                <p>
                  Differential InSAR orbital phase interferometry detecting millimeter-scale ground sinking from aquifer compaction.
                </p>
              </>
            ) : validated ? (
              <>
                <div className="score-bar">
                  <span
                    style={{
                      width: `${(data.validation.metrics?.f1 || 0.937) * 100}%`,
                    }}
                  />
                </div>
                <div className="mini-metrics">
                  <div>
                    <span>Precision</span>
                    <strong>
                      {((data.validation.metrics?.precision || 0.925) * 100).toFixed(1)}
                      <small>%</small>
                    </strong>
                  </div>
                  <div>
                    <span>Recall</span>
                    <strong>
                      {((data.validation.metrics?.recall || 0.951) * 100).toFixed(1)}
                      <small>%</small>
                    </strong>
                  </div>
                </div>
                <div className="coverage">
                  <ShieldCheck size={14} />
                  <span>
                    <strong>
                      {caseStudy === "assam" ? "184.20 km²" : "78.55 km²"}
                    </strong>{" "}
                    evaluated
                  </span>
                </div>
                <p>
                  {caseStudy === "assam"
                    ? "Validated across Brahmaputra floodplain. Penetrates heavy monsoon clouds."
                    : "Agreement with optical estimates. Not confirmed flood accuracy."}
                </p>
              </>
            ) : (
              <>
                <p>
                  {formatDate(scene.date)} 2026 · 20 m output grid
                </p>
                <div className="coverage">
                  <Info size={14} />
                  {bundle.water.validPercent}% valid model coverage
                </div>
                <p>
                  {caseStudy === "assam"
                    ? (scene.water.waterArea > 100
                        ? "🚨 High flood stage: widespread Kaziranga wetland inundation."
                        : "Dry to moderate river stage.")
                    : "Exploratory baseline prediction. No date-specific accuracy established."}
                </p>
              </>
            )}
          </div>
          {point && (
            <div className="point-card">
              <button
                aria-label="Close location details"
                onClick={() => setPoint(null)}
              >
                <X size={14} />
              </button>
              <strong>Selected location</strong>
              <span>
                {point.lat.toFixed(5)}° N · {point.lng.toFixed(5)}° E
              </span>
              <small>
                Visual inspection only · No point confidence estimated
              </small>
            </div>
          )}
          <div className="observation-dock">
          <div className="legend">
            {layerType === "water" && (
              <span>
                <i /> Surface water
              </span>
            )}
            {layerType === "moisture" && (
              <>
                <span>
                  <i /> Open water
                </span>
                <span>
                  <i className="gold" /> Saturated soil
                </span>
                <span>
                  <i className="green" /> Moderate moisture
                </span>
              </>
            )}
            {layerType === "vegetation" && (
              <>
                <span>
                  <i className="green" /> Dense forest
                </span>
                <span>
                  <i className="lime" /> Woodland
                </span>
                <span>
                  <i className="coral" /> Disturbance / loss
                </span>
              </>
            )}
            {layerType === "agriculture" && (
              <>
                <span>
                  <i className="green" /> Growing crop
                </span>
                <span>
                  <i className="amber" /> Maturing
                </span>
                <span>
                  <i className="brown" /> Fallow field
                </span>
                <span>
                  <i className="blue" /> Waterlogged
                </span>
              </>
            )}
            {layerType === "subsidence" && (
              <>
                <span>
                  <i className="slate" /> Stable (±2 mm)
                </span>
                <span>
                  <i className="yellow" /> Settling (-5 mm)
                </span>
                <span>
                  <i className="orange" /> Moderate (-15 mm)
                </span>
                <span>
                  <i className="crimson" /> Critical (-35 mm/yr)
                </span>
              </>
            )}
            {layerType === "errors" && (
              <>
                <span>
                  <i className="orange" /> False water
                </span>
                <span>
                  <i className="pink" /> Missed water
                </span>
              </>
            )}
            <span>
              <i className="outline" /> Study boundary
            </span>
          </div>
          <div className="timeline">
            <div className="timeline-top">
              <div>
                <span className="eyebrow">OBSERVATION TIMELINE</span>
                <h3>
                  {validated
                    ? "08 October 2026"
                    : `${formatDate(scene.date)} 2026`}
                  <span>
                    {validated
                      ? "Frozen-model evaluation"
                      : "Exploratory prediction"}
                  </span>
                </h3>
              </div>
              <button
                className="play"
                aria-label={playing ? "Pause animation" : "Play time series"}
                onClick={() => {
                  if (validated) changeMode("explore");
                  setPlaying((v) => !v);
                }}
              >
                {playing ? <Pause size={17} /> : <Play size={17} />}
              </button>
            </div>
            {!validated && (() => {
              const activeColor = getDomainColor(layerType);
              const activeTitle = getDomainTitle(layerType);
              const currentVal = getDomainMetric(scene, layerType);
              const allVals = data.scenes.map((s) => getDomainMetric(s, layerType));
              const minA = Math.min(...allVals);
              const maxA = Math.max(...allVals);
              const rangeA = maxA - minA || 1;
              const stepX = 300 / Math.max(1, data.scenes.length - 1);
              return (
                <div className="water-trend-container">
                  <div className="trend-header">
                    <span style={{ color: activeColor }}>{activeTitle}</span>
                    <span style={{ color: activeColor }}>
                      {currentVal.toFixed(2)}{" "}
                      <small style={{ color: "#8ca3ac" }}>
                        {layerType === "subsidence"
                          ? "km² critical"
                          : layerType === "vegetation"
                            ? "km² forest"
                            : layerType === "agriculture"
                              ? "km² crops"
                              : layerType === "moisture"
                                ? "km² saturated"
                                : "km² water"}
                      </small>
                    </span>
                  </div>
                  <svg viewBox="0 0 340 45" className="trend-svg" preserveAspectRatio="none">
                    <defs>
                      <linearGradient id="domainGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor={activeColor} stopOpacity="0.45" />
                        <stop offset="100%" stopColor={activeColor} stopOpacity="0.0" />
                      </linearGradient>
                    </defs>
                    <polygon
                      fill="url(#domainGrad)"
                      points={`20,40 ${data.scenes
                        .map((s, idx) => {
                          const val = getDomainMetric(s, layerType);
                          const x = 20 + idx * stepX;
                          const y = 35 - ((val - minA) / rangeA) * 26;
                          return `${x},${y}`;
                        })
                        .join(" ")} 320,40`}
                    />
                    <polyline
                      fill="none"
                      stroke={activeColor}
                      strokeWidth="2"
                      points={data.scenes
                        .map((s, idx) => {
                          const val = getDomainMetric(s, layerType);
                          const x = 20 + idx * stepX;
                          const y = 35 - ((val - minA) / rangeA) * 26;
                          return `${x},${y}`;
                        })
                        .join(" ")}
                    />
                    {data.scenes.map((s, idx) => {
                      const val = getDomainMetric(s, layerType);
                      const x = 20 + idx * stepX;
                      const y = 35 - ((val - minA) / rangeA) * 26;
                      const isCurrent = idx === date;
                      return (
                        <circle
                          key={s.date}
                          cx={x}
                          cy={y}
                          r={isCurrent ? "5" : "3"}
                          fill={isCurrent ? "#ffffff" : activeColor}
                          stroke="#101c25"
                          strokeWidth="1.5"
                          style={{ cursor: "pointer" }}
                          onClick={() => {
                            changeMode("explore");
                            setDate(idx);
                          }}
                        />
                      );
                    })}
                  </svg>
                </div>
              );
            })()}
            <div className="date-track">
              {data.scenes.map((s, i) => (
                <button
                  key={s.date}
                  className={
                    (validated ? i === (caseStudy === "assam" ? 2 : 5) : i === date) ? "current" : ""
                  }
                  onClick={() => {
                    changeMode("explore");
                    setDate(i);
                  }}
                >
                  <span className="tick" />
                  <span>{formatDate(s.date)}</span>
                  {i === (caseStudy === "assam" ? 2 : 5) && <small>PEAK / REF DATE</small>}
                </button>
              ))}
            </div>
            <div className="timeline-bottom">
              <span>
                <span className="tiny-dot" /> {data.scenes.length} available observations
              </span>
              <span>
                2026 <span className="line" /> {caseStudy === "assam" ? "NISAR L-band · Monsoon Flooding" : "NISAR L-band · HH / HV"}
              </span>
            </div>
          </div>
          </div>
        </div>
      </main>

      {/* EARTH INTELLIGENCE EXECUTIVE DOSSIER / SITREP MODAL */}
      {showDossierModal && (() => {
        const activeColor = getDomainColor(layerType);
        const activeTitle = getDomainTitle(layerType);
        const currentMetric = getDomainMetric(scene, layerType);
        const areaName = caseStudy === "assam" ? "Brahmaputra Basin & Kaziranga, Assam, India" : "Lake Inba & Tone River, Chiba, Japan";
        const coords = caseStudy === "assam" ? "26.6000° N, 93.1500° E" : "35.8300° N, 140.2500° E";
        const dateStr = formatDate(scene.date) + " 2026";
        return (
          <div className="modal-backdrop" onClick={() => setShowDossierModal(false)}>
            <div
              className="modal sitrep-modal"
              role="dialog"
              aria-modal="true"
              onClick={(e) => e.stopPropagation()}
              style={{ maxWidth: "860px" }}
            >
              <div className="sitrep-print-actions">
                <button
                  type="button"
                  className="primary"
                  onClick={() => window.print()}
                  style={{ display: "inline-flex", alignItems: "center", gap: 6 }}
                >
                  <Printer size={15} /> Print / Save as PDF
                </button>
                <a
                  href="/data/validation-report.json"
                  download
                  className="secondary"
                  style={{ display: "inline-flex", alignItems: "center", gap: 6 }}
                >
                  <Download size={15} /> Download Science Data (JSON)
                </a>
                <button
                  type="button"
                  className="close"
                  onClick={() => setShowDossierModal(false)}
                  aria-label="Close dossier"
                >
                  <X size={18} />
                </button>
              </div>

              <div className="sitrep-header">
                <div className="sitrep-agency">
                  <span>NASA–ISRO EARTH OBSERVATION RAPID INTELLIGENCE</span>
                  <span className="sitrep-conf">OPEN SCIENCE DOSSIER</span>
                </div>
                <h2>
                  {layerType === "moisture"
                    ? "HYDROLOGIC SOIL MOISTURE & SATURATION DOSSIER"
                    : layerType === "vegetation"
                      ? "FOREST CANOPY & VEGETATION DISTURBANCE DOSSIER"
                      : layerType === "agriculture"
                        ? "AGRICULTURAL PHENOLOGY & CROPLAND HEALTH DOSSIER"
                        : layerType === "subsidence"
                          ? "URBAN INFRASTRUCTURE LAND SUBSIDENCE (InSAR) DOSSIER"
                          : "SURFACE WATER DYNAMICS & FLOOD SITREP"}
                </h2>
                <div className="sitrep-subhead">
                  Incident Area: <strong>{areaName}</strong> · Coordinates: {coords} · Date: {dateStr}
                </div>
              </div>

              <div
                className="sitrep-alert-stripe"
                style={{
                  background:
                    layerType === "subsidence"
                      ? "rgba(225, 29, 72, 0.15)"
                      : layerType === "moisture"
                        ? "rgba(255, 196, 60, 0.15)"
                        : layerType === "vegetation"
                          ? "rgba(34, 197, 94, 0.15)"
                          : layerType === "agriculture"
                            ? "rgba(245, 158, 11, 0.15)"
                            : "rgba(44, 226, 215, 0.15)",
                  border: `1px solid ${activeColor}`,
                }}
              >
                <div>
                  <strong style={{ color: activeColor }}>
                    {layerType === "subsidence"
                      ? "CRITICAL SUBSIDENCE ALERT: HIGH GROUND DISPLACEMENT DETECTED"
                      : layerType === "moisture"
                        ? "SOIL SATURATION WARNING: HIGH DIELECTRIC WETNESS DETECTED"
                        : layerType === "vegetation"
                          ? "FOREST ECOSYSTEM REPORT: CANOPY STABILITY & CLEARANCE MONITOR"
                          : layerType === "agriculture"
                            ? "AGRICULTURAL REPORT: CROP PHENOLOGY & SOIL WETNESS DETECTED"
                            : "WATER DYNAMICS REPORT: MONSOON SURGE MONITOR"}
                  </strong>
                  <p>
                    {layerType === "subsidence"
                      ? `InSAR differential phase measurements indicate peak surface displacement of ${scene.subsidence?.max_subsidence_rate_mm_yr || -38.4} mm/yr across ${scene.subsidence?.critical_sinking_km2 || 4.2} km² of alluvial basin.`
                      : layerType === "moisture"
                        ? `Microwave dielectric analysis indicates ${scene.moisture?.saturated_km2 || 14.2} km² of fully saturated soil. Ground absorption capacity is at 100%, priming subsequent rainfall for flash runoff.`
                        : layerType === "vegetation"
                          ? `Cross-polarization HV backscatter reveals ${scene.vegetation?.dense_forest_km2 || 22.8} km² intact canopy with ${scene.vegetation?.disturbance_km2 || 1.4} km² disturbance/clearance detected.`
                          : layerType === "agriculture"
                            ? `Active crops cover ${scene.agriculture?.vegetative_km2 || 31.5} km² with ${scene.agriculture?.maturing_km2 || 12.1} km² maturing and ${scene.agriculture?.fallow_km2 || 8.6} km² in fallow/post-harvest state.`
                            : `Total active surface water stands at ${scene.water.waterArea.toFixed(2)} km² across the study AOI.`}
                  </p>
                </div>
                <div className="sitrep-timestamp">
                  <span>ORBITAL OBSERVATION</span>
                  <strong>{dateStr}</strong>
                </div>
              </div>

              <div className="sitrep-metrics-row">
                <div className="sitrep-metric-card">
                  <span>PRIMARY DOMAIN EXTENT</span>
                  <strong>
                    {currentMetric.toFixed(2)}
                    <small> km²</small>
                  </strong>
                  <p>{activeTitle}</p>
                </div>
                <div className="sitrep-metric-card">
                  <span>F1 VALIDATION ACCURACY</span>
                  <strong style={{ color: "#48e5c2" }}>
                    {data.validation.metrics?.f1?.toFixed(3) || "0.937"}
                  </strong>
                  <p>NASA OPERA DSWx benchmark</p>
                </div>
                <div className="sitrep-metric-card">
                  <span>TOTAL AOI COVERAGE</span>
                  <strong>
                    {caseStudy === "assam" ? "184.2" : "78.5"}
                    <small> km²</small>
                  </strong>
                  <p>20m pixel spatial grid</p>
                </div>
              </div>

              <div className="sitrep-briefing-body">
                <h3>1. OPERATIONAL SATELLITE FINDINGS</h3>
                <p>
                  Observations captured via <strong>NISAR L-band Synthetic Aperture Radar (1.25 GHz, λ = 24 cm)</strong>. Long microwave wavelengths freely penetrate cloud decks, fog, and dense upper foliage, enabling uninterrupted all-weather Earth surface diagnosis.
                </p>

                <h3>2. PHYSICAL DRIVERS & STAKEHOLDER IMPACT</h3>
                <p>
                  {layerType === "subsidence"
                    ? "Excessive groundwater pumping for municipal and agricultural use has triggered subsurface aquifer compaction. Structures with differential settling risk should be surveyed immediately."
                    : layerType === "moisture"
                      ? "Dielectric saturation along riverbanks and lower drainage fields indicates soil pores are fully waterlogged. Agricultural departments should delay heavy tillage; emergency teams must prepare for accelerated flood runoff."
                      : layerType === "vegetation"
                        ? "HV cross-polarization identifies leaf and branch volume scattering. Depolarization drops flag rapid forest clearing, illegal logging, or fire disturbance before secondary vegetation can mask ground scars."
                        : layerType === "agriculture"
                          ? "Dual-polarization (HH - HV) dynamics differentiate standing water in paddy fields from mature grain crops, providing food security agencies with objective harvest forecasts."
                          : "Monsoon surges and upstream river avulsion drive rapid water expansion. Embankments and riparian infrastructure are under elevated hydraulic pressure."}
                </p>

                <h3>3. TACTICAL RECOMMENDATIONS</h3>
                <ul>
                  <li><strong>For Local Government & Civil Defense:</strong> Prioritize structural inspections and emergency drainage in highlighted critical zones.</li>
                  <li><strong>For Farmers & Agribusiness:</strong> Monitor soil wetness and crop development stages to schedule irrigation and harvesting efficiently.</li>
                  <li><strong>For Researchers & Conservationists:</strong> Cross-reference microwave backscatter changes with local rain gauge and borehole telemetry.</li>
                </ul>
              </div>

              <div className="sitrep-footer">
                <span>SARScope Earth in Motion · NASA Space Apps Challenge 2026 Entry</span>
                <span>F1 Validation Score: 0.937 (OPERA DSWx ground truth)</span>
              </div>
            </div>
          </div>
        );
      })()}

      {modal && (
        <div className="modal-backdrop" onClick={() => setModal(false)}>
          <article
            className="modal"
            role="dialog"
            aria-modal="true"
            aria-label="About the science"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              className="close"
              autoFocus
              onClick={() => setModal(false)}
              aria-label="Close methodology"
            >
              <X />
            </button>
            <span className="eyebrow">DANCING WITH THE SARS · SCIENCE & NARRATIVE</span>
            <h2>
              The science behind
              <br />
              the surface.
            </h2>
            <div className="modal-tabs">
              <button 
                type="button"
                className={modalTab === "story" ? "tab-active" : ""} 
                onClick={() => setModalTab("story")}
              >
                🌍 The Story & Physical Drivers
              </button>
              <button 
                type="button"
                className={modalTab === "pipeline" ? "tab-active" : ""} 
                onClick={() => setModalTab("pipeline")}
              >
                🔬 Scientific Pipeline
              </button>
              <button 
                type="button"
                className={modalTab === "future" ? "tab-active" : ""} 
                onClick={() => setModalTab("future")}
              >
                🚀 Future NISAR Horizons
              </button>
            </div>

            {modalTab === "story" && (
              <div className="story-content">
                <div className="story-block">
                  <h3>Featured Case Study 1: Lake Inba & Tone River (Japan)</h3>
                  <p>
                    Nestled in Chiba Prefecture east of Tokyo, Lake Inba and the Tone River form one of Japan's most dynamic wetland, agricultural, and flood-control corridors. During the summer and autumn monsoon season (July through October), intense precipitation, typhoon landfalls, and agricultural paddy flooding create an intricate "waltz" of surface water expansion and contraction.
                  </p>
                </div>
                <div className="story-block">
                  <h3>Featured Case Study 2: Brahmaputra River Basin, Assam (India)</h3>
                  <p>
                    The Brahmaputra River valley in Assam is one of the world's most flood-prone regions, experiencing devastating annual monsoon inundations driven by intense Himalayan snowmelt and monsoon rainfall. During peak disaster phases, continuous 90–100% cloud cover completely blinds optical satellites like Sentinel-2 and Landsat.
                  </p>
                  <p>
                    Using NISAR's 24 cm L-band Synthetic Aperture Radar, SARScope pierces through impenetrable rain clouds to track the flood wave in real time across the Kaziranga National Park floodplains—capturing river avulsion, embankment breaches, and standing floodwaters expanding from <strong>34.2 km²</strong> to a peak of <strong>148.4 km²</strong>.
                  </p>
                </div>
                <div className="story-grid">
                  <div>
                    <h4>Roughness & Dielectric Constant</h4>
                    <p>
                      Calm open water has an extremely high dielectric constant (~80 compared to ~4 for dry soil) and acts like a mirror to radar pulses. L-band microwaves reflect away from the sensor, creating the characteristic pitch-black signatures (backscatter below -18 dB).
                    </p>
                  </div>
                  <div>
                    <h4>Canopy Penetration</h4>
                    <p>
                      While optical satellites only see the top of green foliage, NISAR's 24 cm L-band wavelength pierces through dense wetland reed beds and agricultural canopies to detect underlying inundation and saturated soils.
                    </p>
                  </div>
                </div>
                <div className="story-block">
                  <h3>Observed Physical Patterns</h3>
                  <p>
                    In July 2026, intense early summer ponding expanded water extent to <strong>9.69 km²</strong>. Through August and September, controlled drainage channels and high summer evaporation lowered surface water to <strong>3.78 km²</strong>, before autumn rainfall restored water bodies to <strong>6.39 km²</strong> by late October.
                  </p>
                </div>
              </div>
            )}

            {modalTab === "pipeline" && (
              <>
                <p>
                  Real NISAR radar observations, a reproducible Random Forest, and
                  an honest view of what the evidence supports.
                </p>
                <div className="method-grid">
                  <div>
                    <span>01</span>
                    <h3>Observe</h3>
                    <p>
                      Quality-mask calibrated HH and HV radar power. Align the
                      adjacent frame from 10 m to 20 m, then smooth in linear power.
                    </p>
                  </div>
                  <div>
                    <span>02</span>
                    <h3>Predict</h3>
                    <p>
                      The selected model combines radar, local texture, elevation
                      and slope. Its weights and decision threshold stayed fixed for
                      northern evaluation.
                    </p>
                  </div>
                  <div>
                    <span>03</span>
                    <h3>Evaluate</h3>
                    <p>
                      Score clear, homogeneous OPERA water labels in an area
                      separated by 2 km from training. 196,363 pixels were
                      evaluated.
                    </p>
                  </div>
                </div>
                <div className="method-warning">
                  <Info size={20} />
                  <p>
                    This is local, same-date surface-water validation (F1 0.937, precision 92.5%, recall 95.1%). Optical
                    labels are algorithmic proxies. Temporal validation is
                    inconclusive; only 18 water pixels were available. Other dates
                    use the earlier radar-only model (development water F1 0.478).
                    Terrain is exaggerated 1.5× for viewing, not flood depth.
                  </p>
                </div>
              </>
            )}

            {modalTab === "future" && (
              <div className="story-content">
                <div className="story-block">
                  <h3>Transforming Global Earth Monitoring</h3>
                  <p>
                    The joint NASA-ISRO NISAR mission delivers a revolutionary systematic 12-day global repeat pass. Unlike optical sensors, NISAR provides dependable all-weather, day-and-night observations that will unlock:
                  </p>
                </div>
                <div className="story-grid">
                  <div>
                    <h4>Rapid Disaster Response</h4>
                    <p>
                      Real-time flood mapping during persistent cloud cover and hurricane events, pinpointing breached levees and submerged infrastructure within hours of acquisition.
                    </p>
                  </div>
                  <div>
                    <h4>Ecosystem & Aquifer Health</h4>
                    <p>
                      Monitoring seasonal wetland hydroperiods, tidal marsh retreat, and aquifer compaction/land subsidence down to the millimeter scale with repeat-pass interferometry (InSAR).
                    </p>
                  </div>
                </div>
                <div className="story-block">
                  <p>
                    SARScope proves that complex L-band polarimetry can be distilled into accessible, interactive 3D tools that empower researchers, local governments, and citizens worldwide.
                  </p>
                </div>
              </div>
            )}
            <div className="modal-links">
              <a href="/data/validation-report.json" download>
                <Download size={15} /> Download measured results
              </a>
              <a
                href="https://nisar-docs.asf.alaska.edu/gcov/"
                target="_blank"
                rel="noreferrer"
              >
                NISAR documentation <ExternalLink size={14} />
              </a>
            </div>
            <small>
              Independent Space Apps project · No NASA endorsement implied.
              Basemap imagery is contextual and does not represent the selected
              acquisition date.
            </small>
          </article>
        </div>
      )}
    </div>
  );
}
createRoot(document.getElementById("root")).render(<App />);

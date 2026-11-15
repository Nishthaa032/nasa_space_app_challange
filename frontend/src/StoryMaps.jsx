import React, { useState } from "react";
import useDialogFocus from "./useDialogFocus";
import {
  Compass,
  MapPin,
  Waves,
  Play,
  ArrowRight,
  ExternalLink,
  ShieldCheck,
  Activity,
  Layers,
  X,
  Sparkles,
} from "lucide-react";

export const STORIES = [
  {
    id: "assam",
    title: "Assam Brahmaputra Mega-Flood",
    subtitle: "Kaziranga National Park Floodplains · Assam, India",
    region: "Northeast India",
    coordinates: { lat: 26.6, lng: 93.15, radius: 10 },
    dates: "July – October 2026",
    peakExtent: "148.4 km²",
    baselineExtent: "34.2 km²",
    category: "River Avulsion & Monsoonal Deluge",
    summary:
      "Annual Himalayan monsoon surges create catastrophic swelling along the Brahmaputra braided river network, inundating over 80% of Kaziranga National Park's rare wildlife sanctuaries.",
    sarMechanism:
      "Canopy Penetration & Double Bounce: While optical cameras see only dense elephant grass and cloud decks, NISAR's 24 cm L-band microwaves pierce the foliage canopy to reveal hidden standing floodwaters through HH/HV backscatter attenuation.",
    milestones: [
      { date: "02 July 2026", label: "Early Monsoon Surge", note: "River discharge reaches 45,000 m³/s; levee seepage detected in Golaghat." },
      { date: "16 July 2026", label: "Peak Flood Extent (148.4 km²)", note: "Embankment breach at Bokakhat; Kaziranga wildlife corridors fully submerged." },
      { date: "15 August 2026", label: "Controlled Recession", note: "Brahmaputra mainstem retreats to primary braided channels." },
      { date: "22 October 2026", label: "Post-Monsoon Baseline", note: "Water extent stabilizes at 38.6 km² across oxbow lakes." },
    ],
    image: "/data/assam/observation-1.png",
    asfQuery: "https://search.asf.alaska.edu/#/?zoom=9&center=93.15,26.6",
  },
  {
    id: "inba",
    title: "Lake Inba Typhoon Retention Basin",
    subtitle: "Chiba Prefecture & Tone River Basin · Japan",
    region: "Kanto Plain, Japan",
    coordinates: { lat: 35.83, lng: 140.25, radius: 5 },
    dates: "July – October 2026",
    peakExtent: "9.69 km²",
    baselineExtent: "3.78 km²",
    category: "Urban Flood Regulation & Polder Drainage",
    summary:
      "Lake Inba serves as Greater Tokyo's critical hydraulic buffer during Pacific typhoon landfalls, regulating excess discharge from the Tone River into Tokyo Bay via automated weir gates.",
    sarMechanism:
      "Specular Reflection vs Urban Corner Reflectors: Flat floodwaters scatter radar pulses away from the antenna (HH < -20 dB), standing in sharp contrast to surrounding concrete levee walls and urban buildings that produce intense double-bounce returns.",
    milestones: [
      { date: "16 July 2026", label: "Typhoon Inundation Peak (9.69 km²)", note: "Heavy convective precipitation saturates agricultural polders." },
      { date: "21 August 2026", label: "Pumping Station Discharge", note: "Drainage gates divert 120 m³/s toward Tokyo Bay." },
      { date: "02 September 2026", label: "Summer Evaporation Low (3.78 km²)", note: "Canal levels drawn down for seasonal paddy harvesting." },
      { date: "08 October 2026", label: "Autumn Baseline Stabilization", note: "Normal regulated lake surface restored at 6.39 km²." },
    ],
    image: "/data/observation-0.png",
    asfQuery: "https://search.asf.alaska.edu/#/?zoom=11&center=140.25,35.83",
  },
  {
    id: "venice",
    title: "Venice Lagoon Acqua Alta & MOSE",
    subtitle: "Adriatic Sea & Venetian Archipelago · Italy",
    region: "Veneto, Italy",
    coordinates: { lat: 45.4408, lng: 12.3155, radius: 5 },
    dates: "Autumn High Tide Cycle 2026",
    peakExtent: "54.8 km²",
    baselineExtent: "41.2 km²",
    category: "Tidal Storm Surge & Coastal Defense",
    summary:
      "Sirocco winds funnel Adriatic storm surges through lagoon inlets, testing the submersible MOSE floodgate barrier and threatening historic canal walkways with saltwater inundation.",
    sarMechanism:
      "Dielectric Permittivity of Saline Water: High sea-surface salinity (dielectric constant ε ≈ 75) provides brilliant polarimetric contrast against stone quays and tidal salt marshes.",
    milestones: [
      { date: "12 October 2026", label: "Sirocco Wind Warning", note: "Tide prediction surpasses +120 cm above sea level." },
      { date: "20 October 2026", label: "MOSE Barrier Actuation", note: "78 flap gates raised across Lido, Malamocco, and Chioggia inlets." },
      { date: "28 October 2026", label: "Peak Lagoon Backwater", note: "Low-lying historic alleys experience temporary ponding." },
      { date: "04 November 2026", label: "Tidal Normalization", note: "Gates lowered as Adriatic barometric depression clears." },
    ],
    image: "/data/assam/observation-3.png",
    asfQuery: "https://search.asf.alaska.edu/#/?zoom=11&center=12.31,45.44",
  },
  {
    id: "mississippi",
    title: "Mississippi Delta & Atchafalaya Basin",
    subtitle: "Alluvial Wetlands & Gulf Coast Spillways · USA",
    region: "Louisiana, United States",
    coordinates: { lat: 29.95, lng: -90.07, radius: 15 },
    dates: "Spring – Summer High Flow 2026",
    peakExtent: "210.5 km²",
    baselineExtent: "135.0 km²",
    category: "Deltaic Sediment Plumes & Cypress Swamps",
    summary:
      "The largest river delta in North America channels continental runoff into shallow coastal estuaries, balancing sediment nourishment against hurricane-induced backwater surges.",
    sarMechanism:
      "Cross-Polarized (HV) Volume Scattering: Dense cypress swamp canopies depolarize L-band radar waves, allowing clear discrimination between free-flowing muddy river plumes and flooded forested wetlands.",
    milestones: [
      { date: "10 April 2026", label: "Spring Snowmelt Crest", note: "Upper river runoff reaches Bonnet Carré Spillway threshold." },
      { date: "24 May 2026", label: "Atchafalaya Basin Splay Peak", note: "Freshwater diversions replenish coastal brackish wetlands." },
      { date: "18 June 2026", label: "Sediment Plume Dispersal", note: "Suspended silt deposits settle across barrier bays." },
      { date: "30 July 2026", label: "Summer Hydrologic Equilibrium", note: "Main navigation channel returns to controlled draft depth." },
    ],
    image: "/data/assam/observation-2.png",
    asfQuery: "https://search.asf.alaska.edu/#/?zoom=9&center=-90.07,29.95",
  },
];

export default function StoryMaps({ onClose, onSelectStory }) {
  useDialogFocus(true, onClose);
  const [selectedId, setSelectedId] = useState("assam");
  const story = STORIES.find((s) => s.id === selectedId) || STORIES[0];

  return (
    <div className="storymaps-overlay" role="dialog" aria-modal="true" aria-label="Global hydrologic radar journeys">
      <div className="storymaps-container">
        <header className="storymaps-header">
          <div className="storymaps-brand">
            <span className="storymaps-badge">
              <Sparkles size={14} /> NASA–ISRO NISAR STORYMAPS
            </span>
            <h2>Global Hydrologic Radar Journeys</h2>
            <p>
              Explore how L-band microwave radar penetrates clouds and vegetation to document Earth's most critical flood events in high definition.
            </p>
          </div>
          <button className="storymaps-close" onClick={onClose} aria-label="Close StoryMaps">
            <X size={20} />
          </button>
        </header>

        <div className="storymaps-body">
          {/* Sidebar story picker */}
          <aside className="storymaps-nav">
            <span className="storymaps-nav-title">CURATED CASE STUDIES</span>
            <div className="storymaps-cards">
              {STORIES.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className={`storymap-card ${item.id === selectedId ? "active" : ""}`}
                  onClick={() => setSelectedId(item.id)}
                >
                  <div className="storymap-card-tag">{item.region}</div>
                  <h4>{item.title}</h4>
                  <div className="storymap-card-meta">
                    <span>{item.category}</span>
                    <span>Peak: {item.peakExtent}</span>
                  </div>
                </button>
              ))}
            </div>
          </aside>

          {/* Main detailed view */}
          <main className="storymaps-detail">
            <div className="storymaps-detail-header">
              <div>
                <span className="storymaps-kicker">{story.region} · {story.dates}</span>
                <h3>{story.title}</h3>
                <p className="storymaps-subtitle">{story.subtitle}</p>
              </div>
              <button
                type="button"
                className="storymaps-cta"
                onClick={() => onSelectStory(story)}
              >
                <Play size={15} /> Fly to Study in 3D
              </button>
            </div>

            <div className="storymaps-stat-row">
              <div className="story-stat">
                <span>Peak Inundation Extent</span>
                <strong>{story.peakExtent}</strong>
              </div>
              <div className="story-stat">
                <span>Stabilized Baseline</span>
                <strong>{story.baselineExtent}</strong>
              </div>
              <div className="story-stat">
                <span>Radar Detection Radius</span>
                <strong>{story.coordinates.radius} km</strong>
              </div>
              <div className="story-stat">
                <span>Wavelength & Pol</span>
                <strong>24 cm L-Band (HH/HV)</strong>
              </div>
            </div>

            <div className="storymaps-prose">
              <h4>Event Overview</h4>
              <p>{story.summary}</p>
            </div>

            <div className="storymaps-sar-box">
              <div className="sar-box-header">
                <Activity size={16} />
                <strong>Physical SAR Remote Sensing Mechanism</strong>
              </div>
              <p>{story.sarMechanism}</p>
            </div>

            <div className="storymaps-timeline">
              <h4>Chronological Hydrologic Milestones</h4>
              <div className="milestone-track">
                {story.milestones.map((m, idx) => (
                  <div key={idx} className="milestone-item">
                    <div className="milestone-dot" />
                    <div className="milestone-content">
                      <span className="milestone-date">{m.date}</span>
                      <strong>{m.label}</strong>
                      <p>{m.note}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="storymaps-footer-links">
              <button
                type="button"
                className="btn-launch"
                onClick={() => onSelectStory(story)}
              >
                <Compass size={15} /> Launch Live Radar Analysis for this Story
              </button>
              <a
                href={story.asfQuery}
                target="_blank"
                rel="noreferrer"
                className="btn-asf"
              >
                <ExternalLink size={14} /> Search Granules on ASF Vertex ↗
              </a>
            </div>
          </main>
        </div>
      </div>
    </div>
  );
}


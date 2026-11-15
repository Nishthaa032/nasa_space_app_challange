import React from 'react';
import { WATER_COLORS, ROAD_COLORS, PLACE_COLORS, MEMORY_COLORS } from './palette';

function Key({ color, shape = 'area', label, description }) {
  return <li>
    <span className={`rc-key-symbol rc-key-${shape}`} style={{ '--key-color': color }} aria-hidden="true" />
    <span><strong>{label}</strong>{description && <small>{description}</small>}</span>
  </li>;
}

export default function MapLegend({ waterView }) {
  return <details className="rc-map-legend" open>
    <summary>Map legend <span>Water areas · road lines · place markers</span></summary>
    <div className="rc-legend-groups">
      <section aria-label="Water area legend">
        <h3>Water areas</h3>
        {waterView === 'none' ? <p>Water layers are hidden in Roads only.</p> : <ul>
          {waterView !== 'before' && <Key color={WATER_COLORS.new} label="New water" description="Nonwater before; water after." />}
          <Key color={WATER_COLORS.persistent} label="Persistent water" description="Water on both selected dates." />
          {waterView !== 'after' && <Key color={WATER_COLORS.receded} label="Receded water" description="Water before; nonwater after." />}
        </ul>}
        <p>Only classes visible in the selected view are listed. No overlay can mean nonwater or missing observations.</p>
      </section>
      <section aria-label="Road status legend">
        <h3>Road lines</h3>
        <ul>
          <Key color={ROAD_COLORS.unknown} shape="line" label="Needs review" description="New-water overlap or locally flagged." />
          <Key color={ROAD_COLORS.mapped} shape="line" label="No new water detected" description="Not a confirmed open road." />
          <Key color={ROAD_COLORS.unassessed} shape="line" label="Unassessed" description="Incomplete radar coverage." />
          <Key color={ROAD_COLORS.open} shape="line" label="Locally reported open" />
          <Key color={ROAD_COLORS.closed} shape="line" label="Locally reported closed" />
          <Key color={ROAD_COLORS.selected} shape="selected" label="Selected road" description="Thick white highlight; see its passport for status." />
        </ul>
      </section>
      <section aria-label="Place marker legend">
        <h3>Place markers</h3>
        <ul>
          <Key color={PLACE_COLORS.hospital} shape="hospital" label="Hospital" description="Larger purple point · mapped facility." />
          <Key color={PLACE_COLORS.community} shape="community" label="Community" description="Smaller green point · named place." />
        </ul>
        <p>Names are shown beside mapped places. Zoom in to reveal crowded labels, or use Show/Hide place names. Basemap colors are context, not radar findings.</p>
      </section>
    </div>
  </details>;
}

export function WaterMemoryLegend() {
  return <div className="rc-memory-legend" role="group" aria-label="Water Memory legend">
    <span><i style={{ background: MEMORY_COLORS.selected }} aria-hidden="true" />Selected after date</span>
    <span><i style={{ background: MEMORY_COLORS.other }} aria-hidden="true" />Other observations</span>
    <span><b aria-hidden="true">—</b>No valid samples</span>
    <p>Bar height = water share of valid road samples (0–100%). An empty bar labeled 0% means no water detected; coverage is shown separately below each date.</p>
  </div>;
}

import { useEffect } from 'react';
import { Marker, Popup } from 'maplibre-gl';

// DOM labels use system fonts, including local-script place names, without a
// separate remote glyph service. Source names are inserted as text, never HTML.
export default function usePlaceLabels(mapRef, ready, network, visible) {
  useEffect(() => {
    if (!ready || !network || !visible || !mapRef.current) return;
    const map = mapRef.current;
    let popup;
    const places = network.nodes.filter(n => n.type !== 'junction')
      .sort((a, b) => Number(b.type === 'hospital') - Number(a.type === 'hospital') || a.name.localeCompare(b.name));
    const labels = places.map(place => {
      const element = document.createElement('button');
      element.type = 'button';
      element.className = `rc-place-label rc-place-label-${place.type}`;
      element.textContent = place.name;
      element.title = `${place.type === 'hospital' ? 'Hospital' : 'Community'}: ${place.name}`;
      element.setAttribute('aria-label', element.title);
      element.style.visibility = 'hidden';
      element.addEventListener('click', event => {
        event.stopPropagation();
        popup?.remove();
        popup = new Popup().setLngLat([place.lon, place.lat])
          .setText(element.title).addTo(map);
      });
      const marker = new Marker({ element, anchor: 'left', offset: [12, 0] })
        .setLngLat([place.lon, place.lat]).addTo(map);
      return { place, element, marker };
    });
    let frame;
    const layout = () => {
      frame = undefined;
      const width = map.getContainer().clientWidth;
      const height = map.getContainer().clientHeight;
      const occupied = [];
      for (const { place, element, marker } of labels) {
        const point = map.project([place.lon, place.lat]);
        const w = element.offsetWidth, h = element.offsetHeight;
        const offset = point.x + 12 + w <= width - 8 ? 12 : -w - 12;
        const rect = { left: point.x + offset, right: point.x + offset + w, top: point.y - h / 2, bottom: point.y + h / 2 };
        const onMap = rect.left >= 8 && rect.right <= width - 8 && rect.top >= 65 && rect.bottom <= height - 30;
        const collision = occupied.some(r => rect.left < r.right + 7 && rect.right + 7 > r.left && rect.top < r.bottom + 7 && rect.bottom + 7 > r.top);
        const show = onMap && !collision;
        element.style.visibility = show ? 'visible' : 'hidden';
        marker.setOffset([offset, 0]);
        if (show) occupied.push(rect);
      }
    };
    const schedule = () => { if (frame === undefined) frame = requestAnimationFrame(layout); };
    map.on('move', schedule);
    map.on('resize', schedule);
    schedule();
    return () => {
      if (frame !== undefined) cancelAnimationFrame(frame);
      map.off('move', schedule);
      map.off('resize', schedule);
      popup?.remove();
      labels.forEach(({ marker }) => marker.remove());
    };
  }, [mapRef, ready, network, visible]);
}

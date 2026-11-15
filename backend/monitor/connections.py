"""Real OSM topology and sampled overlap with locally derived NISAR water rasters.

No synthetic fallback. A water overlap is a review candidate, never a closure.
"""
import hashlib
import json
import math
import threading
import time
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone

import httpx
import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.warp import transform_bounds, transform_geom
from rasterio.features import shapes
from shapely.geometry import LineString

from .settings import ROOT, USER_AGENT

DATES = ['20260716', '20260821', '20260902', '20260914', '20260926', '20261008', '20261020']
ENDPOINTS = ['https://overpass-api.de/api/interpreter', 'https://overpass.kumi.systems/api/interpreter']
CACHE = ROOT / 'data' / 'connections'
FETCH_LOCK = threading.Lock()


def sources():
    result = []
    for date in DATES:
        path = ROOT / 'outputs/ml' / f'{date}_surface_water.tif'
        if path.is_file():
            with rasterio.open(path) as ds:
                result.append({'date': date, 'bounds': list(transform_bounds(ds.crs, 'EPSG:4326', *ds.bounds))})
    return {'dates': result, 'model': 'Earlier three-feature Random Forest; exploratory water predictions. No road-disruption validation.', 'region': 'Lake Inba / Chiba, Japan'}


def parse_osm_xml(content):
    root = ET.fromstring(content)
    elements, nodes, ways = [], {}, {}
    for item in root.findall('node'):
        node = {'type': 'node', 'id': int(item.attrib['id']), 'lon': float(item.attrib['lon']), 'lat': float(item.attrib['lat']), 'tags': {t.attrib['k']: t.attrib['v'] for t in item.findall('tag')}}
        nodes[node['id']] = {'lon': node['lon'], 'lat': node['lat']}
        elements.append(node)
    for item in root.findall('way'):
        refs = [int(n.attrib['ref']) for n in item.findall('nd')]
        way = {'type': 'way', 'id': int(item.attrib['id']), 'nodes': refs, 'geometry': [nodes.get(n) for n in refs], 'tags': {t.attrib['k']: t.attrib['v'] for t in item.findall('tag')}}
        ways[way['id']] = way
        elements.append(way)
    for item in root.findall('relation'):
        tags = {t.attrib['k']: t.attrib['v'] for t in item.findall('tag')}
        if tags.get('amenity') == 'hospital':
            members = [{'geometry': ways[int(m.attrib['ref'])]['geometry']} for m in item.findall('member') if m.attrib['type'] == 'way' and int(m.attrib['ref']) in ways]
            elements.append({'type': 'relation', 'id': int(item.attrib['id']), 'members': members, 'tags': tags})
    return {'elements': elements}


def fetch_osm(bounds):
    west, south, east, north = bounds
    box = f'{south},{west},{north},{east}'
    query = f'''[out:json][timeout:35][maxsize:16777216];(
way["highway"~"^(motorway|trunk|primary|secondary|tertiary|unclassified|residential|living_street|service)(_link)?$"]({box});
nwr["amenity"="hospital"]({box});
node["place"~"^(city|town|village|hamlet|suburb|neighbourhood)$"]({box});
);out geom;'''
    key = hashlib.sha256(query.encode()).hexdigest()
    path = CACHE / f'osm-{key}.json'
    with FETCH_LOCK:
        if path.is_file() and time.time() - path.stat().st_mtime < 86400:
            return json.loads(path.read_text())
        failures = []
        # Official map API is appropriate for a bounded, user-triggered small extract.
        endpoints = ['https://api.openstreetmap.org/api/0.6/map'] + ENDPOINTS
        for endpoint in endpoints:
            try:
                with httpx.Client(timeout=45, headers={'User-Agent': USER_AGENT}) as client:
                    with client.stream('GET' if endpoint.endswith('/map') else 'POST', endpoint, **({'params': {'bbox': ','.join(map(str, bounds))}} if endpoint.endswith('/map') else {'data': query})) as response:
                        response.raise_for_status()
                        chunks, size = [], 0
                        for chunk in response.iter_bytes():
                            size += len(chunk)
                            if size > 16 * 1024 * 1024:
                                raise ValueError('Road data exceeded 16 MB. Choose a smaller radius.')
                            chunks.append(chunk)
                payload = parse_osm_xml(b''.join(chunks)) if endpoint.endswith('/map') else json.loads(b''.join(chunks))
                if payload.get('remark') or not isinstance(payload.get('elements'), list):
                    raise ValueError('Road provider returned incomplete data. Try a smaller area or try later.')
                result = {'payload': payload, 'fetched_at': datetime.now(timezone.utc).isoformat(), 'endpoint': endpoint}
                CACHE.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(result))
                return result
            except (httpx.HTTPError, json.JSONDecodeError, ET.ParseError) as exc:
                failures.append(type(exc).__name__)
        raise ValueError('OpenStreetMap providers are unavailable (' + ', '.join(failures) + '). No substitute roads were generated. Retry later.')


class WaterEvidence:
    def __init__(self, before, after):
        if before not in DATES or after not in DATES or before >= after:
            raise ValueError('Choose two available radar dates in chronological order.')
        self.before, self.after = before, after
        self.datasets = []
        for date in [before, after]:
            path = ROOT / 'outputs/ml' / f'{date}_surface_water.tif'
            if not path.is_file():
                raise ValueError('Selected real water raster is unavailable on this computer.')
            with rasterio.open(path) as ds:
                self.datasets.append((ds.read(1), ds.transform, Transformer.from_crs(4326, ds.crs, always_xy=True)))
                self.crs = ds.crs
        self.fingerprints = {date: hashlib.sha256((ROOT / 'outputs/ml' / f'{date}_surface_water.tif').read_bytes()).hexdigest() for date in [before, after]}
        self.history_datasets = []
        for date in DATES:
            path = ROOT / 'outputs/ml' / f'{date}_surface_water.tif'
            if path.is_file():
                with rasterio.open(path) as ds:
                    self.history_datasets.append((date, ds.read(1), ds.transform, Transformer.from_crs(4326, ds.crs, always_xy=True)))

    def history(self, coords):
        result = []
        for date, data, transform, project in self.history_datasets:
            x, y = project.transform(*np.array(coords).T)
            cols, rows = (~transform) * (np.asarray(x), np.asarray(y))
            cols, rows = np.floor(cols).astype(int), np.floor(rows).astype(int)
            inside = (rows >= 0) & (cols >= 0) & (rows < data.shape[0]) & (cols < data.shape[1])
            values = np.full(len(coords), 255, dtype=np.uint8)
            values[inside] = data[rows[inside], cols[inside]]
            valid = np.isin(values, [0, 1])
            result.append({'date': date, 'coverage': round(float(valid.mean()) * 100, 1), 'water_percent': round(float((values[valid] == 1).mean()) * 100, 1) if valid.any() else None})
        return result


    def overlay(self):
        old, transform, _ = self.datasets[0]
        new, transform2, _ = self.datasets[1]
        if old.shape != new.shape or transform != transform2:
            raise ValueError('Water grids do not align; comparison stopped.')
        valid = np.isin(old, [0, 1]) & np.isin(new, [0, 1])
        classes = np.zeros(old.shape, dtype='uint8')
        classes[valid & (old == 1) & (new == 1)] = 1
        classes[valid & (old == 0) & (new == 1)] = 2
        classes[valid & (old == 1) & (new == 0)] = 3
        return {'type': 'FeatureCollection', 'features': [
            {'type': 'Feature', 'geometry': transform_geom(self.crs, 'EPSG:4326', geom), 'properties': {'class': int(value)}}
            for geom, value in shapes(classes, mask=classes > 0, transform=transform)
        ]}

    def sample(self, coords):
        values = []
        for data, transform, project in self.datasets:
            x, y = project.transform(*np.array(coords).T)
            cols, rows = (~transform) * (np.asarray(x), np.asarray(y))
            cols, rows = np.floor(cols).astype(int), np.floor(rows).astype(int)
            inside = (rows >= 0) & (cols >= 0) & (rows < data.shape[0]) & (cols < data.shape[1])
            arr = np.full(len(coords), 255, dtype=np.uint8)
            arr[inside] = data[rows[inside], cols[inside]]
            values.append(arr)
        old, new = values
        valid = np.isin(old, [0, 1]) & np.isin(new, [0, 1])
        return {'samples': len(coords), 'valid': int(valid.sum()), 'new_water': int((valid & (old == 0) & (new == 1)).sum()), 'persistent_water': int((valid & (old == 1) & (new == 1)).sum()), 'receded_water': int((valid & (old == 1) & (new == 0)).sum()), 'coverage': round(float(valid.mean()) * 100, 1)}


def build_network(payload, bounds, water):
    west, south, east, north = bounds
    center_lon, center_lat = (west + east) / 2, (south + north) / 2
    zone = int((center_lon + 180) // 6) + 1
    epsg = (32600 if center_lat >= 0 else 32700) + min(zone, 60)
    project = Transformer.from_crs(4326, epsg, always_xy=True)
    inverse = Transformer.from_crs(epsg, 4326, always_xy=True)
    def inside(c): return west <= c[0] <= east and south <= c[1] <= north
    ways, locations, visits, places = [], {}, Counter(), []
    for element in payload['elements']:
        tags = element.get('tags', {})
        if element['type'] == 'way' and tags.get('highway') in {'motorway', 'trunk', 'primary', 'secondary', 'tertiary', 'unclassified', 'residential', 'living_street', 'service', 'motorway_link', 'trunk_link', 'primary_link', 'secondary_link', 'tertiary_link'}:
            access = tags.get('motorcar', tags.get('motor_vehicle', tags.get('vehicle', tags.get('access', 'yes'))))
            if access in ['no', 'private', 'agricultural', 'forestry', 'delivery']:
                continue
            points = [(str(n), (g['lon'], g['lat'])) for n, g in zip(element.get('nodes', []), element.get('geometry', [])) if g and 'lon' in g]
            # Keep only contiguous in-bound portions; never join across clipped gaps.
            part = []
            for node_id, coord in points + [(None, (999, 999))]:
                if inside(coord):
                    part.append((node_id, coord)); locations[node_id] = coord
                else:
                    if len(part) > 1:
                        ways.append((element, part)); visits.update(set(n for n, _ in part))
                    part = []
        if tags.get('amenity') == 'hospital' or tags.get('place') in {'city', 'town', 'village', 'hamlet', 'suburb', 'neighbourhood'}:
            coord = None
            if 'lon' in element: coord = (element['lon'], element['lat'])
            else:
                geometry = element.get('geometry', []) or [g for m in element.get('members', []) for g in m.get('geometry', [])]
                points = [(g['lon'], g['lat']) for g in geometry if g and 'lon' in g]
                if points: coord = tuple(np.mean(points, axis=0))
            if coord and inside(coord):
                places.append((element, coord))
    if not ways:
        raise ValueError('No supported public motor roads were returned for this area. Choose another center or radius.')
    locations = {n: c for _, part in ways for n, c in part}
    cuts = {n for n, count in visits.items() if count > 1}
    cuts.update(n for _, part in ways for n, _ in [part[0], part[-1]])
    ids = list(locations)
    xy = np.array([project.transform(*locations[n]) for n in ids])
    attachments = []
    for element, coord in places:
        distance = np.linalg.norm(xy - project.transform(*coord), axis=1)
        index = int(np.argmin(distance)); nearest = ids[index]
        # This is a disclosed proximity attachment, not a verified driveway.
        target = nearest if distance[index] <= 250 else None
        if target: cuts.add(target)
        attachments.append((element, coord, target, float(distance[index])))
    nodes, edges = {}, []
    def add_node(key, coord, name='Road junction', kind='junction'):
        nodes[key] = {'id': key, 'name': name, 'type': kind, 'lon': coord[0], 'lat': coord[1], 'x': 5 + 90 * (coord[0]-west)/(east-west), 'y': 10 + 80 * (north-coord[1])/(north-south)}
    for element, part in ways:
        start = 0
        for index in range(1, len(part)):
            if part[index][0] not in cuts: continue
            portion = part[start:index+1]; start = index
            if portion[0][0] == portion[-1][0]: continue
            coords = [c for _, c in portion]
            line = LineString([project.transform(*c) for c in coords])
            if line.length == 0: continue
            sample_count = max(2, math.ceil(line.length / 10) + 1)
            sampled = [inverse.transform(*line.interpolate(float(d)).coords[0]) for d in np.linspace(0, line.length, sample_count)]
            evidence = water.sample(sampled)
            tags = element.get('tags', {})
            status = 'unknown' if evidence['new_water'] else ('unassessed' if evidence['coverage'] < 100 else 'mapped')
            a, b = 'osm-' + portion[0][0], 'osm-' + portion[-1][0]
            add_node(a, coords[0]); add_node(b, coords[-1])
            one_way = tags.get('oneway', 'yes' if tags.get('junction') == 'roundabout' else 'no')
            if one_way == '-1': a, b = b, a; coords = list(reversed(coords))
            bridge = tags.get('bridge', 'no') != 'no'
            edges.append({'id': f'way-{element["id"]}-{index}', 'name': tags.get('name:en', tags.get('name', tags.get('ref', tags['highway'] + ' road'))), 'from': a, 'to': b, 'directed': one_way in ['yes', '1', 'true', '-1'], 'status': status, 'geometry': coords, 'length_m': round(line.length), 'bridge': bridge, 'osm_url': f'https://www.openstreetmap.org/way/{element["id"]}', 'evidence': evidence, 'source_status': status, 'water_history': water.history(sampled) if hasattr(water, 'history') else []})
    if len(edges) > 8000:
        raise ValueError('More than 8,000 road segments were found. Reduce the radius; the graph was not truncated.')
    for element, coord, target, distance in attachments:
        tags = element.get('tags', {}); key = f'place-{element["type"]}-{element["id"]}'
        kind = 'hospital' if tags.get('amenity') == 'hospital' else 'settlement'
        add_node(key, coord, tags.get('name:en', tags.get('name', f'Unnamed {kind}')), kind)
        nodes[key].update(osm_url=f'https://www.openstreetmap.org/{element["type"]}/{element["id"]}', attachment_m=round(distance) if target else None)
        if target:
            edges.append({'id': 'attach-' + key, 'name': 'Unverified facility/place attachment', 'from': key, 'to': 'osm-' + target, 'status': 'mapped', 'geometry': [coord, locations[target]], 'virtual': True, 'length_m': round(distance), 'evidence': {'coverage': 0}, 'source_status': 'mapped'})
    return {'nodes': list(nodes.values()), 'edges': edges}


def analyze(latitude, longitude, radius_km, before, after):
    dy = radius_km / 111.32; dx = dy / math.cos(math.radians(latitude))
    bounds = [longitude-dx, latitude-dy, longitude+dx, latitude+dy]
    if bounds[0] < -180 or bounds[2] > 180: raise ValueError('Areas crossing the antimeridian are not supported.')
    water = WaterEvidence(before, after)
    fetched = fetch_osm(bounds)
    network = build_network(fetched['payload'], bounds, water)
    network.update(request={'latitude': latitude, 'longitude': longitude, 'radius_km': radius_km}, water=water.overlay(), name='Real road access assessment', kind='observed', bounds=bounds, before=before, after=after, observedAt=after, source='OpenStreetMap contributors (ODbL) + local NISAR-derived exploratory water predictions', fetched_at=fetched['fetched_at'], osm_timestamp=fetched['payload'].get('osm3s', {}).get('timestamp_osm_base'), raster_sha256=water.fingerprints, road_count=sum(not e.get('virtual') for e in network['edges']), limitations=['Current OSM roads are compared with historical radar dates, not a historical road snapshot.', 'No detected new water is not a reported-open road. Coverage gaps remain unassessed.', 'Bridge deck height, culverts, tunnels and 20 m raster alignment require local review.', 'Places and hospitals attach to the nearest mapped road node within 250 m; these links are not verified entrances.', 'Bounded graph, incomplete OSM data, turn restrictions and facility availability can change access.', 'The earlier radar-only model is exploratory; the 0.937 validation score does not apply to this analysis.'])
    return network

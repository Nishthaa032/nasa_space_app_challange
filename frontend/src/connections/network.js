// Connectivity describes only this supplied graph, never road safety or travel time.
export const DEMO = {
  name: 'Riverbend basin', kind: 'demonstration',
  source: 'Fictional network for exploring the verification workflow. No satellite observations.',
  observedAt: null,
  nodes: [
    { id: 'hospital', name: 'District hospital', type: 'hospital', x: 16, y: 48 },
    { id: 'junction', name: 'West junction', type: 'junction', x: 33, y: 48 },
    { id: 'east', name: 'East junction', type: 'junction', x: 60, y: 48 },
    { id: 'north', name: 'Northbank', type: 'settlement', x: 66, y: 18 },
    { id: 'orchard', name: 'Orchard', type: 'settlement', x: 84, y: 34 },
    { id: 'meadow', name: 'Meadow', type: 'settlement', x: 85, y: 68 },
    { id: 'south', name: 'Southbank', type: 'settlement', x: 62, y: 81 },
    { id: 'hill', name: 'Hillcrest', type: 'settlement', x: 27, y: 20 },
  ],
  edges: [
    { id: 'west', name: 'Hospital approach', from: 'hospital', to: 'junction', status: 'open', evidence: 'Assumed open in this fictional scenario.' },
    { id: 'bridge', name: 'River bridge approach', from: 'junction', to: 'east', status: 'unknown', evidence: 'Simulated water overlap at the bridge approach. Its condition is unknown.' },
    { id: 'north-road', name: 'Northbank road', from: 'east', to: 'north', status: 'unknown', evidence: 'Simulated water overlap on the northern access road.' },
    { id: 'orchard-road', name: 'Orchard link', from: 'east', to: 'orchard', status: 'open', evidence: 'Assumed open in this fictional scenario.' },
    { id: 'meadow-road', name: 'Meadow link', from: 'east', to: 'meadow', status: 'open', evidence: 'Assumed open in this fictional scenario.' },
    { id: 'south-road', name: 'Southbank causeway', from: 'east', to: 'south', status: 'unknown', evidence: 'Simulated water overlap on the southern causeway.' },
    { id: 'hill-road', name: 'Hillcrest road', from: 'junction', to: 'hill', status: 'open', evidence: 'Assumed open in this fictional scenario.' },
  ],
};

export function validateNetwork(value) {
  if (!value || typeof value.name !== 'string' || !value.name.trim() || value.name.length > 120) throw Error('Provide a network name (1–120 characters).');
  if (!Array.isArray(value.nodes) || value.nodes.length < 2 || value.nodes.length > 200 || !Array.isArray(value.edges) || value.edges.length > 400) throw Error('Use 2–200 nodes and no more than 400 edges.');
  const ids = new Set();
  const nodes = value.nodes.map(n => {
    if (!n || typeof n.id !== 'string' || !n.id || ids.has(n.id) || typeof n.name !== 'string' || !n.name || !['hospital', 'settlement', 'junction'].includes(n.type) || !Number.isFinite(n.x) || !Number.isFinite(n.y) || n.x < 5 || n.x > 95 || n.y < 10 || n.y > 90) throw Error('Nodes need unique IDs, names, valid types, and diagram coordinates x: 5–95, y: 10–90.');
    ids.add(n.id); return { id: n.id, name: n.name.slice(0, 120), type: n.type, x: n.x, y: n.y };
  });
  if (!nodes.some(n => n.type === 'hospital') || !nodes.some(n => n.type === 'settlement')) throw Error('Include at least one hospital and one settlement.');
  const edgeIds = new Set();
  const edges = value.edges.map(e => {
    if (!e || typeof e.id !== 'string' || !e.id || edgeIds.has(e.id) || typeof e.name !== 'string' || !e.name || !ids.has(e.from) || !ids.has(e.to) || e.from === e.to || !['open', 'closed', 'unknown'].includes(e.status)) throw Error('Edges need unique IDs, names, existing endpoints and an open, closed or unknown status.');
    edgeIds.add(e.id); return { id: e.id, name: e.name.slice(0, 120), from: e.from, to: e.to, status: e.status, evidence: typeof e.evidence === 'string' ? e.evidence.slice(0, 2000) : 'No evidence supplied.' };
  });
  if (typeof value.source !== 'string' || !value.source.trim()) throw Error('Include a source describing where the network and statuses came from.');
  if (value.observedAt != null && (typeof value.observedAt !== 'string' || !Number.isFinite(Date.parse(value.observedAt)))) throw Error('observedAt must be a date string or null.');
  return { name: value.name, kind: value.kind === 'demonstration' ? 'demonstration' : 'imported', source: value.source.slice(0, 2000), observedAt: value.observedAt || null, nodes, edges };
}

export function reachable(network, reviews = {}, unknownOpen = true, override = {}) {
  const seen = new Set(network.nodes.filter(n => n.type === 'hospital').map(n => n.id));
  const adjacency = new Map(network.nodes.map(n => [n.id, []]));
  for (const edge of network.edges) {
    const status = (Object.hasOwn(override, edge.id) ? override[edge.id] : null) ?? (Object.hasOwn(reviews, edge.id) ? reviews[edge.id]?.status : null) ?? edge.status;
    if (status === 'closed' || (['unknown', 'unassessed'].includes(status) && !unknownOpen)) continue;
    adjacency.get(edge.to).push(edge.from); if (!edge.directed) adjacency.get(edge.from).push(edge.to);
  }
  const queue = [...seen];
  for (let i = 0; i < queue.length; i++) for (const id of adjacency.get(queue[i])) if (!seen.has(id)) { seen.add(id); queue.push(id); }
  return seen;
}

export function analyzeNetwork(network, reviews = {}) {
  const possible = reachable(network, reviews, true);
  const supported = reachable(network, reviews, false);
  const settlements = network.nodes.filter(n => n.type === 'settlement').map(n => ({ ...n, access: supported.has(n.id) ? 'connected' : possible.has(n.id) ? 'uncertain' : 'disconnected' }));
  const ranked = network.edges.filter(e => (reviews[e.id]?.status ?? e.status) === 'unknown').map(edge => {
    const open = reachable(network, reviews, true, { [edge.id]: 'open' });
    const closed = reachable(network, reviews, true, { [edge.id]: 'closed' });
    const affected = settlements.filter(n => open.has(n.id) && !closed.has(n.id));
    return { ...edge, affected, score: affected.length };
  }).sort((a, b) => b.score - a.score || (b.evidence?.new_water || 0) - (a.evidence?.new_water || 0) || a.name.localeCompare(b.name));
  return { settlements, ranked };
}

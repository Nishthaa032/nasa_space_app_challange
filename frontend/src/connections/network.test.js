import test from 'node:test';
import assert from 'node:assert/strict';
import { DEMO, analyzeNetwork, validateNetwork } from './network.js';
test('bridge is the highest-value check and opening it reduces uncertainty', () => {
  const before = analyzeNetwork(DEMO);
  assert.equal(before.ranked[0].id, 'bridge');
  assert.equal(before.ranked[0].score, 4);
  assert.equal(before.settlements.filter(n => n.access === 'uncertain').length, 4);
  const after = analyzeNetwork(DEMO, { bridge: { status: 'open' } });
  assert.equal(after.settlements.filter(n => n.access === 'uncertain').length, 2);
});
test('closed bridge disconnects east bank but not Hillcrest', () => {
  const result = analyzeNetwork(DEMO, { bridge: { status: 'closed' } });
  assert.equal(result.settlements.filter(n => n.access === 'disconnected').length, 4);
  assert.equal(result.settlements.find(n => n.id === 'hill').access, 'connected');
});
test('alternative route removes single-bridge dependency', () => {
  const network = { ...DEMO, edges: [...DEMO.edges, { id: 'bypass', from: 'junction', to: 'east', status: 'open', name: 'Bypass' }] };
  assert.equal(analyzeNetwork(network).ranked.find(e => e.id === 'bridge').score, 0);
});
test('multiple hospitals provide independent access', () => {
  const network = { ...DEMO, nodes: DEMO.nodes.map(n => n.id === 'east' ? { ...n, type: 'hospital' } : n) };
  assert.equal(analyzeNetwork(network, { bridge: { status: 'closed' } }).settlements.filter(n => n.access === 'disconnected').length, 0);
});
test('reject malformed imported networks; accept demonstration template', () => {
  assert.equal(validateNetwork(DEMO).nodes.length, 8);
  assert.throws(() => validateNetwork({ ...DEMO, edges: [{ ...DEMO.edges[0], to: 'missing' }] }));
  assert.throws(() => validateNetwork({ ...DEMO, nodes: [...DEMO.nodes, DEMO.nodes[0]] }));
  assert.throws(() => validateNetwork({ ...DEMO, observedAt: 'invalid date' }));
});
test('directed roads assess travel toward hospitals, not away from them', () => {
 const network={nodes:[{id:'h',type:'hospital'},{id:'v',type:'settlement'}],edges:[{id:'e',from:'h',to:'v',status:'mapped',directed:true}]};
 assert.equal(analyzeNetwork(network).settlements[0].access,'disconnected');
 network.edges[0].from='v'; network.edges[0].to='h';
 assert.equal(analyzeNetwork(network).settlements[0].access,'connected');
});
test('missing raster coverage is uncertain, never reported-open access', () => {
 const network={nodes:[{id:'h',type:'hospital'},{id:'v',type:'settlement'}],edges:[{id:'e',name:'Road',from:'v',to:'h',status:'unassessed'}]};
 assert.equal(analyzeNetwork(network).settlements[0].access,'uncertain');
 assert.equal(analyzeNetwork(network).ranked.length,0);
});

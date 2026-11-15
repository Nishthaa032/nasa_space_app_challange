import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Orbit, GitBranch, ArrowUpRight, Download, Upload, RotateCcw, Check, X, HelpCircle, ArrowLeft, MapPin, Hospital, ShieldCheck, Clock3 } from 'lucide-react';
import { DEMO, analyzeNetwork, validateNetwork } from './connections/network.js';
import './connections/connections.css';

const STORAGE = 'sarscope-critical-connections-v1';
const STATUS = { open: 'Reported open', closed: 'Reported closed', unknown: 'Needs verification' };
function initialState() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE));
    if (saved) {
      const network = validateNetwork(saved.network);
      const reviews = Object.fromEntries(Object.entries(saved.reviews || {}).filter(([id, r]) => network.edges.some(e => e.id === id) && r && ['open', 'closed', 'unknown'].includes(r.status) && typeof r.note === 'string' && typeof r.at === 'string'));
      return { network, reviews, history: Array.isArray(saved.history) ? saved.history.filter(h => h && typeof h.edge === 'string' && typeof h.note === 'string' && typeof h.at === 'string' && STATUS[h.status]).slice(0, 100) : [] };
    }
  } catch { /* Invalid or unavailable local storage starts a fresh demonstration. */ }
  return { network: DEMO, reviews: {}, history: [] };
}
function download(value, filename) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2)], { type: 'application/json' }));
  const a = document.createElement('a'); a.href = url; a.download = filename; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function NetworkMap({ network, reviews, selected, onSelect, settlements }) {
  const nodes = Object.fromEntries(network.nodes.map(n => [n.id, n]));
  const colors = { open: '#65d9b4', closed: '#f78083', unknown: '#f3bd66' };
  return <svg className="cc-network" viewBox="0 0 900 550" role="group" aria-label="Interactive schematic road network; select a road to inspect evidence">
    <defs><pattern id="cc-grid" width="30" height="30" patternUnits="userSpaceOnUse"><path d="M 30 0 L 0 0 0 30" fill="none" stroke="#233b42" strokeWidth=".5" /></pattern><linearGradient id="cc-water" x1="0" x2="1"><stop stopColor="#174a58"/><stop offset="1" stopColor="#102e3d"/></linearGradient></defs>
    <rect width="900" height="550" fill="#0d1c24"/><rect width="900" height="550" fill="url(#cc-grid)"/>
    {network.kind === 'demonstration' && <g aria-hidden="true"><path d="M430 -30 C340 80 500 130 443 230 S340 390 490 580" fill="none" stroke="url(#cc-water)" strokeWidth="65"/><path d="M430 -30 C340 80 500 130 443 230 S340 390 490 580" fill="none" stroke="#387182" strokeWidth="1" strokeDasharray="4 8"/><ellipse cx="435" cy="264" rx="66" ry="43" fill="#dca55018" stroke="#efba6144" strokeDasharray="5 5"/><text x="405" y="450" fill="#6094a4" fontSize="11" transform="rotate(-65 405 450)">ILLUSTRATIVE RIVER</text></g>}
    {network.edges.map(e => {
      const a = nodes[e.from], b = nodes[e.to], status = reviews[e.id]?.status ?? e.status;
      const x1 = a.x * 9, y1 = a.y * 5.5, x2 = b.x * 9, y2 = b.y * 5.5;
      return <g key={e.id} role="button" tabIndex={0} aria-label={`${e.name}, ${STATUS[status]}`} aria-pressed={selected === e.id} onClick={() => onSelect(e.id)} onKeyDown={event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); onSelect(e.id); } }} className="cc-road">
        <title>{e.name} — {STATUS[status]}</title>
        <line x1={x1} y1={y1} x2={x2} y2={y2} stroke={selected === e.id ? '#fff' : '#1d343d'} strokeWidth={selected === e.id ? 10 : 9} opacity={selected === e.id ? .22 : 1}/>
        <line x1={x1} y1={y1} x2={x2} y2={y2} stroke={colors[status]} strokeWidth="3" strokeDasharray={status === 'unknown' ? '8 6' : undefined}/>
        <line x1={x1} y1={y1} x2={x2} y2={y2} stroke="transparent" strokeWidth="22"/>
        {status !== 'open' && <><circle cx={(x1+x2)/2} cy={(y1+y2)/2} r="11" fill="#14232b" stroke={colors[status]}/><text x={(x1+x2)/2} y={(y1+y2)/2+4} textAnchor="middle" fill={colors[status]} fontSize="13">{status === 'unknown' ? '?' : '×'}</text></>}
      </g>;
    })}
    {network.nodes.map(n => {
      const access = settlements.find(s => s.id === n.id)?.access;
      const color = n.type === 'hospital' ? '#b5c9ff' : access === 'disconnected' ? '#f78083' : access === 'uncertain' ? '#f3bd66' : '#65d9b4';
      return <g key={n.id} pointerEvents="none"><circle cx={n.x*9} cy={n.y*5.5} r={n.type === 'junction' ? 5 : 10} fill="#0d1c24" stroke={color} strokeWidth="2"/>{n.type === 'hospital' && <text x={n.x*9} y={n.y*5.5+5} fill={color} textAnchor="middle" fontSize="17">+</text>}<text x={n.x*9} y={n.y*5.5-19} fill="#dce8ed" fontSize="12" textAnchor="middle">{n.name}</text></g>;
    })}
    <text x="22" y="526" fill="#7e9ba8" fontSize="10" letterSpacing="1">SCHEMATIC NETWORK · NOT TO SCALE · NOT A NAVIGATION MAP</text>
  </svg>;
}

export default function CriticalConnections({ onBack, onDomainChange }) {
  const [state, setState] = useState(initialState);
  const { network, reviews, history } = state;
  const [selected, setSelected] = useState(() => state.network.edges.find(e => e.status === 'unknown')?.id || state.network.edges[0]?.id);
  const [note, setNote] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [tab, setTab] = useState('queue');
  const [resetting, setResetting] = useState(false);
  const fileInput = useRef(null);
  const analysis = useMemo(() => analyzeNetwork(network, reviews), [network, reviews]);
  const edge = network.edges.find(e => e.id === selected);
  const rankedEdge = analysis.ranked.find(e => e.id === selected);
  const demo = network.kind === 'demonstration';
  const count = type => analysis.settlements.filter(n => n.access === type).length;
  useEffect(() => {
    try { localStorage.setItem(STORAGE, JSON.stringify(state)); }
    catch { setError('Browser storage is unavailable or full. Export your assessment to keep a copy.'); }
  }, [state]);
  function select(id) { setSelected(id); setNote(''); setMessage(''); }
  function verify(status) {
    if (!edge || !note.trim()) { setError('Add an observation or source note before saving a status.'); return; }
    const entry = { edge: edge.id, name: edge.name, status, note: note.trim(), at: new Date().toISOString() };
    setState(s => ({ ...s, reviews: { ...s.reviews, [edge.id]: entry }, history: [entry, ...s.history].slice(0, 100) }));
    setMessage(`${edge.name}: ${STATUS[status].toLowerCase()}. Connectivity updated.`); setError(''); setNote('');
  }
  async function importNetwork(event) {
    const file = event.target.files?.[0]; event.target.value = ''; if (!file) return;
    try {
      if (file.size > 1024 * 1024) throw Error('Choose a JSON network smaller than 1 MB.');
      const next = validateNetwork(JSON.parse(await file.text()));
      setState({ network: next, reviews: {}, history: [] }); select(next.edges[0]?.id); setError(''); setMessage('Network imported. Source claims are supplied by the file and have not been independently verified.');
    } catch (err) { setError(`Import failed: ${err.message}`); }
  }
  const nav = [['water', 'Water & Floods'], ['moisture', 'Soil Moisture'], ['vegetation', 'Forests & Canopy'], ['agriculture', 'Agriculture'], ['subsidence', 'Land Subsidence']];
  return <div className="cc-app">
    <header className="cc-header"><button className="brand" onClick={onBack}><span className="brand-icon"><Orbit size={25}/></span>SAR<span>Scope</span><i>BETA</i></button><nav className="main-nav-tabs" aria-label="Earth observation workspaces"><button onClick={onBack}>Workspace</button>{nav.map(([key, label]) => <button key={key} onClick={() => onDomainChange(key)}>{label}</button>)}<button className="nav-active" aria-current="page">Critical Connections <GitBranch size={14}/></button></nav></header>
    <main className="cc-main">
      <div className="cc-heading"><div><div className="cc-eyebrow"><span/> ACCESS INTELLIGENCE / VERIFICATION WORKSPACE</div><h1>Find the connection<br/><em>that changes everything.</em></h1><p>Understand potential isolation. Prioritize the next check. Keep the evidence.</p></div><div className="cc-actions"><button onClick={() => fileInput.current.click()}><Upload size={15}/> Import network</button><button className="cc-primary" onClick={() => download({ ...state, assessment: analysis, exportedAt: new Date().toISOString(), method: 'Undirected connectivity to any hospital; no travel times or capacity. Priority counts settlements losing possible access when a single uncertain edge closes while other uncertain edges remain open.', limitation: 'User-supplied network and status reports. Connectivity is not verified road safety. Demonstration data are fictional.' }, 'sarscope-connection-assessment.json')}><Download size={15}/> Export assessment</button><input ref={fileInput} type="file" accept=".json,application/json" hidden onChange={importNetwork}/></div></div>
      <div className="cc-banner"><ShieldCheck size={19}/><div><strong>{demo ? 'Demonstration mode · fictional network' : 'Imported network · source not independently verified'}</strong><span>{demo ? 'Explore the workflow with sample roads and communities. These are not live flood or rescue findings.' : 'Assessments use your supplied roads and statuses. Satellite ingestion and road–water intersection are not connected to this page.'}</span></div><span className="cc-local">SAVED ON THIS BROWSER</span></div>
      {(error || message) && <div className={`cc-message ${error ? 'cc-error' : ''}`} role={error ? 'alert' : 'status'}>{error || message}<button aria-label="Dismiss message" onClick={() => {setError(''); setMessage('');}}><X size={16}/></button></div>}
      <section className="cc-metrics" aria-label="Network assessment"><div><span>COMMUNITIES IN NETWORK</span><strong>{analysis.settlements.length}<small>toward {network.nodes.filter(n => n.type === 'hospital').length} hospital destination(s)</small></strong></div><div className="cc-amber"><span>UNCERTAIN ACCESS</span><strong>{count('uncertain')}<small>depend on unverified connections</small></strong></div><div className="cc-red"><span>NO MAPPED CONNECTION</span><strong>{count('disconnected')}<small>even if unknown roads are open</small></strong></div><div className="cc-green"><span>CONNECTED IN THIS NETWORK</span><strong>{count('connected')}<small>using reported-open roads</small></strong></div></section>
      <div className="cc-workbench">
        <section className="cc-queue cc-panel"><div className="cc-panel-heading"><div><span className="cc-eyebrow">01 / PRIORITIZE</span><h2>What to check next</h2></div><span className="cc-count">{analysis.ranked.length}</span></div><div className="cc-tabs"><button className={tab === 'queue' ? 'active' : ''} onClick={() => setTab('queue')}>Verification queue</button><button className={tab === 'all' ? 'active' : ''} onClick={() => setTab('all')}>All roads</button></div><div className="cc-road-list">{(tab === 'queue' ? analysis.ranked : network.edges).map((e, i) => <button key={e.id} className={`cc-road-card ${selected === e.id ? 'selected' : ''}`} onClick={() => select(e.id)}><span className="cc-rank">{String(i+1).padStart(2, '0')}</span><div><strong>{e.name}</strong><span>{tab === 'queue' ? `${e.score} ${e.score === 1 ? 'community depends' : 'communities depend'} on this link` : STATUS[reviews[e.id]?.status ?? e.status]}</span></div><ArrowUpRight size={16}/></button>)}{tab === 'queue' && !analysis.ranked.length && <div className="cc-empty"><Check size={24}/><h3>Queue complete</h3><p>All roads have a reported status. Review or reopen a check under All roads.</p></div>}</div><div className="cc-method"><HelpCircle size={15}/><p>Ranked by communities that lose possible hospital access if this link closes, assuming other unknown links are open. Scores are not probabilities and should not be added.</p></div></section>
        <section className="cc-map-panel cc-panel"><div className="cc-panel-heading"><div><span className="cc-eyebrow">02 / UNDERSTAND</span><h2>{network.name}</h2></div><span className="cc-map-badge"><MapPin size={12}/> NETWORK VIEW</span></div><NetworkMap network={network} reviews={reviews} selected={selected} onSelect={select} settlements={analysis.settlements}/><div className="cc-legend"><span><i className="open"/>Reported open</span><span><i className="unknown"/>Unverified</span><span><i className="closed"/>Reported closed</span><span><Hospital size={13}/>Hospital</span></div><div className="cc-access"><h3>Community access</h3>{analysis.settlements.map(n => <div key={n.id}><span>{n.name}</span><span className={`cc-access-${n.access}`}>{n.access === 'connected' ? 'Connected in graph' : n.access === 'uncertain' ? 'Uncertain' : 'No mapped connection'}</span></div>)}</div></section>
        <section className="cc-evidence cc-panel"><div className="cc-panel-heading"><div><span className="cc-eyebrow">03 / VERIFY</span><h2>Evidence passport</h2></div><ShieldCheck size={20}/></div>{edge ? <div className="cc-evidence-body"><span className={`cc-status cc-status-${reviews[edge.id]?.status ?? edge.status}`}>{STATUS[reviews[edge.id]?.status ?? edge.status]}</span><h3>{edge.name}</h3><p className="cc-endpoints">{network.nodes.find(n => n.id === edge.from)?.name} <span>↔</span> {network.nodes.find(n => n.id === edge.to)?.name}</p>{rankedEdge && <div className="cc-impact"><strong>{rankedEdge.score}</strong><div>communities depend on this link<small>{rankedEdge.affected.map(n => n.name).join(', ') || 'No single-link dependency; alternatives may still be uncertain.'}</small></div></div>}<dl><dt>SUPPLIED EVIDENCE</dt><dd>{edge.evidence}</dd><dt>NETWORK SOURCE</dt><dd>{network.source}</dd><dt>OBSERVATION TIME</dt><dd>{network.observedAt ? new Date(network.observedAt).toLocaleString() : 'Not supplied — no acquisition claimed'}</dd>{reviews[edge.id] && <><dt>LATEST LOCAL REPORT</dt><dd>{reviews[edge.id].note}<small>{new Date(reviews[edge.id].at).toLocaleString()}</small></dd></>}</dl><label htmlFor="cc-note">{demo ? 'Try a verification note' : 'Record a verification note'}</label><textarea id="cc-note" value={note} onChange={e => setNote(e.target.value)} maxLength={1000} placeholder={demo ? 'Example: simulated field check found the approach open.' : 'Who checked, when, and what evidence supports the status?'} rows={3}/><div className="cc-verification"><button disabled={!note.trim()} onClick={() => verify('open')}><Check size={14}/>Report open</button><button disabled={!note.trim()} onClick={() => verify('closed')}><X size={14}/>Report closed</button></div><button className="cc-reopen" disabled={!note.trim()} onClick={() => verify('unknown')}><RotateCcw size={12}/> Return to unverified</button><p className="cc-disclaimer">Reports are local user observations, not independently verified. A mapped connection does not establish safe passage.</p></div> : <div className="cc-empty">Select a road, or import a network with road connections.</div>}</section>
      </div>
      <div className="cc-bottom"><section className="cc-panel"><div className="cc-panel-heading"><div><span className="cc-eyebrow">AUDIT TRAIL</span><h2>Every update leaves a trace</h2></div><Clock3 size={18}/></div><div className="cc-history">{history.length ? history.slice(0, 8).map((h, i) => <div key={`${h.at}-${i}`}><span className="cc-history-dot"/><div><strong>{h.name || h.edge} · {STATUS[h.status]}</strong><p>{h.note}</p><time>{new Date(h.at).toLocaleString()}</time></div></div>) : <p>No reports yet. Select a connection and record a check to see the assessment change.</p>}</div></section><section className="cc-panel cc-guide"><span className="cc-eyebrow">BRING YOUR OWN NETWORK</span><h2>Start small. Keep it traceable.</h2><p>Download the sample JSON as a template. Add hospitals, settlements, junctions and road edges with open, closed or unknown statuses. Coordinates position nodes on the schematic, not on Earth.</p><p>Import replaces this browser’s current network and local reports. Export your assessment first to preserve them. Missing roads and unmapped destinations can change the result.</p><div className="cc-guide-actions"><button onClick={() => download(DEMO, 'sarscope-network-template.json')}><Download size={14}/> Download template</button><button onClick={() => setResetting(v => !v)}><RotateCcw size={14}/> Reset demo</button></div>{resetting && <div className="cc-reset">Replace the current network and clear local reports?<button onClick={() => {setState({network: DEMO, reviews: {}, history: []}); select('bridge'); setResetting(false); setError('');}}>Reset now</button><button onClick={() => setResetting(false)}>Cancel</button></div>}</section></div>
      <footer className="cc-footer"><span>SARScope / Critical Connections · Experimental decision support</span><button onClick={onBack}><ArrowLeft size={13}/> Back to workspace</button></footer>
    </main>
  </div>;
}

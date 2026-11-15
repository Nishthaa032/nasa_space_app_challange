import React, {useEffect, useRef, useState} from 'react';
import {Orbit, Radio} from 'lucide-react';
import {readableDate} from './echo/sound';
import {drawFrame} from './echo/draw';
import ExplainerVideo from './echo/ExplainerVideo.jsx';
import './echo/echo.css';

const domains=[['water','Water & Floods'],['moisture','Soil Moisture'],['vegetation','Forests & Canopy'],['agriculture','Agriculture'],['subsidence','Land Subsidence']];
export default function EarthEcho({onBack,onConnections,onDomainChange}){
 const [data,setData]=useState(null),[images,setImages]=useState([]),[error,setError]=useState(''),[regionId,setRegionId]=useState('study'),[index,setIndex]=useState(0),[endpoints,setEndpoints]=useState(false);
 const canvas=useRef(null);
 const region=data?.regions.find(r=>r.id===regionId);
 useEffect(()=>{const controller=new AbortController();let alive=true;
  (async()=>{try{const response=await fetch('/data/echo/manifest.json',{signal:controller.signal});if(!response.ok)throw Error('Could not load the observation archive.');const d=await response.json();const loaded=await Promise.all(d.observations.map(o=>new Promise((resolve,reject)=>{const image=new Image();image.onload=()=>resolve(image);image.onerror=()=>reject(Error('A radar image could not be loaded. Please reload.'));image.src=o.image;})));if(alive){setData(d);setImages(loaded);}}catch(e){if(alive&&e.name!=='AbortError')setError(e.message);}})();
  return()=>{alive=false;controller.abort();};
 },[]);
 useEffect(()=>{drawFrame(canvas.current,data,region,images,index,0,endpoints);},[data,region,images,index,endpoints]);
 const choose=(r)=>{setRegionId(r.id);setIndex(r.peak_index);setEndpoints(false);};
 return <div className="ee-app"><header className="ee-header"><button className="brand" onClick={onBack}><Orbit size={25}/> SAR<span>Scope</span></button><nav className="main-nav-tabs" aria-label="Earth observation workspaces"><button onClick={onBack}>Workspace</button>{domains.map(([id,label])=><button key={id} onClick={()=>onDomainChange(id)}>{label}</button>)}<button onClick={onConnections}>Critical Connections</button><button className="nav-active" aria-current="page">Earth Echo <Radio size={14}/></button></nav></header>
 <main className="ee-main">{error?<div role="alert"><h1>Earth Echo is unavailable</h1><p>{error}</p><button onClick={()=>window.location.reload()}>Retry</button></div>:!data?<p role="status">Loading real radar observations…</p>:<>
 <div className="ee-intro"><div><span className="ee-kicker">LAKE INBA, JAPAN</span><h1>Earth Echo</h1><p>Explore water changes. Turn an observation into a narrated video.</p></div><div className="ee-stats"><div><strong>{data.observations.length}</strong><span>observations</span></div><div><strong>{data.common_coverage_percent}%</strong><span>comparable coverage</span></div></div></div>
 <div className="ee-layout"><section className="ee-player" aria-label="Radar observations"><div className="ee-toolbar"><h2>{region.name}</h2><button aria-pressed={endpoints} onClick={()=>setEndpoints(v=>!v)}>{endpoints?'Show selected date':'Compare first & last'}</button></div>
 <label className="ee-date-select">Observation<select aria-label="Observation date" value={index} onChange={e=>{setEndpoints(false);setIndex(Number(e.target.value));}}>{data.observations.map((o,i)=><option key={o.date} value={i}>{readableDate(o.date)}{o.gap_days?` · ${o.gap_days} days since previous pass`: ' · First observation'}</option>)}</select></label>
 <canvas ref={canvas} width="1280" height="720" role="img" aria-label={endpoints?`${region.name}: first observation ${readableDate(data.observations[0].date)} compared with last observation ${readableDate(data.observations.at(-1).date)}.`:`${region.name}, ${readableDate(region.series[index].date)}, ${region.series[index].water_km2.toFixed(3)} square kilometres of predicted water.`}/>
 <div className="ee-reading" hidden={endpoints}><strong>{region.series[index].water_km2.toFixed(3)} km²</strong><span>predicted water · {readableDate(region.series[index].date)} · {Math.round(region.series[index].water_fraction*100)}% of selected comparable area</span></div>
 <div className="ee-legend" aria-label="Map legend"><span><i style={{background:'#50d8c0'}}/>Predicted water</span><span><i style={{background:'#b390f0'}}/>Temporary-water candidate</span><span><i style={{background:'#87939b'}}/>Radar background</span><span><i style={{background:'#101722'}}/>No data</span></div>
 <ExplainerVideo region={region} index={index}/>
 </section><aside className="ee-aside"><h2>Explore an area</h2><p>Find patches classified as water between two non-water observations.</p><button className={regionId==='study'?'ee-patch selected':'ee-patch'} aria-pressed={regionId==='study'} onClick={()=>choose(data.regions[0])}><strong>Whole study area</strong><span>Lake Inba, Japan</span></button>{data.regions.slice(1).map(r=><button className={`ee-patch ${r.id===regionId?'selected':''}`} aria-pressed={r.id===regionId} key={r.id} onClick={()=>choose(r)}><strong>{r.name}</strong><span>{r.area_km2.toFixed(3)} km²</span></button>)}<p className="ee-note">Exploratory predictions, not confirmed floods. Only pixels available on all dates are compared.</p></aside></div>
 <details className="ee-evidence-details"><summary>Data sources & limitations</summary><p>Measurements do not establish what happened between satellite passes. Grey radar context may include pixels outside the comparable area.</p>{data.limitations.filter(s=>!s.startsWith('Audio')&&!s.includes('Equal playback')).map((s,i)=><p key={i}>{s}</p>)}<a href="/data/echo/manifest.json" download="earth-echo-evidence.json">Download source data</a><div className="ee-sources">{data.observations.map(o=><div key={o.date}><strong>{readableDate(o.date)} · {o.coverage_percent}% valid coverage</strong><a href={o.source?.url} target="_blank" rel="noreferrer">NASA NISAR source observation</a></div>)}</div></details>
 </>}</main></div>;
}

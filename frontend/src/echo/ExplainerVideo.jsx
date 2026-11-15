import React,{useEffect,useRef,useState} from 'react';
import {Film,Download} from 'lucide-react';
export default function ExplainerVideo({region,index,active=false,onStart=()=>{},videoRef}){
 const [busy,setBusy]=useState(false),[error,setError]=useState(''),[url,setUrl]=useState('');
 const pending=useRef(null),asset=useRef(null);
 const ownVideo=useRef(null);
 const video=videoRef||ownVideo;
 const date=region.series[index].date;
 useEffect(()=>{setUrl('');setError('');setBusy(false);return()=>{pending.current?.abort();pending.current=null;if(asset.current)URL.revokeObjectURL(asset.current);asset.current=null;};},[region.id,date]);
 useEffect(()=>{if(active)video.current?.pause();},[active]);
 async function generate(){
  onStart();setBusy(true);setError('');const controller=new AbortController();pending.current=controller;
  try{const response=await fetch('/api/echo/video',{method:'POST',headers:{'Content-Type':'application/json','X-SARScope':'1'},body:JSON.stringify({region_id:region.id,date}),signal:controller.signal});
   if(!response.ok){const body=await response.json().catch(()=>({}));throw Error(body.detail||'Start the local backend and try again.');}
   const blob=await response.blob();if(!blob.size||!blob.type.includes('video/'))throw Error('The server did not return a playable video.');
   if(pending.current!==controller)return;if(asset.current)URL.revokeObjectURL(asset.current);asset.current=URL.createObjectURL(blob);setUrl(asset.current);
  }catch(e){if(e.name!=='AbortError')setError(e.message);}finally{if(pending.current===controller){pending.current=null;setBusy(false);}}
 }
 return <section className="ee-video-explainer" aria-label="Narrated video explanation"><div className="ee-narration-heading"><div><h3>Video explanation</h3></div><button className="ee-primary" disabled={busy||active} onClick={generate}><Film size={17}/>{busy?'Creating narrated video…':'Create explainer video'}</button></div><p>English narration, radar comparisons and captions in one downloadable video.</p><p className="ee-narration-note" role="status">{busy?'Building scenes and recording narration locally. This can take a minute.':error||''}</p>{url&&<><video ref={video} controls playsInline src={url} aria-label={`Narrated explanation of ${region.name}, ${date}`} onPlay={onStart}/><a href={url} download={`earth-echo-${region.id}-${date}-explained.mp4`}><Download size={16}/> Download narrated MP4</a></>}</section>;
}

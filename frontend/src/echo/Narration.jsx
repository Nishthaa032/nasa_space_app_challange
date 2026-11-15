import React,{useEffect,useRef,useState} from 'react';
import ExplainerVideo from './ExplainerVideo.jsx';
import {Volume2,Square} from 'lucide-react';
import {explanation,matchingVoices} from './narration.js';

export default function Narration({data,region,index,active,volume,onStart}){
 const supported=typeof window!=='undefined'&&'speechSynthesis' in window&&'SpeechSynthesisUtterance' in window;
 const [language,setLanguage]=useState('en-IN'),[voices,setVoices]=useState([]),[voiceId,setVoiceId]=useState(''),[speed,setSpeed]=useState(1),[speaking,setSpeaking]=useState(false),[sentence,setSentence]=useState(-1),[message,setMessage]=useState('');
 const session=useRef(0),utterance=useRef(null),videoRef=useRef(null);
 const lines=explanation(data,region,index,language),available=matchingVoices(voices,language);
 const selected=available.find(v=>v.voiceURI===voiceId)||available[0];
 function cancel(update=true){session.current++;if(utterance.current){utterance.current.onend=null;utterance.current.onerror=null;utterance.current.onstart=null;window.speechSynthesis.cancel();utterance.current=null;}if(update){setSpeaking(false);setSentence(-1);}}
 useEffect(()=>{if(!supported)return;const refresh=()=>setVoices(window.speechSynthesis.getVoices());refresh();window.speechSynthesis.addEventListener('voiceschanged',refresh);return()=>{window.speechSynthesis.removeEventListener('voiceschanged',refresh);cancel(false);};},[supported]);
 useEffect(()=>{cancel();setMessage('');},[region.id,index,language,voiceId,speed,active,volume]);
 function speak(){
  cancel();videoRef.current?.pause();setMessage('');if(!supported)return;
  if(!selected&&language.startsWith('hi')){setMessage('A Hindi voice is not available on this device. Install a Hindi system voice or read the Hindi transcript below.');return;}
  onStart();const id=session.current;setSpeaking(true);
  const next=(i)=>{if(id!==session.current)return;if(i===lines.length){utterance.current=null;setSpeaking(false);setSentence(-1);setMessage('Explanation finished.');return;}
   const speech=new SpeechSynthesisUtterance(lines[i]);utterance.current=speech;speech.lang=language;if(selected)speech.voice=selected;speech.rate=speed;speech.volume=volume;
   speech.onstart=()=>{if(id===session.current)setSentence(i);};speech.onend=()=>next(i+1);speech.onerror=event=>{if(id!==session.current)return;cancel();setMessage(event.error==='not-allowed'?'Speech was blocked by your browser. Try Explain this observation again.':'This voice could not play. Try another available voice; the transcript remains available.');};
   window.speechSynthesis.speak(speech);
  };next(0);
 }
 return <><ExplainerVideo videoRef={videoRef} region={region} index={index} active={active} onStart={()=>{cancel();onStart();}}/><details className="ee-audio-details"><summary>Audio-only explanation and transcript</summary><section className="ee-narration" aria-label="Spoken data explanation"><div className="ee-narration-heading"><div><span className="ee-kicker">EXPLAIN THE DATA</span><h3>Your observation, in plain words.</h3></div><button className="ee-primary" disabled={!supported||active} onClick={()=>speaking?cancel():speak()}>{speaking?<Square size={16}/>:<Volume2 size={16}/>} {speaking?'Stop explanation':'Explain this observation'}</button></div>
 <div className="ee-narration-options"><label>Language<select aria-label="Narration language" value={language} onChange={e=>{setVoiceId('');setLanguage(e.target.value);}}><option value="en-IN">English</option><option value="hi-IN">हिन्दी</option></select></label><label>Voice<select aria-label="Narration voice" value={selected?.voiceURI||''} onChange={e=>setVoiceId(e.target.value)} disabled={!available.length}><option value="" disabled>{available.length?'Choose a voice':'Device default / unavailable'}</option>{available.map(v=><option key={v.voiceURI} value={v.voiceURI}>{v.name}{v.localService?' · device voice':''}</option>)}</select></label><label>Speed<select aria-label="Narration speed" value={speed} onChange={e=>setSpeed(Number(e.target.value))}><option value="0.8">Slower</option><option value="1">Normal</option><option value="1.2">Faster</option></select></label></div>
 <p className="ee-narration-note">Uses the volume above. Voices depend on your browser and device; some voices use an online speech service. Narration is separate from the sound-story audio and video downloads.</p>
 <p role="status" className="ee-narration-note">{!supported?'Speech playback is unavailable in this browser. Read the explanation below.':active?'Stop the sound story before starting an explanation.':message||(speaking?'Speaking — the current passage is highlighted.':'Select a date or patch to update the explanation.')}</p>
 <ol className="ee-transcript" lang={language}>{lines.map((line,i)=><li key={i} className={sentence===i?'ee-speaking':''} aria-current={sentence===i?'step':undefined}>{line}</li>)}</ol>
 </section></details></>;
}

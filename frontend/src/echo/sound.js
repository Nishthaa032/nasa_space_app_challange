export const STORY_SECONDS = 20;
export const SAMPLE_RATE = 22050;

// A documented, fixed mapping; no invented environmental variables.
export function soundParameters(row, previous) {
  if (!row || row.water_fraction == null || row.valid_pixels === 0) return null;
  const water = Math.max(0, Math.min(1, row.water_fraction));
  return { frequency: 220 + 440 * water, pulses: 1 + Math.floor(water * 5), accent: previous?.water_fraction != null && water - previous.water_fraction >= .02 };
}

export function renderSamples(series, duration = STORY_SECONDS, sampleRate = SAMPLE_RATE) {
  if (!series.length) throw Error('No observations to sonify.');
  const result = new Float32Array(Math.round(duration * sampleRate));
  const slot = duration / series.length;
  const parameters = series.map((row,i) => soundParameters(row, series[i-1]));
  for (let i=0; i<result.length; i++) {
    const time=i/sampleRate, index=Math.min(series.length-1,Math.floor(time/slot));
    const p=parameters[index]; if(!p)continue;
    const local=time-index*slot, phase=local/slot;
    const pulse=Math.pow(Math.max(0,Math.sin(Math.PI*((phase*p.pulses)%1))),3);
    const fade=Math.min(1,local/.04,(slot-local)/.04);
    let value=.18*pulse*Math.sin(2*Math.PI*p.frequency*local);
    if(p.accent&&local<.16)value+=.08*Math.sin(Math.PI*local/.16)*Math.sin(2*Math.PI*880*local);
    result[i]=value*Math.max(0,fade);
  }
  return result;
}

export function wavBytes(samples, sampleRate = SAMPLE_RATE) {
  const buffer=new ArrayBuffer(44+samples.length*2),view=new DataView(buffer);
  const word=(offset,text)=>[...text].forEach((c,i)=>view.setUint8(offset+i,c.charCodeAt(0)));
  word(0,'RIFF');view.setUint32(4,36+samples.length*2,true);word(8,'WAVE');word(12,'fmt ');
  view.setUint32(16,16,true);view.setUint16(20,1,true);view.setUint16(22,1,true);view.setUint32(24,sampleRate,true);
  view.setUint32(28,sampleRate*2,true);view.setUint16(32,2,true);view.setUint16(34,16,true);word(36,'data');view.setUint32(40,samples.length*2,true);
  samples.forEach((s,i)=>view.setInt16(44+i*2,Math.round(Math.max(-1,Math.min(1,s))*32767),true));
  return buffer;
}
export function readableDate(date) { return `${date.slice(0,4)}-${date.slice(4,6)}-${date.slice(6,8)}`; }
export function captions(dataset, region, duration=STORY_SECONDS) {
  const stamp=seconds=>{const ms=Math.round(seconds*1000);return `${String(Math.floor(ms/3600000)).padStart(2,'0')}:${String(Math.floor(ms/60000)%60).padStart(2,'0')}:${String(Math.floor(ms/1000)%60).padStart(2,'0')},${String(ms%1000).padStart(3,'0')}`;};
  return region.series.map((row,i)=>`${i+1}\n${stamp(i*duration/region.series.length)} --> ${stamp((i+1)*duration/region.series.length)}\n${region.name} | ${readableDate(row.date)} | ${row.water_km2.toFixed(3)} km² water on common valid pixels\nData-generated sound; time compressed. ${dataset.observations[i].gap_days??0} days since prior observation.\n`).join('\n');
}

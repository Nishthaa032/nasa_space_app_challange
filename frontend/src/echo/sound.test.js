import test from 'node:test';
import assert from 'node:assert/strict';
import {soundParameters,renderSamples,wavBytes,captions} from './sound.js';
test('missing observations remain silent, never dry-sounding substitutes',()=>{
 assert.equal(soundParameters({water_fraction:null,valid_pixels:0}),null);
 assert.ok(renderSamples([{water_fraction:null,valid_pixels:0}],1,1000).every(v=>v===0));
});
test('water share controls bounded pitch and pulse counts',()=>{
 assert.deepEqual(soundParameters({water_fraction:1,valid_pixels:10},{water_fraction:0}),{frequency:660,pulses:6,accent:true});
 const data=renderSamples([{water_fraction:1,valid_pixels:10}],1,1000);
 assert.equal(data.length,1000);assert.ok(data.some(v=>v!==0));assert.ok(data.every(v=>Math.abs(v)<=.26));
});
test('WAV header matches samples and captions cover the full clip',()=>{
 const bytes=wavBytes(new Float32Array(1000),1000),view=new DataView(bytes);
 assert.equal(view.getUint32(24,true),1000);assert.equal(view.getUint32(40,true),2000);
 const srt=captions({observations:[{gap_days:null},{gap_days:36}]},{name:'Test region',series:[{date:'20260101',water_km2:0},{date:'20260206',water_km2:1}]});
 assert.ok(srt.includes('00:00:10,000 --> 00:00:20,000'));assert.ok(srt.includes('36 days'));
});

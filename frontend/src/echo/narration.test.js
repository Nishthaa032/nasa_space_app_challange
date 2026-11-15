import test from 'node:test';
import assert from 'node:assert/strict';
import {explanation,matchingVoices} from './narration.js';
const data={common_coverage_percent:51.25,observations:[{gap_days:null},{gap_days:24}]};
const row=(date,water)=>({date,water_km2:water,water_fraction:water,valid_pixels:100});
const region={id:'return-1',name:'Test patch',series:[row('20260423',.8),row('20260517',.974)]};
test('narration preserves actual date, change, coverage and uncertainty',()=>{
 const text=explanation(data,region,1).join(' ');
 for(const expected of ['17 May 2026','0.974','97 percent','increased by 0.174','24 days','51.25 percent','does not confirm a flood'])assert.ok(text.includes(expected),expected);
});
test('missing data does not become zero water and first date has no invented comparison',()=>{
 assert.ok(explanation(data,region,0).join(' ').includes('No comparison'));
 const missing={...region,series:[{...region.series[0],water_km2:null,water_fraction:null,valid_pixels:0}]};
 const text=explanation(data,missing,0).join(' ');assert.ok(text.includes('Missing data does not mean dry land'));assert.ok(!text.includes('0.000'));
});
test('Hindi preserves numeric evidence; decrease and unchanged are distinguished',()=>{
 assert.ok(explanation(data,region,1,'hi-IN').join(' ').includes('0.174 वर्ग किलोमीटर बढ़ा'));
 const falling={...region,series:[region.series[1],region.series[0]]};assert.ok(explanation(data,falling,1).join(' ').includes('decreased by 0.174'));
 const equal={...region,series:[region.series[0],region.series[0]]};assert.ok(explanation(data,equal,1).join(' ').includes('unchanged'));
});
test('voice matching never substitutes an unrelated language and prefers device voices',()=>{
 const voices=[{lang:'en-US',localService:true},{lang:'hi-IN',localService:false},{lang:'hi_IN',localService:true}];
 assert.deepEqual(matchingVoices(voices,'hi-IN'),[voices[2],voices[1]]);assert.deepEqual(matchingVoices([voices[0]],'hi-IN'),[]);
});

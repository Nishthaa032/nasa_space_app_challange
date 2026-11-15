const usable = row => row && row.valid_pixels > 0 && Number.isFinite(row.water_km2) && Number.isFinite(row.water_fraction);
export function explanation(data, region, index, language = 'en-IN') {
 const row=region.series[index], previous=region.series[index-1], hi=language.startsWith('hi');
 const date=new Intl.DateTimeFormat(language,{day:'numeric',month:'long',year:'numeric',timeZone:'UTC'}).format(new Date(`${row.date.slice(0,4)}-${row.date.slice(4,6)}-${row.date.slice(6,8)}T12:00:00Z`));
 const lines=[hi?`${region.name}। यह अवलोकन ${date} का है।`:`${region.name}. This observation was acquired on ${date}.`];
 if(usable(row)){
  lines.push(hi?`तुलना योग्य क्षेत्र में अनुमानित पानी ${row.water_km2.toFixed(3)} वर्ग किलोमीटर है। यह चुने गए क्षेत्र का लगभग ${Math.round(row.water_fraction*100)} प्रतिशत है।`:`Predicted water covers ${row.water_km2.toFixed(3)} square kilometres, approximately ${Math.round(row.water_fraction*100)} percent of the selected comparable area.`);
  if(usable(previous)){
   const delta=row.water_km2-previous.water_km2,amount=Math.abs(delta).toFixed(3);
   lines.push(Math.abs(delta)<.0005?(hi?'पिछले अवलोकन की तुलना में, तीन दशमलव स्थानों तक पानी का कुल क्षेत्र समान है।':'Total predicted water area is unchanged from the previous observation to three decimal places.'):(hi?`पिछले अवलोकन की तुलना में पानी का कुल क्षेत्र ${amount} वर्ग किलोमीटर ${delta>0?'बढ़ा':'घटा'} है।`:`Total predicted water area ${delta>0?'increased':'decreased'} by ${amount} square kilometres since the previous observation.`));
  }else lines.push(hi?'इस तारीख के लिए पिछले अवलोकन से विश्वसनीय तुलना उपलब्ध नहीं है।':'No comparison with a previous valid observation is available for this date.');
 }else lines.push(hi?'इस अवलोकन में पानी का विश्वसनीय माप उपलब्ध नहीं है। इसे सूखी भूमि न समझें।':'No usable water measurement is available for this observation. Missing data does not mean dry land.');
 const gap=data.observations[index].gap_days;
 if(gap>0)lines.push(hi?`पिछले अवलोकन से ${gap} दिन का अंतर है। इन तारीखों के बीच क्या हुआ, यह डेटा नहीं बताता।`:`There are ${gap} days since the previous observation. These measurements do not establish what happened between passes.`);
 lines.push(hi?`आँकड़े केवल उन पिक्सेलों पर आधारित हैं जो हर तारीख पर उपलब्ध हैं। यह पूरे अध्ययन क्षेत्र का ${data.common_coverage_percent} प्रतिशत है।`:`Statistics use only pixels available on every date, covering ${data.common_coverage_percent} percent of the full study area.`);
 if(region.id!=='study')lines.push(hi?'इस क्षेत्र को पहली और आखिरी तारीख पर गैर-पानी, और बीच की किसी तारीख पर पानी के रूप में वर्गीकृत किया गया है। इससे बाढ़ या उसके कारण की पुष्टि नहीं होती।':'This patch was classified as non-water at both endpoints and as water in between. This does not confirm a flood or its cause.');
 lines.push(hi?'ये रडार आधारित प्रायोगिक अनुमान हैं, बाढ़ की पुष्ट चेतावनी नहीं।':'These are exploratory radar-based predictions, not a confirmed flood warning.');
 return lines;
}
export function matchingVoices(voices, language){return voices.filter(v=>v.lang.toLowerCase().split(/[-_]/)[0]===language.split('-')[0]).sort((a,b)=>Number(b.localService)-Number(a.localService));}

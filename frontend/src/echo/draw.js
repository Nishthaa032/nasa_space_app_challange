import {readableDate} from './sound';
function text(ctx,value,x,y,size=18,color='#aac0c8',weight=400){ctx.fillStyle=color;ctx.font=`${weight} ${size}px system-ui,sans-serif`;ctx.fillText(value,x,y);}
function fitImage(ctx,image,box,x,y,w,h){
 const [x1,y1,x2,y2]=box, sw=x2-x1,sh=y2-y1,scale=Math.min(w/sw,h/sh),dw=sw*scale,dh=sh*scale;
 ctx.imageSmoothingEnabled=false;ctx.drawImage(image,x1,y1,sw,sh,x+(w-dw)/2,y+(h-dh)/2,dw,dh);
}
export function drawFrame(canvas,dataset,region,images,index,progress=0,endpoints=false){
 if(!canvas||!dataset||!images.length)return;
 const ctx=canvas.getContext('2d'),w=canvas.width,h=canvas.height;
 ctx.fillStyle='#0a1420';ctx.fillRect(0,0,w,h);
 for(let x=0;x<w;x+=40){ctx.strokeStyle='#18303b';ctx.lineWidth=.4;ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,h);ctx.stroke();}
 for(let y=0;y<h;y+=40){ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(w,y);ctx.stroke();}
 text(ctx,'SARScope  /  EARTH ECHO',36,44,16,'#97ddc8',650);
 text(ctx,region.name,36,86,28,'#edf6f4',600);
 const row=region.series[index],observation=dataset.observations[index];
 if(endpoints){
  fitImage(ctx,images[0],region.box,30,135,570,400);fitImage(ctx,images.at(-1),region.box,650,135,570,400);
  text(ctx,readableDate(dataset.observations[0].date),42,125,18,'#cadfdf');text(ctx,readableDate(dataset.observations.at(-1).date),660,125,18,'#cadfdf');
  text(ctx,'The middle matters.',42,579,26,'#c5adff',600);
  text(ctx,'A first / last comparison can hide intermediate water changes.',42,613,19,'#c4d5dc');
 }else{
  fitImage(ctx,images[index],region.box,30,120,670,430);
  text(ctx,readableDate(row.date),750,153,34,'#f0f6f3',650);
  text(ctx,`${index+1} / ${region.series.length} real observations`,750,188,17);
  text(ctx,`${row.water_km2.toFixed(3)} km²`,750,267,43,'#91e5ce',600);
  text(ctx,'predicted water on common pixels',750,299,16);
  text(ctx,`${Math.round((row.water_fraction??0)*100)}% of selected area`,750,334,20,'#d5e4e5');
  text(ctx,`+${row.new_km2.toFixed(3)} new / −${row.receded_km2.toFixed(3)} receded km²`,750,377,16);
  text(ctx,observation.gap_days?`${observation.gap_days} real days since previous observation`:'First observation in this timeline',750,422,16,'#b9a3e8');
  text(ctx,`${dataset.common_coverage_percent}% of full crop comparable on all dates`,750,455,15);
  text(ctx,'Teal = water   ·   Purple = temporary-water candidate',40,581,16);
  const left=45,top=610,cw=1160,ch=48,max=Math.max(...region.series.map(s=>s.water_km2),.0001);
  ctx.strokeStyle='#80ddc7';ctx.lineWidth=2;ctx.beginPath();
  region.series.forEach((s,i)=>{const x=left+i*cw/(region.series.length-1),y=top+ch-s.water_km2/max*ch;i?ctx.lineTo(x,y):ctx.moveTo(x,y);});ctx.stroke();
  region.series.forEach((s,i)=>{ctx.fillStyle=i===index?'#e8c884':'#80ddc7';ctx.beginPath();ctx.arc(left+i*cw/(region.series.length-1),top+ch-s.water_km2/max*ch,i===index?6:3,0,Math.PI*2);ctx.fill();});
  ctx.fillStyle='#8ee3c8';ctx.fillRect(0,h-5,w*Math.min(1,progress),5);
 }
 text(ctx,'NISAR-derived exploratory predictions · not a flood warning',36,690,14,'#8ca5b3');
}

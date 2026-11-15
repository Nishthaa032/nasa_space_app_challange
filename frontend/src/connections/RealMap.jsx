import React, { useEffect, useRef, useState } from 'react';
import * as maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import usePlaceLabels from './usePlaceLabels';
import { WATER_COLORS, ROAD_COLORS, PLACE_COLORS } from './palette';
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url';
maplibregl.setWorkerUrl(workerUrl);
const collection = features => ({type:'FeatureCollection',features});
export default function RealMap({network, reviews, selected, onSelect, waterView}) {
  const container = useRef(null), map = useRef(null), selectRef = useRef(onSelect);
  const [ready,setReady] = useState(false), [error,setError] = useState(''), [showNames,setShowNames] = useState(true);
  usePlaceLabels(map, ready, network, showNames);
  selectRef.current = onSelect;
  useEffect(() => {
    let instance;
    try {
      instance = new maplibregl.Map({container:container.current,center:[140.26,35.80],zoom:12,style:{version:8,sources:{base:{type:'raster',tiles:['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],tileSize:256,attribution:'© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>'}},layers:[{id:'base',type:'raster',source:'base',paint:{'raster-saturation':-.7,'raster-brightness-max':.45}}]}});
      map.current = instance;
      instance.addControl(new maplibregl.NavigationControl(),'top-right');
      instance.on('load',()=>{
        for(const id of ['roads','places','water','selection']) instance.addSource(id,{type:'geojson',data:collection([])});
        instance.addLayer({id:'water',source:'water',type:'fill',paint:{'fill-color':['match',['get','class'],2,WATER_COLORS.new,3,WATER_COLORS.receded,WATER_COLORS.persistent],'fill-opacity':.5}});
        instance.addLayer({id:'roads',source:'roads',type:'line',paint:{'line-color':['match',['get','status'],'unknown',ROAD_COLORS.unknown,'closed',ROAD_COLORS.closed,'open',ROAD_COLORS.open,'unassessed',ROAD_COLORS.unassessed,ROAD_COLORS.mapped],'line-width':2.5,'line-opacity':.85}});
        instance.addLayer({id:'selection',source:'selection',type:'line',paint:{'line-color':ROAD_COLORS.selected,'line-width':6}});
        instance.addLayer({id:'places',source:'places',type:'circle',paint:{'circle-radius':['match',['get','type'],'hospital',8,5],'circle-color':['match',['get','type'],'hospital',PLACE_COLORS.hospital,PLACE_COLORS.community],'circle-stroke-color':'#111f29','circle-stroke-width':2}});
        instance.on('click','roads',e=>selectRef.current(e.features[0].properties.id));
        instance.on('click','places',e=>new maplibregl.Popup().setLngLat(e.features[0].geometry.coordinates).setText(e.features[0].properties.name).addTo(instance));
        instance.on('mouseenter','roads',()=>{instance.getCanvas().style.cursor='pointer';});
        instance.on('mouseleave','roads',()=>{instance.getCanvas().style.cursor='';});
        setReady(true);
      });
      instance.on('error',()=>setError('Some map resources could not load. Road analysis remains available in the lists.'));
      instance.on('idle',()=>setError(''));
    } catch {setError('The geographic map needs WebGL. Use the road and community lists below.');}
    return ()=>{instance?.remove();map.current=null;};
  },[]);
  useEffect(()=>{
    if(!ready||!network)return;
    const m=map.current;
    const roads=network.edges.filter(e=>!e.virtual).map(e=>({type:'Feature',geometry:{type:'LineString',coordinates:e.geometry},properties:{id:e.id,status:reviews[e.id]?.status??e.status}}));
    m.getSource('roads').setData(collection(roads));
    m.getSource('places').setData(collection(network.nodes.filter(n=>n.type!=='junction').map(n=>({type:'Feature',geometry:{type:'Point',coordinates:[n.lon,n.lat]},properties:{name:n.name,type:n.type}}))));
    m.getSource('selection').setData(collection(roads.filter(f=>f.properties.id===selected)));
    const classes=waterView==='before'?[1,3]:waterView==='after'?[1,2]:waterView==='none'?[]:[1,2,3];
    m.getSource('water').setData(collection((network.water?.features||[]).filter(f=>classes.includes(f.properties.class))));
  },[ready,network,reviews,selected,waterView]);
  useEffect(()=>{if(ready&&network)map.current.fitBounds([[network.bounds[0],network.bounds[1]],[network.bounds[2],network.bounds[3]]],{padding:40,duration:600});},[ready,network]);
  return <div className="rc-map-wrap"><div className="rc-map" ref={container}/>{ready&&network&&selected&&<button className="rc-focus" onClick={()=>{const e=network.edges.find(e=>e.id===selected);if(e?.geometry?.length){const b=new maplibregl.LngLatBounds(e.geometry[0],e.geometry[0]);e.geometry.forEach(c=>b.extend(c));map.current.fitBounds(b,{padding:80,maxZoom:16,duration:600});}}}>Focus selected road</button>}{network&&<button className="rc-label-toggle" aria-pressed={showNames} onClick={()=>setShowNames(value=>!value)}>{showNames?'Hide place names':'Show place names'}</button>}{error&&<p className="rc-map-error">{error}</p>}{!network&&<div className="rc-map-prompt"><strong>Your real area, your actual evidence.</strong><span>Choose observation dates and load the road network.</span></div>}</div>;
}

"""Export every compatible, real local radar date for Earth Echo.

Comparison statistics use the same pixels on every date. Candidate return
patches are dry at both endpoints and wet on an intermediate observation.
"""
import hashlib
import json
import re
from datetime import datetime

import numpy as np
import rasterio
from PIL import Image
from pyproj import Transformer
from scipy.ndimage import label, find_objects

from .common import ROOT


def return_patches(stack, minimum_pixels=25, limit=6):
    valid = np.isin(stack, [0, 1]).all(axis=0)
    returning = valid & (stack[0] == 0) & (stack[-1] == 0) & (stack[1:-1] == 1).any(axis=0)
    components, count = label(returning)
    sizes = np.bincount(components.ravel()); sizes[0] = 0
    candidates = [i for i in np.argsort(sizes)[::-1] if sizes[i] >= minimum_pixels][:limit]
    slices = find_objects(components)
    patches = []
    for component in candidates:
        rows, cols = slices[component-1]
        patches.append({'mask': components == component, 'pixels': int(sizes[component]), 'box': [cols.start, rows.start, cols.stop, rows.stop]})
    return valid, returning, patches


def build():
    destination = ROOT / 'frontend/public/data/echo'
    destination.mkdir(parents=True, exist_ok=True)
    frames, profiles, dates, hh = [], [], [], []
    for path in sorted((ROOT/'outputs/ml').glob('*_surface_water.tif')):
        date = path.name[:8]
        if not re.fullmatch(r'\d{8}', date): continue
        radar = ROOT/'data/cleaned'/f'{date}_HHHH_dB.tif'
        hv = ROOT/'data/cleaned'/f'{date}_HVHV_dB.tif'
        if not radar.is_file() or not hv.is_file(): continue
        with rasterio.open(path) as ds:
            profile = ds.profile
            if profiles and any(profile[k] != profiles[0][k] for k in ['crs','transform','width','height']):
                raise ValueError(f'Incompatible grid on {date}; no silent alignment.')
            frames.append(ds.read(1));profiles.append(profile);dates.append(date)
        with rasterio.open(radar) as ds:
            if ds.transform != profile['transform'] or ds.crs != profile['crs'] or ds.shape != frames[-1].shape:
                raise ValueError(f'Radar grid mismatch on {date}')
            hh.append(ds.read(1))
    if len(frames) < 5: raise ValueError('Earth Echo requires at least five real observations.')
    stack = np.stack(frames)
    common, returning, patches = return_patches(stack)
    if not common.any(): raise ValueError('No common valid pixels across these dates; cannot compare areas.')
    profile = profiles[0]; transform = profile['transform']
    pixel_area = abs(transform.a * transform.e - transform.b * transform.d) / 1e6
    height,width=stack.shape[1:]
    project=Transformer.from_crs(profile['crs'],4326,always_xy=True)
    bounds=[list(project.transform(* (transform * point))) for point in [(0,0),(width,0),(width,height),(0,height)]]
    regions=[{'id':'study','name':'Lake Inba study area','box':[0,0,width,height],'mask':common,'description':'Full study crop, compared on the same valid pixels across all dates.'}]
    for i,patch in enumerate(patches):
        x1,y1,x2,y2=patch['box']
        lon,lat=project.transform(*(transform*((x1+x2)/2,(y1+y2)/2)))
        compass=('North' if (y1+y2)/2 < height/2 else 'South') + ('-east' if (x1+x2)/2 > width/2 else '-west')
        regions.append({'id':f'return-{i+1}','name':f'{compass} return patch {i+1}','box':[max(0,x1-12),max(0,y1-12),min(width,x2+12),min(height,y2+12)],'mask':patch['mask'],'description':'Candidate temporary water: nonwater at both endpoints, water in between. Cause unconfirmed.','latitude':round(lat,6),'longitude':round(lon,6)})
    source_records={}
    for item in json.loads((ROOT/'data/manifests/nisar_expansion.json').read_text()):
        source_records[item['date'][:10].replace('-','')]={'name':item['id'],'url':item['url'],'acquired':item['date']}
    extra=ROOT/'data/manifests/echo_sources.json'
    if extra.exists():source_records.update(json.loads(extra.read_text()))
    observations=[]
    for index,date in enumerate(dates):
        data=frames[index]; gray=np.clip((np.nan_to_num(hh[index],nan=-25)+25)/22,0,1)
        rgb=np.stack([19+gray*38,33+gray*47,42+gray*52],axis=-1).astype('uint8')
        rgb[data==1]=[85,214,193]
        rgb[(data==1)&returning]=[189,159,252]
        rgb[~np.isin(data,[0,1])]=[10,14,24]
        Image.fromarray(rgb).save(destination/f'{date}.png')
        previous=datetime.strptime(dates[index-1],'%Y%m%d') if index else None
        observations.append({'date':date,'image':f'/data/echo/{date}.png','gap_days':(datetime.strptime(date,'%Y%m%d')-previous).days if previous else None,'coverage_percent':round(float(np.isin(data,[0,1]).mean())*100,2),'source':source_records.get(date,{}),'raster_sha256':hashlib.sha256((ROOT/'outputs/ml'/f'{date}_surface_water.tif').read_bytes()).hexdigest()})
    for region in regions:
        mask=region.pop('mask'); total=int(mask.sum()); series=[]
        for index,date in enumerate(dates):
            wet=int(((stack[index]==1)&mask).sum())
            prev=stack[index-1] if index else stack[index]
            series.append({'date':date,'water_km2':round(wet*pixel_area,5),'water_fraction':wet/total if total else None,'new_km2':round(float((mask&(prev==0)&(stack[index]==1)).sum())*pixel_area,5),'receded_km2':round(float((mask&(prev==1)&(stack[index]==0)).sum())*pixel_area,5),'mean_hh_db':round(float(np.nanmean(hh[index][mask])),2) if np.isfinite(hh[index][mask]).any() else None,'valid_pixels':total,'coverage_percent':round(float(np.isin(stack[index],[0,1])[mask].mean())*100,2)})
        region.update(series=series,area_km2=round(total*pixel_area,5),peak_index=int(np.argmax([s['water_km2'] for s in series])))
        if region['id']!='study':
            wet_indices=[i for i,s in enumerate(series) if s['water_km2']>0]
            region.update(first_wet=dates[wet_indices[0]],last_wet=dates[wet_indices[-1]],return_observed=dates[wet_indices[-1]+1])
    output={'version':1,'title':'Earth Echo · Lake Inba, Japan','width':width,'height':height,'coordinates':bounds,'pixel_size_m':abs(transform.a),'observations':observations,'regions':regions,'common_coverage_percent':round(float(common.mean())*100,2),'return_area_km2':round(float(returning.sum())*pixel_area,5),'minimum_patch_pixels':25,'limitations':['Exploratory predictions from the earlier radar-only Random Forest, not independently validated flood events.','Statistics use pixels valid on every observation; they do not describe the unobserved part of the crop.','Observed dates do not establish what happened between acquisitions. Equal playback slots compress unequal real time gaps.','Purple map pixels are candidate return pixels; a patch can include pixels peaking on different dates.','Audio is generated from measurements, not satellite-recorded sound. No vegetation or hazard inference is encoded.']}
    output['sonification'] = {'duration_seconds':20,'sample_rate_hz':22050,'frequency_hz':'220 + 440 * water_fraction','pulses_per_observation':'1 + floor(5 * water_fraction)','accent':'880 Hz when water fraction increases by at least 0.02','timing':'Equal observation slots; real acquisition gaps retained separately.','missing':'Silence; never replaced with zero water.'}
    (destination/'manifest.json').write_text(json.dumps(output,indent=2,allow_nan=False))
    print(f'Exported {len(dates)} real dates, {len(patches)} return patches, common coverage {output["common_coverage_percent"]}%.')
    return output


if __name__=='__main__':build()

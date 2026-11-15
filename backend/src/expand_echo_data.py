"""Add explicitly selected, catalog-listed real scenes to the original study grid.

No full-file download, synthetic fallback, model fitting, or overwritten dates.
"""
import argparse
import hashlib
import json
from pathlib import Path

import h5py
import joblib
import numpy as np

from monitor.remote import RangeFile
from monitor.catalog import science_url
from .clean_data import smooth_power
from .common import ROOT, read_raster, write_raster
from .train_ml import feature_stack


def expand(catalog_path, dates):
    catalog = json.loads(Path(catalog_path).read_text())
    selected = {}
    for item in catalog:
        name = item.get('producer_granule_id', '')
        if '_118_D_071_2005_DHDH_M_' not in name:
            continue
        date = name.split('_')[11][:8]
        links = [link['href'] for link in item.get('links', []) if science_url(link.get('href', '')) and not link.get('inherited')]
        if date in dates and links:
            # Prefer the latest processing revision if the catalog has duplicates.
            if date not in selected or name > selected[date]['name']:
                selected[date] = {'name': name, 'date': date, 'url': links[0], 'cmr_id': item['id'], 'acquired': item['time_start']}
    _, profile = read_raster(ROOT / 'data/processed/20260914_HHHH_dB.tif')
    t = profile['transform']
    expected_x = t.c + (np.arange(profile['width']) + .5) * t.a
    expected_y = t.f + (np.arange(profile['height']) + .5) * t.e
    model_path = ROOT / 'models/random_forest.joblib'
    model = joblib.load(model_path)['classifier']
    provenance = ROOT / 'data/manifests/echo_sources.json'
    records = json.loads(provenance.read_text()) if provenance.exists() else {}
    for date in dates:
        if (ROOT / 'outputs/ml' / f'{date}_surface_water.tif').exists():
            print(date, 'already processed; left unchanged', flush=True)
            continue
        scene = selected.get(date)
        if not scene:
            print(date, 'no matching catalog-verified direct source', flush=True)
            continue
        print(date, 'reading bounded real radar window', flush=True)
        try:
            cleaned = {}
            with RangeFile(scene['url'], allow_signed_redirect=True) as remote:
                with h5py.File(remote, 'r') as file:
                    group = file['science/LSAR/GCOV/grids/frequencyA']
                    if int(group['projection'][()]) != profile['crs'].to_epsg():
                        raise ValueError('Projection mismatch')
                    x,y = group['xCoordinates'][:],group['yCoordinates'][:]
                    cols=np.flatnonzero((x>=expected_x[0])&(x<=expected_x[-1]))
                    rows=np.flatnonzero((y<=expected_y[0])&(y>=expected_y[-1]))
                    if not np.array_equal(x[cols],expected_x) or not np.array_equal(y[rows],expected_y):
                        raise ValueError('Exact grid match required')
                    window=(slice(rows[0],rows[-1]+1),slice(cols[0],cols[-1]+1))
                    mask=group['mask'][window]; exceptions=group['inputDataExceptionMask'][window]
                    good=(mask>0)&(mask<255)&(exceptions==0)
                    for pol in ['HHHH','HVHV']:
                        power=group[pol][window]
                        valid=good&np.isfinite(power)&(power>0)
                        db=np.full(power.shape,np.nan,dtype='float32');db[valid]=10*np.log10(power[valid])
                        cleaned[pol]=smooth_power(db,5,20)
                transferred=remote.transferred
            for pol,values in cleaned.items():
                write_raster(ROOT/'data/cleaned'/f'{date}_{pol}_dB.tif',values,profile)
            features,_=feature_stack(ROOT/'data/cleaned',date)
            valid=np.isfinite(features).all(axis=-1)
            if not valid.any():raise ValueError('No usable radar pixels')
            predicted=np.full(valid.shape,255,dtype='uint8');predicted[valid]=model.predict(features[valid])
            target=ROOT/'outputs/ml'/f'{date}_surface_water.tif'
            write_raster(target,predicted,profile,True)
            records[date]={**scene,'transferred_mb':round(transferred/1024**2,2),'valid_percent':round(float(valid.mean())*100,2),'model_sha256':hashlib.sha256(model_path.read_bytes()).hexdigest(),'raster_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'status':'Exploratory radar-only prediction; no independent validation on this date.'}
            provenance.write_text(json.dumps(records,indent=2))
            print(date,'prepared',records[date]['valid_percent'],'% coverage;',records[date]['transferred_mb'],'MB transferred',flush=True)
        except Exception as exc:
            print(date,'could not be added:',type(exc).__name__,str(exc),flush=True)
    return records


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('catalog');parser.add_argument('dates',nargs='+')
    args=parser.parse_args();expand(args.catalog,args.dates)

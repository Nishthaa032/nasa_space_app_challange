"""Explicit synthetic fixtures for topology and overlap; no provider requests."""
import unittest
from unittest.mock import patch
import numpy as np
from affine import Affine
from pyproj import Transformer
from fastapi.testclient import TestClient
from monitor.connections import WaterEvidence, build_network, parse_osm_xml

class WaterTests(unittest.TestCase):
    def evidence(self):
        obj = WaterEvidence.__new__(WaterEvidence)
        old = np.array([[0,1,1,255]],dtype='uint8')
        new = np.array([[1,1,0,1]],dtype='uint8')
        transform = Affine(1,0,0,0,-1,1)
        identity = Transformer.from_crs(4326,4326,always_xy=True)
        obj.datasets = [(old,transform,identity),(new,transform,identity)]
        obj.crs = 'EPSG:4326'
        return obj
    def test_new_persistent_receded_and_missing_are_distinct(self):
        result=self.evidence().sample([(0.5,.5),(1.5,.5),(2.5,.5),(3.5,.5),(9,.5)])
        self.assertEqual(result,{'samples':5,'valid':3,'new_water':1,'persistent_water':1,'receded_water':1,'coverage':60.0})
    def test_overlay_classes_preserve_change_semantics(self):
        self.assertEqual({f['properties']['class'] for f in self.evidence().overlay()['features']},{1,2,3})
    def test_water_memory_keeps_missing_coverage_separate_from_dry(self):
        obj=self.evidence()
        data,transform,project=obj.datasets[0]
        obj.history_datasets=[('20260914',data,transform,project)]
        row=obj.history([(0.5,.5),(1.5,.5),(3.5,.5)])[0]
        self.assertEqual(row['water_percent'],50.0)
        self.assertEqual(row['coverage'],66.7)
        self.assertIsNone(obj.history([(9,.5)])[0]['water_percent'])
    def test_invalid_date_order_rejected_before_io(self):
        with self.assertRaises(ValueError):WaterEvidence('20260926','20260914')

class FakeWater:
    def sample(self,coords):return {'samples':len(coords),'valid':len(coords),'coverage':100,'new_water':0,'persistent_water':0,'receded_water':0}

class NetworkTests(unittest.TestCase):
    def test_real_topology_only_connects_shared_osm_nodes(self):
        xml=b'''<osm><node id="1" lon="0" lat="0"/><node id="2" lon="0.001" lat="0"/><node id="3" lon="0.002" lat="0"/><node id="4" lon="0.001" lat="0.001"/><node id="5" lon="0.001" lat="-0.001"/><node id="6" lon="0.0001" lat="0.0001"><tag k="amenity" v="hospital"/><tag k="name" v="Test hospital"/></node><way id="10"><nd ref="1"/><nd ref="2"/><nd ref="3"/><tag k="highway" v="residential"/><tag k="oneway" v="-1"/></way><way id="11"><nd ref="4"/><nd ref="5"/><tag k="highway" v="primary"/><tag k="bridge" v="yes"/></way></osm>'''
        result=build_network(parse_osm_xml(xml),[-.01,-.01,.01,.01],FakeWater())
        roads=[e for e in result['edges'] if not e.get('virtual')]
        self.assertEqual(len(roads),2)
        self.assertTrue(roads[0]['directed']);self.assertEqual(roads[0]['from'],'osm-3')
        self.assertTrue(roads[1]['bridge'])
        self.assertTrue(set([roads[0]['from'],roads[0]['to']]).isdisjoint([roads[1]['from'],roads[1]['to']]))
        self.assertEqual(sum(n['type']=='hospital' for n in result['nodes']),1)
    def test_no_roads_is_an_error_not_a_fallback(self):
        with self.assertRaisesRegex(ValueError,'No supported'):
            build_network({'elements':[]},[0,0,1,1],FakeWater())
    def test_api_rejects_invalid_bounds_and_reports_provider_failure(self):
        from monitor.api import app
        client=TestClient(app)
        body={'latitude':35.8,'longitude':140.26,'radius_km':3,'before':'20260914','after':'20260926'}
        self.assertEqual(client.post('/api/connections/analyze',json=body).status_code,403)
        self.assertEqual(client.post('/api/connections/analyze',json={**body,'radius_km':90},headers={'x-sarscope':'1'}).status_code,422)
        with patch('monitor.connections.analyze',side_effect=ValueError('Provider unavailable')):
            response=client.post('/api/connections/analyze',json=body,headers={'x-sarscope':'1'})
            self.assertEqual(response.status_code,422)
            self.assertEqual(response.json()['detail'],'Provider unavailable')

import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from monitor.api import app
from monitor.echo_video import storyboard

class ExplainerTests(unittest.TestCase):
    def setUp(self):
        self.data={'common_coverage_percent':51.25,'observations':[{'date':'20260105','gap_days':None},{'date':'20260306','gap_days':60}]}
        self.region={'id':'study','name':'Lake Inba study area','series':[{'date':'20260105','valid_pixels':100,'water_km2':.8,'water_fraction':.8},{'date':'20260306','valid_pixels':100,'water_km2':.3,'water_fraction':.3}]}
    def test_visual_scenes_use_actual_measurements_and_date_indices(self):
        scenes=storyboard(self.data,self.region,1)
        self.assertEqual(scenes[1]['frames'],[0,1])
        self.assertIn('decreased by 0.500',scenes[1]['text'])
        self.assertIn('60 days',scenes[1]['text'])
        self.assertEqual(scenes[2]['kind'],'chart')
        self.assertIn('51.25 percent',scenes[-1]['text'])
        self.assertIn('not confirmed floods',scenes[-1]['text'])
    def test_first_date_has_no_invented_comparison_and_return_patch_uses_endpoints(self):
        scenes=storyboard(self.data,self.region,0)
        self.assertIn('no earlier observation',scenes[1]['text'])
        self.region['id']='return-1'
        self.assertEqual(storyboard(self.data,self.region,1)[-2]['frames'],[0,1])
    def test_no_data_is_rejected(self):
        self.region['series'][1]['valid_pixels']=0
        with self.assertRaises(ValueError):storyboard(self.data,self.region,1)
    def test_request_validation_and_failure_are_explicit(self):
        client=TestClient(app)
        self.assertEqual(client.post('/api/echo/video',json={'region_id':'study','date':'20260306'}).status_code,403)
        self.assertEqual(client.post('/api/echo/video',headers={'X-SARScope':'1'},json={'region_id':'../../private','date':'20260306'}).status_code,422)
        with patch('monitor.echo_video.create_video',side_effect=RuntimeError('Voice unavailable')):
            response=client.post('/api/echo/video',headers={'X-SARScope':'1'},json={'region_id':'study','date':'20260306'})
            self.assertEqual(response.status_code,503)
            self.assertEqual(response.json()['detail'],'Voice unavailable')

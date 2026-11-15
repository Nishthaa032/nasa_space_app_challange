"""Temporary-water detection and authenticated range delivery invariants."""
import unittest
import httpx
import numpy as np
from monitor.remote import RangeFile, RangeRequired
from src.export_echo import return_patches

URL = 'https://nisar.asf.earthdatacloud.nasa.gov/NISAR/test.h5'
CDN = 'https://d1mv8zhcvry6x4.cloudfront.net/test.h5?Signature=test'

class EchoTests(unittest.TestCase):
    def test_intermediate_water_with_dry_endpoints_and_complete_coverage(self):
        stack = np.zeros((5, 4, 5), dtype='uint8')
        stack[2, :2, :2] = 1
        stack[0, 3, 0] = stack[2, 3, 0] = 1
        stack[2, 3, 1] = stack[-1, 3, 1] = 1
        stack[1, 3, 2] = 255
        stack[2, 3, 2] = 1
        valid, returning, patches = return_patches(stack, minimum_pixels=4)
        self.assertEqual(returning.sum(), 4)
        self.assertFalse(valid[3, 2])
        self.assertEqual(len(patches), 1)
        self.assertEqual(patches[0]['box'], [0, 0, 2, 2])
        self.assertEqual(return_patches(stack, minimum_pixels=5)[2], [])

    def test_signed_delivery_never_receives_bearer_and_retains_ranges(self):
        calls=[]
        def reply(req):
            calls.append(req)
            if req.url.host.endswith('nasa.gov'):
                return httpx.Response(303, headers={'Location': CDN})
            self.assertNotIn('Authorization', req.headers)
            a,b=map(int,req.headers['Range'].split('=')[1].split('-'))
            return httpx.Response(206,headers={'Content-Range':f'bytes {a}-{b}/4'},content=b'data'[a:b+1])
        with httpx.Client(transport=httpx.MockTransport(reply)) as client:
            with RangeFile(URL,'test-only',client=client,allow_signed_redirect=True) as file:
                self.assertEqual(file.read(4),b'data')
                self.assertEqual(file.transferred,5)
        self.assertEqual(len(calls),3)
        self.assertEqual(calls[0].headers['Authorization'],'Bearer test-only')

    def test_redirect_requires_opt_in_and_rejects_unapproved_destination(self):
        for target,opt_in in [(CDN,False),('https://other.invalid/file',True)]:
            calls=[]
            def reply(req):
                calls.append(req)
                return httpx.Response(303,headers={'Location':target})
            with httpx.Client(transport=httpx.MockTransport(reply)) as client:
                with self.assertRaises(RangeRequired):
                    RangeFile(URL,'test-only',client=client,allow_signed_redirect=opt_in)
            self.assertEqual(len(calls),1)

    def test_cdn_full_response_is_rejected(self):
        def reply(req):
            return httpx.Response(303,headers={'Location':CDN}) if req.url.host.endswith('nasa.gov') else httpx.Response(200,content=b'whole file')
        with httpx.Client(transport=httpx.MockTransport(reply)) as client:
            with self.assertRaises(RangeRequired):
                RangeFile(URL,'test-only',client=client,allow_signed_redirect=True)

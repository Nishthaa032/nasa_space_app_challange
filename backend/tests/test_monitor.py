"""Monitoring safety, geospatial preprocessing and API behavior using synthetic data."""

import io
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import h5py
import httpx
import numpy as np
from fastapi.testclient import TestClient
from monitor import api, processing
from monitor.remote import RangeFile, RangeRequired
from monitor.store import Store
from rasterio.transform import from_origin

URL = "https://nisar.asf.earthdatacloud.nasa.gov/NISAR/test.h5"


class RangeTests(unittest.TestCase):
    def test_full_response_never_read(self):
        client = httpx.Client(
            transport=httpx.MockTransport(lambda req: httpx.Response(200, content=b"not a range"))
        )
        with self.assertRaisesRegex(RangeRequired, "partial response"):
            RangeFile(URL, "test-only", client=client)

    def test_redirect_does_not_forward_credentials(self):
        calls = []

        def reply(req):
            calls.append(str(req.url))
            return httpx.Response(302, headers={"Location": "https://other.invalid/file"})

        with self.assertRaises(RangeRequired):
            RangeFile(URL, "test-only", client=httpx.Client(transport=httpx.MockTransport(reply)))
        self.assertEqual(calls, [URL])

    def test_unapproved_host_rejected(self):
        with self.assertRaises(ValueError):
            RangeFile("https://example.com/file.h5", "test-only")

    def test_hdf_subset_and_transfer_budget(self):
        buffer = io.BytesIO()
        with h5py.File(buffer, "w") as f:
            f.create_dataset("pixels", data=np.arange(500000, dtype="float32"), chunks=(1000,))
        payload = buffer.getvalue()
        calls = []

        def reply(req):
            a, b = map(int, req.headers["Range"].split("=")[1].split("-"))
            calls.append((a, b))
            return httpx.Response(
                206,
                headers={"Content-Range": f"bytes {a}-{b}/{len(payload)}"},
                content=payload[a : b + 1],
            )

        client = httpx.Client(transport=httpx.MockTransport(reply))
        with RangeFile(URL, "test-only", budget=1024**2, client=client) as remote:
            with h5py.File(remote, "r") as f:
                np.testing.assert_array_equal(f["pixels"][20:30], np.arange(20, 30))
            self.assertLess(remote.transferred, len(payload))
        with RangeFile(URL, "test-only", budget=10, client=client) as remote:
            with self.assertRaisesRegex(RangeRequired, "cap reached"):
                remote.read(100)


class ScienceTests(unittest.TestCase):
    def test_prior_water_not_new_and_missing_excluded(self):
        a = np.array([[1, 0, 255, 0]], dtype="uint8")
        b = np.array([[0, 0, 0, 0]], dtype="uint8")
        c = np.array([[0, 0, 0, 0]], dtype="uint8")
        latest = np.array([[1, 1, 1, 255]], dtype="uint8")
        baseline, change = processing.historical_change([a, b, c], latest)
        np.testing.assert_array_equal(change, [[1, 2, 255, 255]])
        self.assertEqual(baseline[0, 0], 1)

    def test_not_enough_baseline_dates(self):
        with self.assertRaises(ValueError):
            processing.historical_change([np.zeros((2, 2))], np.zeros((2, 2)))

    def test_projected_grid_and_synthetic_crop(self):
        buffer = io.BytesIO()
        with h5py.File(buffer, "w") as f:
            g = f.create_group("science/LSAR/GCOV/grids/frequencyA")
            g["projection"] = 32654
            g["xCoordinateSpacing"] = 10
            g["yCoordinateSpacing"] = -10
            g["xCoordinates"] = 430005 + np.arange(100) * 10
            g["yCoordinates"] = 3970995 - np.arange(100) * 10
            g["HHHH"] = np.ones((100, 100), dtype="float32") * 0.1
            g["HVHV"] = np.ones((100, 100), dtype="float32") * 0.01
            g["mask"] = np.ones((100, 100), dtype="uint8")
            g["inputDataExceptionMask"] = np.zeros((100, 100), dtype="uint8")
            profile = {
                "width": 20,
                "height": 20,
                "transform": from_origin(430200, 3970800, 20, 20),
                "crs": "EPSG:32654",
            }
            features = processing.crop(f, profile)
            np.testing.assert_allclose(features[5:-5, 5:-5, 0], -10, atol=0.001)
            np.testing.assert_allclose(features[5:-5, 5:-5, 1], -20, atol=0.001)

    def test_daily_checks_are_not_continuous(self):
        current = datetime.now(timezone.utc)
        self.assertFalse(api.due({"daily": True, "last_attempt": current.isoformat()}, current))
        self.assertTrue(
            api.due(
                {"daily": True, "last_attempt": (current - timedelta(days=2)).isoformat()}, current
            )
        )
        self.assertFalse(api.due({"daily": False}, current))


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.patcher = patch.object(api, "store", Store(Path(self.tmp.name) / "state.sqlite"))
        self.patcher.start()
        self.client = TestClient(api.app)
        self.body = {
            "name": "Synthetic test area",
            "latitude": 35.8,
            "longitude": 140.2,
            "radius_km": 1,
            "daily": False,
            "auto_process": False,
        }
        self.headers = {"X-SARScope": "1"}

    def tearDown(self):
        self.client.close()
        self.patcher.stop()
        self.tmp.cleanup()

    def test_cross_origin_and_missing_header_rejected(self):
        self.assertEqual(self.client.post("/api/areas", json=self.body).status_code, 403)
        self.assertEqual(
            self.client.post(
                "/api/areas",
                json=self.body,
                headers={**self.headers, "Origin": "https://untrusted.invalid"},
            ).status_code,
            403,
        )

    def test_saved_areas_and_validation(self):
        response = self.client.post("/api/areas", json=self.body, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        area = response.json()
        self.assertEqual(len(area["bounds"]), 4)
        self.assertEqual(len(self.client.get("/api/areas").json()), 1)
        self.assertEqual(
            self.client.post(
                "/api/areas", json={**self.body, "radius_km": 500}, headers=self.headers
            ).status_code,
            422,
        )
        self.assertEqual(
            self.client.put(
                "/api/areas/" + area["id"], json={**self.body, "latitude": 30}, headers=self.headers
            ).status_code,
            400,
        )

    def test_no_token_in_status(self):
        with patch.object(api.settings, "TOKEN", "secret-test-token"):
            response = self.client.get("/api/status")
            self.assertTrue(response.json()["token_configured"])
            self.assertNotIn("secret-test-token", response.text)

    def test_unlisted_scene_not_processed(self):
        area = self.client.post("/api/areas", json=self.body, headers=self.headers).json()
        response = self.client.post(
            "/api/areas/" + area["id"] + "/analyze",
            json={"scene_ids": ["one", "two", "three", "four"]},
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 400)


class ExportIntegrationTests(unittest.TestCase):
    def test_synthetic_processing_exports_all_views_and_reuses_cache(self):
        from contextlib import ExitStack

        class SyntheticFile(io.BytesIO):
            transferred = 10

            def __init__(self, url):
                super().__init__()
                with h5py.File(self, "w") as file:
                    file["fixture"] = np.array([1])
                self.seek(0)

        area = {
            "id": "fixture-area",
            "name": "Synthetic test only",
            "longitude": 140.2,
            "latitude": 35.8,
            "radius_km": 0.5,
        }
        scenes = [
            {
                "id": str(i),
                "name": f"NISAR_L2_PR_GCOV_03{i}_118_D_071_2005_DHDH_M_2026100{i}T092825",
                "acquired": f"2026-10-0{i}T09:28:25Z",
                "url": URL,
                "collection": "fixture",
            }
            for i in range(1, 5)
        ]
        features = np.zeros((50, 50, 3), dtype="float32")
        features[:] = [-10, -20, 10]
        with tempfile.TemporaryDirectory() as temp, ExitStack() as stack:
            stack.enter_context(patch.object(processing, "CACHE", Path(temp)))
            stack.enter_context(patch.object(processing, "cache_ready", return_value=True))
            remote = stack.enter_context(
                patch.object(processing, "RangeFile", side_effect=SyntheticFile)
            )
            stack.enter_context(patch.object(processing, "crop", return_value=features))
            result = processing.process(area, scenes, "a" * 32, lambda text: None)
            self.assertEqual(len(result["acquisitions"]), 4)
            self.assertTrue((Path(temp) / ("a" * 32) / "change.tif").is_file())
            self.assertFalse(result["report"]["full_files_downloaded"])
            self.assertEqual(result["report"]["comparison_coverage_percent"], 100)
            self.assertEqual(result["report"]["candidate_new_water_km2"], 0)
            processing.process(area, scenes, "b" * 32, lambda text: None)
            self.assertEqual(remote.call_count, 4)

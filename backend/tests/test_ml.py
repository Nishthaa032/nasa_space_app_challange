"""Synthetic checks of label handling and leakage-resistant partitioning."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import rasterio
from rasterio.transform import from_origin

from src.train_ml import DATE_PAIRS, confident_labels, spatial_partitions, train, validate_classes


class MLDataTests(unittest.TestCase):
    def test_cloud_and_partial_water_are_not_negative_labels(self):
        for code in [2, 3, 4, 9, 10, 11, 20, 21, 254, 255]:
            values = np.full((9, 9), code, dtype=np.uint8)
            labels = confident_labels(values, values)
            self.assertTrue((labels == 255).all())

    def test_homogeneous_high_confidence_water_is_retained(self):
        water = np.ones((9, 9), dtype=np.uint8)
        labels = confident_labels(water, water)
        self.assertEqual(int((labels == 1).sum()), 49)

    def test_partitions_repeat_and_have_separation(self):
        split = spatial_partitions((483, 300))
        np.testing.assert_array_equal(split, spatial_partitions((483, 300)))
        self.assertEqual(set(np.unique(split)), {0, 1, 2, 255})
        for start in range(50, 480, 50):
            self.assertTrue((split[start - 3 : start + 3] == 255).all())

    def test_missing_class_stops_training(self):
        with self.assertRaises(ValueError):
            validate_classes(np.zeros(100, dtype=np.uint8), "test")

    def test_training_pipeline_on_explicitly_synthetic_data(self):
        """Exercise fitting/export without pretending synthetic scores are science results."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            radar_dir, labels_dir = root / "radar", root / "labels"
            radar_dir.mkdir()
            labels_dir.mkdir()
            (root / "data/manifests").mkdir(parents=True)
            rows, columns = np.indices((200, 250))
            truth = ((rows // 10 + columns // 10) % 2).astype(np.uint8)
            profile = dict(
                driver="GTiff",
                height=200,
                width=250,
                count=1,
                crs="EPSG:32654",
                transform=from_origin(430000, 3970000, 20, 20),
            )
            manifest = []
            for radar_date, optical_date in DATE_PAIRS.items():
                for pol, offset in [("HHHH", 0), ("HVHV", -5)]:
                    values = np.where(truth == 1, -20, -4).astype("float32") + offset
                    with rasterio.open(
                        radar_dir / f"{radar_date}_{pol}_dB.tif", "w", dtype="float32", **profile
                    ) as target:
                        target.write(values, 1)
                for band in ["B01_WTR", "B03_CONF"]:
                    name = f"synthetic_{optical_date}_{band}.tif"
                    manifest.append({"date": optical_date, "band": band, "filename": name})
                    with rasterio.open(labels_dir / name, "w", dtype="uint8", **profile) as target:
                        target.write(truth, 1)
            (root / "data/manifests/opera_downloads.json").write_text(json.dumps(manifest))
            with patch("src.train_ml.ROOT", root):
                result = train(labels_dir, radar_dir)
            self.assertEqual(result["status"], "trained")
            self.assertTrue((root / "models/random_forest.joblib").is_file())
            self.assertEqual(result["candidate_new_water_km2"], 0.0)
            self.assertEqual(len(result["validation_trials"]), 2)
            single_date = {
                "name": "synthetic_single_date",
                "manifest": "data/manifests/opera_downloads.json",
                "label_dates": {"20261008": "20261008"},
                "training_dates": ["20261008"],
            }
            with patch("src.train_ml.ROOT", root):
                result = train(labels_dir, radar_dir, single_date)
            self.assertIn(
                "not an independent temporal test",
                result["heldout_spatial_and_later_date_proxy_agreement"]["status"],
            )
            self.assertEqual(result["label_coverage"]["20260914"]["usable_label_pixels"], 0)


if __name__ == "__main__":
    unittest.main()

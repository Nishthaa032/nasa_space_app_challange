import unittest

import numpy as np

from src.clean_data import smooth_power
from src.model import detect, remove_small


class AnalysisTests(unittest.TestCase):
    def test_missing_centers_stay_missing(self):
        db = np.full((9, 9), -10.0, dtype=float)
        db[4, 4] = np.nan
        out = smooth_power(db)
        self.assertTrue(np.isnan(out[4, 4]))
        self.assertAlmostEqual(float(out[4, 3]), -10.0, places=5)

    def test_average_is_linear_power(self):
        db = np.zeros((3, 3))
        db[0, 0] = 10
        out = smooth_power(db, 3, 9)
        self.assertAlmostEqual(float(out[1, 1]), 10 * np.log10(2), places=5)

    def test_identical_dates_have_no_candidates(self):
        a = np.linspace(-25, 5, 100).reshape(10, 10)
        candidates, _ = detect(a, a, -12, minimum=1)
        self.assertFalse(candidates.any())

    def test_new_dark_patch_and_existing_water(self):
        before = np.full((12, 12), -5.0)
        after = before.copy()
        before[:3, :3] = -20
        after[:3, :3] = -20
        after[5:8, 5:8] = -20
        pred, _ = detect(before, after, -12, minimum=9)
        self.assertEqual(int(pred.sum()), 9)
        self.assertFalse(pred[:3, :3].any())

    def test_small_components_removed(self):
        a = np.zeros((10, 10), bool)
        a[1, 1] = True
        a[5:8, 5:8] = True
        self.assertEqual(int(remove_small(a, 9).sum()), 9)


if __name__ == "__main__":
    unittest.main()

import unittest

import numpy as np

from src.improve_model import errors, local_std, select_trial


class DevelopmentTests(unittest.TestCase):
    def test_selection_ignores_diagnostic_scores(self):
        trials = [
            {"model": "a", "validation": {"f1": 0.8, "precision": 0.7}, "diagnostic": 0.1},
            {"model": "b", "validation": {"f1": 0.7, "precision": 0.9}, "diagnostic": 0.99},
        ]
        self.assertEqual(select_trial(trials)["model"], "a")

    def test_constant_texture_and_missing_centers(self):
        values = np.full((9, 9), -12.0)
        values[4, 4] = np.nan
        result = local_std(values)
        self.assertTrue(np.isnan(result[4, 4]))
        self.assertAlmostEqual(float(result[4, 3]), 0.0, places=5)

    def test_error_codes(self):
        truth = np.array([[0, 1, 0, 1, 0]])
        prediction = np.array([[0, 1, 1, 0, 1]])
        valid = np.array([[True, True, True, True, False]])
        np.testing.assert_array_equal(errors(truth, prediction, valid), [[0, 1, 2, 3, 255]])


if __name__ == "__main__":
    unittest.main()

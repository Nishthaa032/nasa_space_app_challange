import unittest

import numpy as np

from src.adjacent_frame import average_power


class AdjacentFrameTests(unittest.TestCase):
    def test_average_linear_power(self):
        power = np.array([[1.0, 1.0], [1.0, 9.0]])
        result = average_power(power, np.ones((2, 2), bool), 2)
        self.assertEqual(result.shape, (1, 1))
        self.assertAlmostEqual(float(result[0, 0]), 3.0)

    def test_any_invalid_contributor_excludes_target(self):
        power = np.ones((2, 2))
        valid = np.array([[True, True], [False, True]])
        self.assertTrue(np.isnan(average_power(power, valid, 2)[0, 0]))

    def test_misaligned_shape_is_rejected(self):
        with self.assertRaises(ValueError):
            average_power(np.ones((3, 2)), np.ones((3, 2), bool), 2)


if __name__ == "__main__":
    unittest.main()

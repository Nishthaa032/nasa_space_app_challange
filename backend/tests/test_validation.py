import hashlib
import tempfile
import unittest
from pathlib import Path

from src.validate_frozen import verify_frozen_model
from src.validate_region import assert_separation


class FrozenModelTests(unittest.TestCase):
    def test_spatial_holdout_cannot_overlap_training(self):
        assert_separation([0, 3000, 100, 4000], [0, 0, 100, 1000], 2000)
        with self.assertRaises(ValueError):
            assert_separation([0, 900, 100, 1900], [0, 0, 100, 1000], 2000)

    def test_modified_model_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "model"
            path.write_bytes(b"original")
            digest = hashlib.sha256(b"original").hexdigest()
            self.assertEqual(verify_frozen_model(path, digest), digest)
            path.write_bytes(b"changed")
            with self.assertRaises(ValueError):
                verify_frozen_model(path, digest)


if __name__ == "__main__":
    unittest.main()

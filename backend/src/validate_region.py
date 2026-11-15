"""Prepare and evaluate the prospectively declared northern spatial holdout.

Only radar data are read during preparation. The region is fixed in the protocol
before any regional optical label extraction. No training or threshold tuning.
"""

import json
from pathlib import Path

import h5py
import numpy as np
from rasterio.transform import from_origin

from .clean_data import smooth_power
from .common import CONFIG, ROOT, read_raster, write_raster
from .validate_frozen import evaluate, verify_frozen_model


def assert_separation(bounds, training_bounds, gap):
    if bounds[1] - training_bounds[3] < gap:
        raise ValueError("Northern evaluation region does not respect the declared training gap")


def main() -> None:
    protocol = json.loads((ROOT / "configs/spatial_validation.json").read_text())
    verify_frozen_model(ROOT / protocol["model_path"], protocol["model_sha256"])
    bounds = protocol["bounds_epsg32654"]
    assert_separation(
        bounds, protocol["training_crop_bounds_epsg32654"], protocol["gap_from_training_m"]
    )
    storage = json.loads((ROOT / "configs/storage.json").read_text())
    source = next(
        Path(storage["nisar_dir"]).glob(f"NISAR*_118_D_071_2005_*_{protocol['radar_date']}T*.h5")
    )
    _, profile = read_raster(ROOT / "data/processed/20261008_HHHH_dB.tif")
    actual = profile["transform"]
    training_bounds = [
        actual.c,
        actual.f + profile["height"] * actual.e,
        actual.c + profile["width"] * actual.a,
        actual.f,
    ]
    if not np.allclose(training_bounds, protocol["training_crop_bounds_epsg32654"]):
        raise ValueError("Training extent differs from the declared protocol")
    left, bottom, right, top = bounds
    destination = ROOT / "data/spatial_validation"
    with h5py.File(source, "r") as file:
        group = file["science/LSAR/GCOV/grids/frequencyA"]
        if int(group["projection"][()]) != 32654:
            raise ValueError("Unexpected projection")
        x, y = group["xCoordinates"][:], group["yCoordinates"][:]
        expected_x = np.arange(left + 10, right, 20)
        expected_y = np.arange(top - 10, bottom, -20)
        columns = np.flatnonzero((x >= expected_x[0]) & (x <= expected_x[-1]))
        rows = np.flatnonzero((y <= expected_y[0]) & (y >= expected_y[-1]))
        if not np.array_equal(x[columns], expected_x) or not np.array_equal(y[rows], expected_y):
            raise ValueError("Regional raster does not match the expected pixel grid")
        window = (slice(rows[0], rows[-1] + 1), slice(columns[0], columns[-1] + 1))
        mask, exceptions = group["mask"][window], group["inputDataExceptionMask"][window]
        profile.update(
            width=len(columns), height=len(rows), transform=from_origin(left, top, 20, 20)
        )
        for polarization in ["HHHH", "HVHV"]:
            power = group[polarization][window]
            valid = (mask > 0) & (mask < 255) & (exceptions == 0) & np.isfinite(power) & (power > 0)
            db = np.full(power.shape, np.nan, dtype=np.float32)
            db[valid] = 10 * np.log10(power[valid])
            clean = smooth_power(db, CONFIG["window_pixels"], CONFIG["minimum_valid_neighbors"])
            write_raster(
                destination / f"{protocol['radar_date']}_{polarization}_dB.tif", clean, profile
            )
    report = evaluate(protocol, destination, "spatial_validation")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

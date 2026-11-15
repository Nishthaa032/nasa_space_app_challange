"""Crop additional SSD scenes to the existing grid and make exploratory ML maps."""

import json
from pathlib import Path

import h5py
import joblib
import numpy as np

from .clean_data import smooth_power
from .common import CONFIG, ROOT, read_raster, save_json, write_raster
from .train_ml import feature_stack


def main() -> None:
    storage = json.loads((ROOT / "configs/storage.json").read_text())
    scenes = json.loads((ROOT / "data/manifests/nisar_expansion.json").read_text())
    _, profile = read_raster(ROOT / "data/processed/20260914_HHHH_dB.tif")
    affine = profile["transform"]
    expected_x = affine.c + (np.arange(profile["width"]) + 0.5) * affine.a
    expected_y = affine.f + (np.arange(profile["height"]) + 0.5) * affine.e
    classifier = joblib.load(ROOT / "models/random_forest.joblib")["classifier"]
    records = []
    for scene in scenes:
        date = scene["date"][:10].replace("-", "")
        if date in [CONFIG["before"], CONFIG["event"], CONFIG["followup"]]:
            continue
        source = Path(storage["nisar_dir"]) / (scene["id"] + ".h5")
        with h5py.File(source, "r") as file:
            group = file["science/LSAR/GCOV/grids/frequencyA"]
            if int(group["projection"][()]) != profile["crs"].to_epsg():
                raise ValueError(f"Projection mismatch: {source.name}")
            x, y = group["xCoordinates"][:], group["yCoordinates"][:]
            columns = np.flatnonzero((x >= expected_x[0]) & (x <= expected_x[-1]))
            rows = np.flatnonzero((y <= expected_y[0]) & (y >= expected_y[-1]))
            if not np.array_equal(x[columns], expected_x) or not np.array_equal(
                y[rows], expected_y
            ):
                raise ValueError(f"Grid mismatch: {source.name}")
            window = (slice(rows[0], rows[-1] + 1), slice(columns[0], columns[-1] + 1))
            mask = group["mask"][window]
            exceptions = group["inputDataExceptionMask"][window]
            quality = (mask > 0) & (mask < 255) & (exceptions == 0)
            for polarization in ["HHHH", "HVHV"]:
                power = group[polarization][window]
                valid = quality & np.isfinite(power) & (power > 0)
                db = np.full(power.shape, np.nan, dtype=np.float32)
                db[valid] = 10 * np.log10(power[valid])
                name = f"{date}_{polarization}_dB.tif"
                write_raster(ROOT / "data/processed" / name, db, profile)
                cleaned = smooth_power(
                    db, CONFIG["window_pixels"], CONFIG["minimum_valid_neighbors"]
                )
                write_raster(ROOT / "data/cleaned" / name, cleaned, profile)
        features, _ = feature_stack(ROOT / "data/cleaned", date)
        usable = np.isfinite(features).all(axis=-1)
        prediction = np.full(usable.shape, 255, dtype=np.uint8)
        if usable.any():
            prediction[usable] = classifier.predict(features[usable])
        write_raster(ROOT / "outputs/ml" / f"{date}_surface_water.tif", prediction, profile, True)
        records.append(
            {
                "date": date,
                "source": str(source),
                "usable_percent": float(usable.mean() * 100),
                "status": "exploratory prediction; no independent labels for this date",
            }
        )
    save_json(ROOT / "reports/extra_dates.json", records)
    print(f"Prepared {len(records)} additional dates; outputs are exploratory, not validated.")


if __name__ == "__main__":
    main()

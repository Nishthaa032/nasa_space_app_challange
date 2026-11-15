"""Align the adjacent 10 m GCOV frame and evaluate the unchanged model.

The 10-to-20 m reduction averages calibrated linear power, never dB. A target
pixel is valid only when all four contributing native pixels pass quality checks.
The original frame-071 results and frozen model are preserved.
"""

import json
from pathlib import Path

import h5py
import numpy as np
from rasterio.transform import from_origin

from .clean_data import smooth_power
from .common import CONFIG, ROOT, read_raster, save_json, write_raster
from .validate_frozen import evaluate, verify_frozen_model
from .validate_region import assert_separation


def average_power(power: np.ndarray, valid: np.ndarray, factor: int) -> np.ndarray:
    """Aggregate complete aligned pixel blocks; exclude any invalid contributors."""
    if factor < 1 or power.shape != valid.shape:
        raise ValueError("Invalid aggregation factor or array shape")
    height, width = power.shape
    if height % factor or width % factor:
        raise ValueError("Native crop is not divisible by the target pixel factor")
    shape = (height // factor, factor, width // factor, factor)
    valid = valid & np.isfinite(power) & (power > 0)
    usable = valid.reshape(shape).all(axis=(1, 3))
    mean = np.where(valid, power, 0).astype(np.float64).reshape(shape).mean(axis=(1, 3))
    mean[~usable] = np.nan
    return mean.astype(np.float32)


def prepare(source: Path, bounds: list, destination: Path) -> dict:
    left, bottom, right, top = bounds
    _, profile = read_raster(ROOT / "data/processed/20261008_HHHH_dB.tif")
    profile.update(
        width=round((right - left) / 20),
        height=round((top - bottom) / 20),
        transform=from_origin(left, top, 20, 20),
    )
    result = {
        "source": str(source),
        "bounds_epsg32654": bounds,
        "target_spacing_m": 20,
        "bands": {},
    }
    with h5py.File(source, "r") as file:
        group = file["science/LSAR/GCOV/grids/frequencyA"]
        spacing = float(group["xCoordinateSpacing"][()])
        if (
            int(group["projection"][()]) != 32654
            or spacing not in [10, 20]
            or group["yCoordinateSpacing"][()] != -spacing
        ):
            raise ValueError("Unsupported CRS or native pixel spacing")
        factor = int(20 / spacing)
        x, y = group["xCoordinates"][:], group["yCoordinates"][:]
        columns = np.flatnonzero((x >= left) & (x < right))
        rows = np.flatnonzero((y > bottom) & (y <= top))
        if not np.array_equal(
            x[columns], np.arange(left + spacing / 2, right, spacing)
        ) or not np.array_equal(y[rows], np.arange(top - spacing / 2, bottom, -spacing)):
            raise ValueError("Native grid is not aligned to the target bounds")
        window = (slice(rows[0], rows[-1] + 1), slice(columns[0], columns[-1] + 1))
        mask = group["mask"][window]
        exception = group["inputDataExceptionMask"][window]
        quality = (mask > 0) & (mask < 255) & (exception == 0)
        result["native_spacing_m"] = spacing
        for polarization in ["HHHH", "HVHV"]:
            power = group[polarization][window]
            mean = average_power(power, quality, factor)
            db = np.full(mean.shape, np.nan, dtype=np.float32)
            valid = np.isfinite(mean) & (mean > 0)
            db[valid] = 10 * np.log10(mean[valid])
            clean = smooth_power(db, CONFIG["window_pixels"], CONFIG["minimum_valid_neighbors"])
            write_raster(destination / f"20261008_{polarization}_dB.tif", clean, profile)
            result["bands"][polarization] = {
                "valid_20m_percent": float(valid.mean() * 100),
                "valid_cleaned_percent": float(np.isfinite(clean).mean() * 100),
            }
    return result


def main() -> None:
    protocol = json.loads((ROOT / "configs/spatial_validation.json").read_text())
    storage = json.loads((ROOT / "configs/storage.json").read_text())
    verify_frozen_model(ROOT / protocol["model_path"], protocol["model_sha256"])
    assert_separation(
        protocol["bounds_epsg32654"],
        protocol["training_crop_bounds_epsg32654"],
        protocol["gap_from_training_m"],
    )
    source = next(
        Path(storage["nisar_dir"]).glob("NISAR_L2_PR_GCOV_032_118_D_070_4005_DHDH_A_20261008T*.h5")
    )
    regional = prepare(source, protocol["bounds_epsg32654"], ROOT / "data/adjacent_validation")
    overlap = prepare(
        source, protocol["training_crop_bounds_epsg32654"], ROOT / "data/adjacent_overlap"
    )
    comparison = {}
    for band in ["HHHH", "HVHV"]:
        original, _ = read_raster(ROOT / "data/cleaned" / f"20261008_{band}_dB.tif")
        adjacent, _ = read_raster(ROOT / "data/adjacent_overlap" / f"20261008_{band}_dB.tif")
        common = np.isfinite(original) & np.isfinite(adjacent)
        difference = adjacent[common] - original[common]
        comparison[band] = {
            "paired_pixels": int(common.sum()),
            "paired_area_km2": float(common.sum() * 0.0004),
            "median_adjacent_minus_original_db": float(np.median(difference))
            if difference.size
            else None,
            "difference_10_90_percentile_db": np.percentile(difference, [10, 90]).tolist()
            if difference.size
            else None,
        }
    audit = {
        "regional_preparation": regional,
        "overlap_preparation": overlap,
        "overlap_comparison": comparison,
        "normalization_fitted": False,
        "mode_note": "Adjacent frame 070 uses 4005_DHDH_A rather than frame 071's 2005_DHDH_M; native 10 m pixels averaged to 20 m in linear power. Mode difference remains a validation limitation.",
    }
    save_json(ROOT / "reports/adjacent_frame_audit.json", audit)
    report = evaluate(protocol, ROOT / "data/adjacent_validation", "adjacent_validation")
    report["source"] = str(source)
    report["limitations"].append(audit["mode_note"])
    report["evaluation_context"] = (
        "Same northern extent and frozen model; expanded coverage from a newly downloaded adjacent frame. Earlier limited-coverage result remains recorded."
    )
    save_json(ROOT / "reports/adjacent_validation.json", report)
    print(json.dumps({"coverage": regional, "overlap": comparison, "validation": report}, indent=2))


if __name__ == "__main__":
    main()

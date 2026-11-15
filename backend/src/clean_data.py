"""Quality masks are applied by src/preprocess.py; smooth power, not dB.

The 5x5 normalized box average is a simple baseline speckle reducer. It
blurs boundaries and is not an adaptive Lee filter or a change in pixel spacing.
Missing center pixels remain missing even if their neighbors are valid.
"""

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

from .common import CONFIG, ROOT, read_raster, save_json, write_raster


def smooth_power(db, window=5, minimum=20):
    if window % 2 != 1 or not 1 <= minimum <= window * window:
        raise ValueError("Use an odd window and a valid support count")
    valid = np.isfinite(db)
    power = np.zeros(db.shape, dtype=np.float64)
    power[valid] = 10.0 ** (db[valid] / 10.0)
    pad = window // 2
    sums = sliding_window_view(np.pad(power, pad), (window, window)).sum(axis=(-1, -2))
    counts = sliding_window_view(np.pad(valid.astype(np.uint8), pad), (window, window)).sum(
        axis=(-1, -2)
    )
    keep = valid & (counts >= minimum) & (sums > 0)
    result = np.full(db.shape, np.nan, dtype=np.float32)
    result[keep] = 10 * np.log10(sums[keep] / counts[keep])
    return result


def run():
    records = []
    for date in [CONFIG["before"], CONFIG["event"], CONFIG["followup"]]:
        for pol in ["HHHH", "HVHV"]:
            source = ROOT / "data/processed" / f"{date}_{pol}_dB.tif"
            db, profile = read_raster(source)
            cleaned = smooth_power(db, CONFIG["window_pixels"], CONFIG["minimum_valid_neighbors"])
            write_raster(ROOT / "data/cleaned" / source.name, cleaned, profile)
            records.append(
                {
                    "date": date,
                    "polarization": pol,
                    "input_valid_percent": float(np.isfinite(db).mean() * 100),
                    "output_valid_percent": float(np.isfinite(cleaned).mean() * 100),
                }
            )
    save_json(
        ROOT / "reports/cleaning.json",
        {
            "window_pixels": CONFIG["window_pixels"],
            "minimum_valid_neighbors": CONFIG["minimum_valid_neighbors"],
            "method": "normalized arithmetic mean in linear power; center validity preserved",
            "records": records,
        },
    )
    return records


if __name__ == "__main__":
    run()

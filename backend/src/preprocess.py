"""Create reproducible, quality-masked NISAR study-area crops and a preview.
Called by run_analysis.py; raw data are never modified.
"""

import json

import h5py
import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.transform import from_origin
from shapely.geometry import shape
from shapely.ops import transform, unary_union

from .common import CONFIG, ROOT
from .visualize_results import render_radar_preview


def run():
    """Crop and validate raw GCOV observations, then export diagnostic rasters."""
    output_dir = ROOT / "data" / "processed"
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = ROOT / "data" / "raw" if (ROOT / "data" / "raw").exists() else ROOT / "raw"
    reference = ROOT / CONFIG["reference"]
    if not reference.is_file():
        raise FileNotFoundError(f"Reference outline not found: {reference}")
    geo = json.loads(reference.read_text())
    project = Transformer.from_crs(4326, 32654, always_xy=True).transform
    outline = unary_union([transform(project, shape(f["geometry"])) for f in geo["features"]])
    left, bottom, right, top = outline.buffer(2000).bounds
    layers, records, grid = {}, [], None
    files = sorted(raw_dir.glob("NISAR*GCOV*.h5"))
    if not files:
        raise FileNotFoundError(f"No NISAR GCOV files found in {raw_dir}")
    for path in files:
        date = path.name.split("_")[11][:8]
        with h5py.File(path, "r") as f:
            g = f["science/LSAR/GCOV/grids/frequencyA"]
            if int(g["projection"][()]) != 32654:
                raise ValueError("This case study requires EPSG:32654 inputs")
            if g["xCoordinateSpacing"][()] != 20 or g["yCoordinateSpacing"][()] != -20:
                raise ValueError("This case study requires 20 m pixel spacing")
            x, y = g["xCoordinates"][:], g["yCoordinates"][:]
            cols = np.flatnonzero((x >= left) & (x <= right))
            rows = np.flatnonzero((y >= bottom) & (y <= top))
            if not len(cols) or not len(rows):
                raise ValueError(f"No study-area overlap: {path.name}")
            c0, c1, r0, r1 = cols[0], cols[-1] + 1, rows[0], rows[-1] + 1
            current_grid = (x[c0:c1], y[r0:r1])
            if grid is None:
                grid = current_grid
            elif not all(np.array_equal(a, b) for a, b in zip(grid, current_grid)):
                raise ValueError("Grids differ; reproject before differencing")
            affine = from_origin(x[c0] - 10, y[r0] + 10, 20, 20)
            mask = g["mask"][r0:r1, c0:c1]
            exceptions = g["inputDataExceptionMask"][r0:r1, c0:c1]
            quality = (mask > 0) & (mask < 255) & (exceptions == 0)
            for pol in ["HHHH", "HVHV"]:
                power = g[pol][r0:r1, c0:c1]
                valid = quality & np.isfinite(power) & (power > 0)
                db = np.full(power.shape, np.nan, dtype="float32")
                db[valid] = 10 * np.log10(power[valid])
                layers[(date, pol)] = db
                with rasterio.open(
                    output_dir / f"{date}_{pol}_dB.tif",
                    "w",
                    driver="GTiff",
                    height=db.shape[0],
                    width=db.shape[1],
                    count=1,
                    dtype="float32",
                    crs="EPSG:32654",
                    transform=affine,
                    nodata=np.nan,
                    compress="deflate",
                ) as dst:
                    dst.write(db, 1)
                records.append(
                    {
                        "date": date,
                        "polarization": pol,
                        "valid_percent": round(float(valid.mean() * 100), 2),
                        "shape": list(db.shape),
                        "source": path.name,
                    }
                )

    dates = sorted({d for d, p in layers})
    expected_dates = sorted(CONFIG[key] for key in ["before", "event", "followup"])
    if dates != expected_dates:
        raise ValueError(f"Expected dates {expected_dates}, found {dates}")
    change = layers[(dates[1], "HHHH")] - layers[(dates[0], "HHHH")]
    if not np.isfinite(change).any():
        raise ValueError("No valid common observations")
    with rasterio.open(
        output_dir / "20260914_to_20260926_HH_change_dB.tif",
        "w",
        driver="GTiff",
        height=change.shape[0],
        width=change.shape[1],
        count=1,
        dtype="float32",
        crs="EPSG:32654",
        transform=affine,
        nodata=np.nan,
        compress="deflate",
    ) as dst:
        dst.write(change, 1)

    render_radar_preview(
        layers, outline, affine, dates, change, output_dir / "radar_comparison.png"
    )
    report = {
        "reference": str(reference.relative_to(ROOT)),
        "buffer_m": 2000,
        "crs": "EPSG:32654",
        "pixel_spacing_m": 20,
        "grids_identical": True,
        "common_HH_valid_percent": round(float(np.isfinite(change).mean() * 100), 2),
        "layers": records,
        "limitations": [
            "No flood classification or accuracy claim",
            "GSI reference is September 25; event image is September 26",
            "No speckle filter or terrain/land-cover exclusion applied beyond product masks",
            "Baseline and follow-up conditions require interpretation",
        ],
    }
    (output_dir / "inspection_report.json").write_text(json.dumps(report, indent=2))
    return report

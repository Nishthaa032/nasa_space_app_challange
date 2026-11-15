"""Shared project paths and raster/JSON input-output helpers."""

import json
from pathlib import Path
from typing import Any

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[2]
CONFIG = json.loads((ROOT / "configs/baseline.json").read_text())


def read_raster(path: Path) -> tuple[np.ndarray, dict]:
    """Return band one and its geospatial metadata; close the file promptly."""
    with rasterio.open(path) as src:
        return src.read(1), src.profile


def write_raster(path: Path, values: np.ndarray, profile: dict, categorical: bool = False) -> None:
    """Write a compressed single-band raster with an explicit no-data value."""
    path.parent.mkdir(parents=True, exist_ok=True)
    opts = profile.copy()
    opts.update(
        driver="GTiff",
        count=1,
        compress="deflate",
        dtype="uint8" if categorical else "float32",
        nodata=255 if categorical else np.nan,
    )
    with rasterio.open(path, "w", **opts) as dst:
        dst.write(values.astype(opts["dtype"]), 1)


def save_json(path: Path, data: Any) -> None:
    """Write readable JSON, rejecting nonstandard NaN and infinity values."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, allow_nan=False))

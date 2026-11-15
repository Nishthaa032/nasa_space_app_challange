"""Export small georeferenced browser assets without exposing raw science files."""

import json
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image
from rasterio.warp import Resampling, calculate_default_transform, reproject

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "frontend/public/data"


def export(path, name, palette=None):
    with rasterio.open(ROOT / path) as src:
        data = src.read(1)
        valid = np.isfinite(data) & (data != src.nodata)
        transform, width, height = calculate_default_transform(
            src.crs, "EPSG:3857", src.width, src.height, *src.bounds
        )
        dest = np.full((height, width), -9999, dtype="float32")
        reproject(
            np.where(valid, data, -9999).astype("float32"),
            dest,
            src_transform=src.transform,
            src_crs=src.crs,
            src_nodata=-9999,
            dst_transform=transform,
            dst_crs="EPSG:3857",
            dst_nodata=-9999,
            resampling=Resampling.nearest,
        )
        from pyproj import Transformer

        project = Transformer.from_crs(3857, 4326, always_xy=True)
        coordinates = [
            project.transform(*(transform * p))
            for p in [(0, 0), (width, 0), (width, height), (0, height)]
        ]
        rgba = np.zeros((height, width, 4), dtype="uint8")
        if palette:
            for value, color in palette.items():
                rgba[dest == value] = color
        else:
            shade = (np.clip((dest + 25) / 30, 0, 1) * 210 + 30).astype("uint8")
            rgba[:, :, :3] = shade[:, :, None]
            rgba[:, :, 3] = np.where(dest != -9999, 230, 0)
        Image.fromarray(rgba).save(OUT / f"{name}.png")
        return {
            "url": f"/data/{name}.png",
            "coordinates": coordinates,
            "waterArea": round(
                float(np.sum(data == 1)) * abs(src.transform.a * src.transform.e) / 1e6, 3
            ),
            "validPercent": round(float(valid.mean()) * 100, 1),
        }


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    water = {1: (44, 226, 215, 240)}
    scenes = []
    for date in [
        "20260716",
        "20260821",
        "20260902",
        "20260914",
        "20260926",
        "20261008",
        "20261020",
    ]:
        scenes.append(
            {
                "date": date,
                "water": export(f"outputs/ml/{date}_surface_water.tif", date, water),
                "radar": export(f"data/cleaned/{date}_HHHH_dB.tif", f"{date}-radar"),
            }
        )
    result = {
        "scenes": scenes,
        "validation": {
            "water": export("outputs/adjacent_validation/prediction.tif", "validated-water", water),
            "reference": export(
                "outputs/adjacent_validation/reference.tif",
                "reference",
                {0: (132, 156, 171, 65), 1: (44, 226, 215, 240), 255: (18, 24, 34, 150)},
            ),
            "errors": export(
                "outputs/adjacent_validation/scored_errors.tif",
                "errors",
                {
                    1: (44, 226, 215, 200),
                    2: (255, 158, 93, 255),
                    3: (239, 99, 183, 255),
                    255: (18, 24, 34, 150),
                },
            ),
            "radar": export("data/adjacent_validation/20261008_HHHH_dB.tif", "validated-radar"),
            "metrics": json.loads((ROOT / "reports/adjacent_validation.json").read_text())[
                "metrics"
            ],
        },
    }
    (OUT / "manifest.json").write_text(json.dumps(result))
    report = json.loads((ROOT / "reports/adjacent_validation.json").read_text())
    for field in ["source", "input_sha256"]:
        report.pop(field, None)
    (OUT / "validation-report.json").write_text(json.dumps(report, indent=2))
    print("Exported seven dates and northern validation layers")


if __name__ == "__main__":
    main()

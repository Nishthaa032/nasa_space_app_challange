"""Descriptive agreement with an incomplete, one-day-earlier reference.

Do not interpret outside-reference pixels as verified dry ground. No headline
accuracy, precision, recall, or probability is claimed. Sensitivity is reported
for all predeclared settings; no best setting is selected using the reference.
"""

import csv
import json

from rasterio.features import rasterize, shapes
from rasterio.warp import transform_geom

from .common import CONFIG, ROOT, read_raster, save_json, write_raster
from .model import detect


def run():
    classes, profile = read_raster(ROOT / "outputs/water_change_classes.tif")
    geo = json.loads((ROOT / CONFIG["reference"]).read_text())
    projected = [
        transform_geom("EPSG:4326", profile["crs"], f["geometry"]) for f in geo["features"]
    ]
    reference = rasterize(
        [(g, 1) for g in projected],
        out_shape=classes.shape,
        transform=profile["transform"],
        all_touched=False,
    ).astype(bool)
    valid = classes != 255
    candidate = classes == 2
    ref_valid = reference & valid
    pixel_km2 = abs(profile["transform"].a * profile["transform"].e) / 1e6
    intersection = candidate & ref_valid

    def fraction(a, b):
        return float(a / b) if b else None

    report = {
        "comparison_type": "descriptive spatial overlap; not validated classification accuracy",
        "reference_date": "2026-09-25",
        "satellite_event_date": "2026-09-26",
        "pixel_area_km2": pixel_km2,
        "valid_area_km2": float(valid.sum() * pixel_km2),
        "candidate_new_open_water_km2": float(candidate.sum() * pixel_km2),
        "reference_area_in_crop_km2": float(reference.sum() * pixel_km2),
        "reference_area_with_valid_observations_km2": float(ref_valid.sum() * pixel_km2),
        "intersection_km2": float(intersection.sum() * pixel_km2),
        "candidate_area_outside_reference_km2": float((candidate & ~reference).sum() * pixel_km2),
        "fraction_of_candidate_area_inside_reference": fraction(
            intersection.sum(), candidate.sum()
        ),
        "fraction_of_valid_reference_area_detected": fraction(intersection.sum(), ref_valid.sum()),
        "intersection_over_union": fraction(intersection.sum(), (candidate | ref_valid).sum()),
        "reference_pixel_rule": "pixel center inside polygon",
        "limitations": [
            "Reference outline is an estimate and is one day earlier",
            "Outside-reference land is not verified dry",
            "Open-water detector can miss inundated vegetation and urban flooding",
            "Study crop was defined using reference geometry; results are local, not independent regional generalization",
            "No held-out labeled dataset or supervised ML model",
        ],
    }
    save_json(ROOT / "reports/reference_agreement.json", report)
    write_raster(ROOT / "outputs/reference_mask.tif", reference.astype("uint8"), profile, True)
    features = []
    for geometry, value in shapes(
        candidate.astype("uint8"), mask=candidate, transform=profile["transform"]
    ):
        features.append(
            {
                "type": "Feature",
                "properties": {"class": "candidate_new_open_water", "event_date": "2026-09-26"},
                "geometry": transform_geom(profile["crs"], "EPSG:4326", geometry),
            }
        )
    save_json(
        ROOT / "outputs/candidate_new_water.geojson",
        {"type": "FeatureCollection", "features": features},
    )
    before, _ = read_raster(ROOT / "data/cleaned" / f"{CONFIG['before']}_HHHH_dB.tif")
    after, _ = read_raster(ROOT / "data/cleaned" / f"{CONFIG['event']}_HHHH_dB.tif")
    params = json.loads((ROOT / "models/baseline_parameters.json").read_text())
    sensitivity = []
    for offset in [-2, 0, 2]:
        for decrease in [-2, -3, -4]:
            pred, _ = detect(
                before,
                after,
                params["intensity_threshold_db"] + offset,
                decrease,
                CONFIG["minimum_component_pixels"],
            )
            overlap = (pred & ref_valid).sum()
            sensitivity.append(
                {
                    "intensity_offset_db": offset,
                    "decrease_threshold_db": decrease,
                    "candidate_km2": float(pred.sum() * pixel_km2),
                    "fraction_inside_reference": fraction(overlap, pred.sum()),
                    "fraction_reference_detected": fraction(overlap, ref_valid.sum()),
                }
            )
    with (ROOT / "reports/threshold_sensitivity.csv").open("w") as f:
        writer = csv.DictWriter(f, fieldnames=list(sensitivity[0]))
        writer.writeheader()
        writer.writerows(sensitivity)
    return report


if __name__ == "__main__":
    run()

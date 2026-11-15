"""Evaluate the frozen development model on the predeclared August date.

No fitting, threshold selection or label-driven split changes occur here.
This is retrospective temporal-transfer agreement with optical proxy labels,
not cross-region or human-ground-truth validation.
"""

import hashlib
import json
from pathlib import Path

import joblib
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .common import ROOT, save_json, write_raster
from .improve_model import CONTEXT_NAMES, errors, local_std, terrain_features
from .train_ml import align_labels, confident_labels, feature_stack, score, spatial_partitions


def verify_frozen_model(path: Path, expected: str) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != expected:
        raise ValueError("Model differs from the frozen protocol. Evaluation stopped.")
    return digest


def draw_comparison(labels, prediction, error_map, evaluation, report, output):
    def font(size):
        try:
            return ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", size)
        except OSError:
            return ImageFont.truetype("DejaVuSans.ttf", size)

    canvas = Image.new("RGB", (1440, 1000), "#101827")
    draw = ImageDraw.Draw(canvas)
    draw.text((35, 25), "SARScope | Frozen-model evaluation", font=font(32), fill="white")
    draw.text(
        (35, 72),
        f"Radar: {report['radar_date']} | Optical reference: {report['optical_date']} | No retraining",
        font=font(22),
        fill="#b9c9db",
    )
    for index, (values, title) in enumerate(
        [
            (labels, "Clear optical proxy labels"),
            (prediction, "Frozen model prediction"),
            (error_map, "Scored pixels: disagreements"),
        ]
    ):
        x = 35 + index * 475
        draw.text((x, 125), title, font=font(22), fill="white")
        rgb = np.full((*values.shape, 3), [42, 52, 68], dtype=np.uint8)
        for code, color in {
            0: [175, 181, 190],
            1: [40, 140, 235],
            2: [245, 105, 55],
            3: [215, 70, 195],
        }.items():
            rgb[values == code] = color
        scale = min(360 / rgb.shape[1], 580 / rgb.shape[0])
        size = (round(rgb.shape[1] * scale), round(rgb.shape[0] * scale))
        canvas.paste(Image.fromarray(rgb).resize(size, Image.Resampling.NEAREST), (x, 170))
    metrics = report.get("metrics")
    if metrics:
        text = f"Water F1: {metrics['f1']:.3f}   Precision: {metrics['precision']:.3f}   Recall: {metrics['recall']:.3f}   IoU: {metrics['iou']:.3f}"
    else:
        text = "Insufficient usable reference pixels: no performance score reported."
    draw.text((35, 780), text, font=font(25), fill="white")
    draw.text(
        (35, 825),
        f"Scored: {int(evaluation.sum()):,} pixels ({report['scored_percent_of_crop']:.2f}% of crop) | No model or threshold changes",
        font=font(21),
        fill="#b9c9db",
    )
    draw.text(
        (35, 870),
        "Blue: water/agreement | Orange: false water | Magenta: missed water | Dark: excluded or missing",
        font=font(20),
        fill="#b9c9db",
    )
    draw.text(
        (35, 915),
        f"Optical proxy labels acquired about {report['acquisition_gap_hours']} hours earlier; not verified flood accuracy or broad regional validation.",
        font=font(19),
        fill="#ffdc41",
    )
    canvas.save(output / "comparison.png")


def evaluate(protocol: dict, radar_dir: Path, output_name: str) -> dict:
    storage = json.loads((ROOT / "configs/storage.json").read_text())
    model_path = ROOT / protocol["model_path"]
    digest = verify_frozen_model(model_path, protocol["model_sha256"])
    saved = joblib.load(model_path)
    if saved["feature_names"] != CONTEXT_NAMES:
        raise ValueError("Frozen model feature order differs from the declared context feature set")
    core, profile = feature_stack(radar_dir, protocol["radar_date"])
    dem = next(Path(storage["terrain_dir"]).glob("OPERA*B10_DEM.tif"))
    elevation, slope = terrain_features(dem, profile)
    features = np.concatenate(
        [
            core,
            local_std(core[..., 0])[..., None],
            local_std(core[..., 1])[..., None],
            elevation[..., None],
            slope[..., None],
        ],
        axis=-1,
    )
    paths = {
        band: Path(storage["opera_dir"]) / url.rsplit("/", 1)[1]
        for band, url in protocol["label_links"].items()
    }
    water = align_labels(paths["B01_WTR"], profile)
    confidence = align_labels(paths["B03_CONF"], profile)
    labels = confident_labels(water, confidence)
    usable = np.isfinite(features).all(axis=-1)
    partition = spatial_partitions(labels.shape)
    evaluation = usable & (labels != 255)
    if protocol["partition"] is not None:
        evaluation &= partition == protocol["partition"]
    counts = np.bincount(labels[evaluation], minlength=2)
    prediction = np.full(labels.shape, 255, dtype=np.uint8)
    prediction[usable] = (
        saved["classifier"].predict_proba(features[usable])[:, 1] >= saved["threshold"]
    )
    sufficient = counts.min() >= protocol["minimum_pixels_per_class"]
    report = {
        "status": "evaluated" if sufficient else "insufficient reference coverage",
        "radar_date": protocol["radar_date"],
        "optical_date": protocol["optical_date"],
        "model_sha256": digest,
        "threshold": saved["threshold"],
        "model_retrained": False,
        "threshold_changed": False,
        "partition": protocol["partition"],
        "scope": protocol.get("scope", "Same area, separate date; reserved geographic blocks"),
        "acquisition_gap_hours": protocol.get("acquisition_gap_hours", 32),
        "scored_class_counts_nonwater_water": counts.tolist(),
        "minimum_pixels_per_class": protocol["minimum_pixels_per_class"],
        "optical_class_counts_in_crop": {
            str(k): int(v) for k, v in zip(*np.unique(water, return_counts=True))
        },
        "usable_label_pixels_in_crop": int((labels != 255).sum()),
        "usable_label_percent_in_crop": float((labels != 255).mean() * 100),
        "finite_radar_feature_percent": float(np.isfinite(core).all(axis=-1).mean() * 100),
        "finite_terrain_feature_percent": float(
            (np.isfinite(elevation) & np.isfinite(slope)).mean() * 100
        ),
        "finite_all_feature_percent": float(usable.mean() * 100),
        "scored_percent_of_crop": float(evaluation.mean() * 100),
        "scored_area_km2": float(
            evaluation.sum() * abs(profile["transform"].a * profile["transform"].e) / 1e6
        ),
        "metrics": score(labels[evaluation], prediction[evaluation]) if sufficient else None,
        "input_sha256": {
            str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths.values()
        },
        "limitations": [
            "Single geographic area; not cross-region validation",
            f"Optical and radar acquisitions differ by about {protocol.get('acquisition_gap_hours', 32)} hours",
            "Optical labels are algorithmic proxies, not human-verified ground truth",
            "Same terrain context as training can favor persistent water geography",
            "Reference clear-pixel subset may not represent cloudy, mixed or vegetated areas",
            "Retrospective surface-water mapping experiment, not forecasting",
            "This evaluates surface water, not new inundation or flood depth",
        ],
    }
    output = ROOT / "outputs" / output_name
    error_map = errors(labels, prediction, evaluation)
    for name, array in [
        ("reference", labels),
        ("prediction", prediction),
        ("scored_errors", error_map),
    ]:
        write_raster(output / f"{name}.tif", array, profile, True)
    verify_frozen_model(model_path, digest)
    save_json(ROOT / "reports" / f"{output_name}.json", report)
    draw_comparison(labels, prediction, error_map, evaluation, report, output)
    return report


def main() -> None:
    protocol = json.loads((ROOT / "configs/next_validation.json").read_text())
    report = evaluate(protocol, ROOT / "data/cleaned", "temporal_validation")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

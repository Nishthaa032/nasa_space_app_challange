"""Analyze errors and compare supervised models without claiming a new test.

The original geographic test has been inspected. Its scores below are explicitly
development diagnostics. Selection uses the old validation blocks only; a new
date/region with usable labels is required for independent final evaluation.
"""

import csv
import json
from pathlib import Path

import joblib
import numpy as np
import rasterio
from PIL import Image, ImageDraw, ImageFont
from rasterio.warp import Resampling, reproject
from scipy.ndimage import distance_transform_edt, uniform_filter
from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier

from .common import ROOT, save_json, write_raster
from .train_ml import (
    align_labels,
    confident_labels,
    feature_stack,
    score,
    spatial_partitions,
    validate_classes,
)

CONTEXT_NAMES = [
    "HH_dB",
    "HV_dB",
    "HH_minus_HV_dB",
    "HH_local_std_dB",
    "HV_local_std_dB",
    "elevation_m",
    "slope_degrees",
]


def local_std(values: np.ndarray) -> np.ndarray:
    """3x3 standard deviation in dB, requiring seven finite neighbors.

    Combined with the earlier 5x5 smoother, the raw-input radius is three pixels.
    The existing six-pixel gaps between spatial blocks prevent overlap across splits.
    """
    valid = np.isfinite(values)
    support = uniform_filter(valid.astype(float), size=3, mode="constant")
    filled = np.where(valid, values, 0).astype(float)
    sums = uniform_filter(filled, size=3, mode="constant")
    squares = uniform_filter(filled * filled, size=3, mode="constant")
    result = np.full(values.shape, np.nan, dtype=np.float32)
    usable = valid & (support >= (7 / 9 - 1e-10))
    variance = squares[usable] / support[usable] - (sums[usable] / support[usable]) ** 2
    result[usable] = np.sqrt(np.maximum(variance, 0))
    return result


def terrain_features(path: Path, profile: dict) -> tuple[np.ndarray, np.ndarray]:
    """Align the NASA-distributed elevation layer and estimate local slope."""
    elevation = np.full((profile["height"], profile["width"]), np.nan, dtype=np.float32)
    with rasterio.open(path) as source:
        reproject(
            source=rasterio.band(source, 1),
            destination=elevation,
            src_transform=source.transform,
            src_crs=source.crs,
            src_nodata=source.nodata,
            dst_transform=profile["transform"],
            dst_crs=profile["crs"],
            dst_nodata=np.nan,
            resampling=Resampling.bilinear,
        )
    dy, dx = np.gradient(elevation, abs(profile["transform"].e), abs(profile["transform"].a))
    slope = np.degrees(np.arctan(np.hypot(dx, dy))).astype(np.float32)
    return elevation, slope


def select_trial(trials: list[dict]) -> dict:
    """Never use the former-test diagnostic to select a model or threshold."""
    return max(trials, key=lambda item: (item["validation"]["f1"], item["validation"]["precision"]))


def errors(reference: np.ndarray, prediction: np.ndarray, valid: np.ndarray) -> np.ndarray:
    result = np.full(reference.shape, 255, np.uint8)
    result[valid & (reference == 0) & (prediction == 0)] = 0
    result[valid & (reference == 1) & (prediction == 1)] = 1
    result[valid & (reference == 0) & (prediction == 1)] = 2
    result[valid & (reference == 1) & (prediction == 0)] = 3
    return result


def make_figure(labels, original_errors, selected_errors, partition, report):
    font_path = "/System/Library/Fonts/Supplemental/Arial.ttf"

    def font(size):
        try:
            return ImageFont.truetype(font_path, size)
        except OSError:
            return ImageFont.truetype("DejaVuSans.ttf", size)

    canvas = Image.new("RGB", (1500, 1060), "#101827")
    draw = ImageDraw.Draw(canvas)
    draw.text((35, 25), "SARScope | Model error analysis", font=font(32), fill="white")
    draw.text(
        (35, 72),
        "October 8, 2026 | Optical proxy labels | Previously inspected test is now development data",
        font=font(20),
        fill="#bac9d9",
    )
    palettes = [
        {0: (175, 181, 190), 1: (40, 140, 235)},
        {0: (175, 181, 190), 1: (40, 140, 235), 2: (245, 105, 55), 3: (215, 70, 195)},
    ]
    for index, (values, title) in enumerate(
        [
            (labels, "Optical reference (clear pixels)"),
            (original_errors, "Original model: disagreements"),
            (selected_errors, "Selected model: disagreements"),
        ]
    ):
        x = 35 + index * 495
        draw.text((x, 125), title, font=font(21), fill="white")
        rgb = np.full((*values.shape, 3), [42, 52, 68], np.uint8)
        for value, color in palettes[0 if index == 0 else 1].items():
            rgb[values == value] = color
        # A thin border identifies the former-test blocks without hiding their pixels.
        test = partition == 2
        interior = test.copy()
        for shift, axis in [(1, 0), (-1, 0), (1, 1), (-1, 1)]:
            interior &= np.roll(test, shift, axis)
        rgb[test & ~interior] = [255, 220, 65]
        image = Image.fromarray(rgb).resize((370, 596), Image.Resampling.NEAREST)
        canvas.paste(image, (x, 165))
    before = report["original_former_test_diagnostic"]
    after = report["selected_former_test_diagnostic"]
    draw.text(
        (35, 790),
        "Orange: predicted water / reference nonwater   |   Magenta: missed reference water",
        font=font(21),
        fill="white",
    )
    draw.text(
        (35, 827),
        "Yellow outlines: former test blocks   |   Dark slate: missing or excluded reference",
        font=font(21),
        fill="#ffdc41",
    )
    draw.text(
        (35, 877),
        f"Development water F1: {before['f1']:.3f} → {after['f1']:.3f}    Precision: {before['precision']:.3f} → {after['precision']:.3f}",
        font=font(27),
        fill="white",
    )
    draw.text(
        (35, 927),
        f"Selected on validation only: {report['selected']['model']} at score threshold {report['selected']['threshold']:.1f}",
        font=font(22),
        fill="#bac9d9",
    )
    draw.text(
        (35, 978),
        "This is a development comparison, not new independent accuracy. Cross-date and cross-region validation remain open.",
        font=font(20),
        fill="#bac9d9",
    )
    canvas.save(ROOT / "outputs/ml_development/error_comparison.png")


def main() -> None:
    config = json.loads((ROOT / "configs/development.json").read_text())
    storage = json.loads((ROOT / "configs/storage.json").read_text())
    manifest = json.loads((ROOT / "data/manifests/opera_alternatives.json").read_text())
    date = config["date"]
    core, profile = feature_stack(ROOT / "data/cleaned", date)
    files = {
        item["band"]: Path(storage["opera_dir"]) / item["filename"]
        for item in manifest
        if item["date"] == date
    }
    labels = confident_labels(
        align_labels(files["B01_WTR"], profile), align_labels(files["B03_CONF"], profile)
    )
    terrain_path = next(Path(storage["terrain_dir"]).glob("OPERA*B10_DEM.tif"))
    elevation, slope = terrain_features(terrain_path, profile)
    context = np.concatenate(
        [
            core,
            local_std(core[..., 0])[..., None],
            local_std(core[..., 1])[..., None],
            elevation[..., None],
            slope[..., None],
        ],
        axis=-1,
    )
    common = (labels != 255) & np.isfinite(context).all(axis=-1)
    partition = spatial_partitions(labels.shape)
    masks = {
        name: common & (partition == code)
        for name, code in [("train", 0), ("validation", 1), ("diagnostic", 2)]
    }
    for name, mask in masks.items():
        validate_classes(labels[mask], name)
    original = joblib.load(ROOT / "models/random_forest.joblib")["classifier"]
    predictors = {"original_rf": (original, core)}
    kwargs = dict(
        n_estimators=config["trees"],
        max_depth=config["max_depth"],
        min_samples_leaf=config["min_samples_leaf"],
        n_jobs=2,
        random_state=config["seed"],
    )
    for name, cls, features in [
        ("unweighted_rf", RandomForestClassifier, core),
        ("context_rf", RandomForestClassifier, context),
        ("context_extra_trees", ExtraTreesClassifier, context),
    ]:
        model = cls(**kwargs)
        model.fit(features[masks["train"]], labels[masks["train"]])
        predictors[name] = (model, features)
    trials = []
    for name, (classifier, features) in predictors.items():
        scores = classifier.predict_proba(features[masks["validation"]])[:, 1]
        for threshold in config["thresholds"]:
            trials.append(
                {
                    "model": name,
                    "threshold": threshold,
                    "validation": score(labels[masks["validation"]], scores >= threshold),
                }
            )
    selected = select_trial(trials)
    classifier, features = predictors[selected["model"]]
    selected_map = np.full(labels.shape, 255, np.uint8)
    original_map = np.full(labels.shape, 255, np.uint8)
    usable = np.isfinite(features).all(axis=-1)
    selected_map[usable] = classifier.predict_proba(features[usable])[:, 1] >= selected["threshold"]
    core_valid = np.isfinite(core).all(axis=-1)
    original_map[core_valid] = original.predict(core[core_valid])
    before = score(labels[masks["diagnostic"]], original_map[masks["diagnostic"]])
    after = score(labels[masks["diagnostic"]], selected_map[masks["diagnostic"]])
    fp = masks["diagnostic"] & (labels == 0) & (original_map == 1)
    distance_to_labeled_water = distance_transform_edt(labels != 1) * 20
    groups = np.indices(labels.shape)
    group_ids = (groups[0] // 50) * int(np.ceil(labels.shape[1] / 50)) + groups[1] // 50
    block_errors = []
    for group in np.unique(group_ids[masks["diagnostic"]]):
        mask = masks["diagnostic"] & (group_ids == group)
        block_errors.append(
            {
                "block": int(group),
                "pixels": int(mask.sum()),
                "reference_water": int((mask & (labels == 1)).sum()),
                "original_false_positives": int((fp & mask).sum()),
            }
        )
    block_errors.sort(key=lambda item: item["original_false_positives"], reverse=True)
    report = {
        "status": "development experiment complete; no new independent test",
        "config": config,
        "selected": selected,
        "validation_trials": trials,
        "partition_class_counts": {
            name: np.bincount(labels[mask], minlength=2).tolist() for name, mask in masks.items()
        },
        "original_former_test_diagnostic": before,
        "selected_former_test_diagnostic": after,
        "original_false_positives_within_60m_of_labeled_water": int(
            (fp & (distance_to_labeled_water <= 60)).sum()
        ),
        "diagnostic_block_errors": block_errors,
        "context_feature_names": CONTEXT_NAMES,
        "limitations": [
            "Former test was previously inspected and is now development data",
            "Optical labels are proxy estimates, not human truth",
            "DEM and related terrain may also influence OPERA labels; contextual gains can reflect shared ancillary bias",
            "Only one labeled date and one area",
            "No new temporal or cross-region validation",
            "All comparison metrics use the same finite-feature cohort",
            "Vote scores and selected threshold are not calibrated probabilities",
        ],
    }
    destination = ROOT / "outputs/ml_development"
    original_errors = errors(labels, original_map, common)
    selected_errors = errors(labels, selected_map, common)
    for name, values in [
        ("reference", labels),
        ("original_errors", original_errors),
        ("selected_errors", selected_errors),
        ("selected_water", selected_map),
    ]:
        write_raster(destination / f"{name}.tif", values, profile, True)
    joblib.dump(
        {
            "classifier": classifier,
            "threshold": selected["threshold"],
            "feature_names": CONTEXT_NAMES if features is context else CONTEXT_NAMES[:3],
            "status": "development_only",
        },
        ROOT / "models/development_model.joblib",
    )
    save_json(ROOT / "reports/model_development.json", report)
    with (ROOT / "reports/model_comparison.csv").open("w", newline="") as file:
        writer = csv.DictWriter(
            file, fieldnames=["model", "threshold", "precision", "recall", "f1", "iou"]
        )
        writer.writeheader()
        for trial in trials:
            writer.writerow(
                {
                    "model": trial["model"],
                    "threshold": trial["threshold"],
                    **{
                        key: trial["validation"][key]
                        for key in ["precision", "recall", "f1", "iou"]
                    },
                }
            )
    make_figure(labels, original_errors, selected_errors, partition, report)
    print(
        json.dumps(
            {
                "selected": selected,
                "original_diagnostic": before,
                "selected_diagnostic": after,
                "top_error_blocks": block_errors[:3],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

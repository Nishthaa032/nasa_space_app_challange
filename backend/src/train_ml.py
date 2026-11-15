"""Train and evaluate Random Forest using NASA OPERA optical proxy labels.

This learns surface water, not flood depth or a verified flood class. A change
map is derived by comparing predicted before/event water. Optical labels remain
algorithmic estimates with acquisition-time mismatch. GSI is not used here.
"""

import argparse
import json
import logging
from pathlib import Path

import joblib
import numpy as np
import rasterio
from numpy.lib.stride_tricks import sliding_window_view
from rasterio.warp import Resampling, reproject
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import confusion_matrix, f1_score, jaccard_score, precision_score, recall_score

from .common import ROOT, read_raster, save_json, write_raster

LOGGER = logging.getLogger(__name__)
DATE_PAIRS = {"20260914": "20260914", "20260926": "20260925", "20261008": "20261008"}
FEATURE_NAMES = ["HH_dB", "HV_dB", "HH_minus_HV_dB"]
RANDOM_SEED = 42


def feature_stack(radar_dir: Path, date: str) -> tuple[np.ndarray, dict]:
    """Build same-date radar features without reference information."""
    hh, profile = read_raster(radar_dir / f"{date}_HHHH_dB.tif")
    hv, other = read_raster(radar_dir / f"{date}_HVHV_dB.tif")
    if (
        hh.shape != hv.shape
        or profile["transform"] != other["transform"]
        or profile["crs"] != other["crs"]
    ):
        raise ValueError("HH and HV must share the same grid")
    return np.stack([hh, hv, hh - hv], axis=-1), profile


def align_labels(path: Path, profile: dict) -> np.ndarray:
    """Resample class codes by nearest neighbor; preserve no-data as 255."""
    result = np.full((profile["height"], profile["width"]), 255, dtype=np.uint8)
    with rasterio.open(path) as src:
        reproject(
            source=rasterio.band(src, 1),
            destination=result,
            src_transform=src.transform,
            src_crs=src.crs,
            src_nodata=255,
            dst_transform=profile["transform"],
            dst_crs=profile["crs"],
            dst_nodata=255,
            resampling=Resampling.nearest,
        )
    return result


def confident_labels(water: np.ndarray, confidence: np.ndarray) -> np.ndarray:
    """Use only matching unmasked nonwater / high-confidence open-water codes.

    All other classes are ignored, not assigned to nonwater. Keep only spatially
    homogeneous 3x3 neighborhoods to reduce mixed shore pixels and alignment noise.
    Nonwater is still an algorithmic proxy, potentially affected by ancillary masks.
    """
    labels = np.full(water.shape, 255, dtype=np.uint8)
    labels[(water == 0) & (confidence == 0)] = 0
    labels[(water == 1) & (confidence == 1)] = 1
    windows = sliding_window_view(np.pad(labels, 1, constant_values=255), (3, 3))
    homogeneous = (windows == labels[..., None, None]).all(axis=(-1, -2))
    labels[~homogeneous] = 255
    return labels


def spatial_partitions(shape: tuple[int, int], block: int = 50, margin: int = 3) -> np.ndarray:
    """Fixed 1 km blocks: 60/20/20 train/validation/test, with 120 m gaps.

    Assignment uses coordinates and a fixed seed, never labels or model scores.
    The same geographic partition is used for every date.
    """
    rows, cols = np.indices(shape)
    groups = (rows // block) * int(np.ceil(shape[1] / block)) + cols // block
    unique = np.unique(groups)
    if len(unique) < 10:
        raise ValueError("Need at least ten spatial blocks; expand the study area")
    rng = np.random.default_rng(RANDOM_SEED)
    rng.shuffle(unique)
    lookup = np.full(int(groups.max()) + 1, 2, dtype=np.uint8)
    train_end, val_end = int(len(unique) * 0.6), int(len(unique) * 0.8)
    lookup[unique[:train_end]] = 0
    lookup[unique[train_end:val_end]] = 1
    partition = lookup[groups]
    edge = (rows % block < margin) | (rows % block >= block - margin)
    edge |= (cols % block < margin) | (cols % block >= block - margin)
    partition[edge] = 255
    return partition


def score(y_true: np.ndarray, prediction: np.ndarray) -> dict:
    """Agreement with proxy labels, not independent real-world accuracy."""
    return {
        "pixels": int(len(y_true)),
        "confusion_matrix_nonwater_water": confusion_matrix(
            y_true, prediction, labels=[0, 1]
        ).tolist(),
        "precision": float(precision_score(y_true, prediction, zero_division=0)),
        "recall": float(recall_score(y_true, prediction, zero_division=0)),
        "f1": float(f1_score(y_true, prediction, zero_division=0)),
        "iou": float(jaccard_score(y_true, prediction, zero_division=0)),
    }


def validate_classes(labels: np.ndarray, name: str, minimum: int = 50) -> None:
    """Fail rather than train or report scores on unusable partitions."""
    counts = np.bincount(labels.astype(int), minlength=2)
    if len(counts) != 2 or counts.min() < minimum:
        raise ValueError(
            f"{name} needs at least {minimum} labels of each class; found {counts.tolist()}. Add clearer dates or a larger area."
        )


def train(labels_dir: Path, radar_dir: Path, experiment: dict = None) -> dict:
    experiment = experiment or {
        "name": "original_multidate_design",
        "manifest": "data/manifests/opera_downloads.json",
        "label_dates": DATE_PAIRS,
        "training_dates": ["20260914", "20260926"],
    }
    manifest = json.loads((ROOT / experiment["manifest"]).read_text())
    needed_dates = set(experiment["label_dates"].values())
    manifest = [item for item in manifest if item["date"] in needed_dates]
    missing = [x["filename"] for x in manifest if not (labels_dir / x["filename"]).is_file()]
    if missing:
        raise FileNotFoundError(
            f"Missing {len(missing)} NASA label files specified by the experiment manifest in {labels_dir}."
        )

    frames = {}
    coverage = {}
    first_profile = None
    for radar_date in DATE_PAIRS:
        optical_date = experiment["label_dates"].get(radar_date)
        features, profile = feature_stack(radar_dir, radar_date)
        if first_profile is not None and any(
            profile[k] != first_profile[k] for k in ["crs", "transform", "width", "height"]
        ):
            raise ValueError("Radar dates do not share the same pixel grid")
        first_profile = profile
        paths = {
            x["band"]: labels_dir / x["filename"] for x in manifest if x["date"] == optical_date
        }
        if optical_date is not None:
            labels = confident_labels(
                align_labels(paths["B01_WTR"], profile), align_labels(paths["B03_CONF"], profile)
            )
        else:
            labels = np.full(features.shape[:2], 255, dtype=np.uint8)
        valid = np.isfinite(features).all(axis=-1) & (labels != 255)
        frames[radar_date] = (features, labels, valid)
        coverage[radar_date] = {
            "optical_date": optical_date,
            "usable_label_pixels": int(valid.sum()),
            "usable_percent": float(valid.mean() * 100),
        }

    partition = spatial_partitions(frames["20260914"][1].shape)
    subsets = {}
    for name, split in [("train", 0), ("validation", 1), ("test", 2)]:
        xs, ys = [], []
        for date in experiment["training_dates"]:
            features, labels, valid = frames[date]
            selected = valid & (partition == split)
            xs.append(features[selected])
            ys.append(labels[selected])
        subsets[name] = (np.concatenate(xs), np.concatenate(ys))
        validate_classes(subsets[name][1], name)
    # Bound training memory without changing validation/test prevalence.
    train_x, train_y = subsets["train"]
    if len(train_y) > 100_000:
        take = np.random.default_rng(RANDOM_SEED).choice(len(train_y), 100_000, replace=False)
        train_x, train_y = train_x[take], train_y[take]
    trials = []
    best_model, best_f1 = None, -1.0
    for depth, leaf in [(12, 5), (None, 10)]:
        classifier = RandomForestClassifier(
            n_estimators=200,
            max_depth=depth,
            min_samples_leaf=leaf,
            class_weight="balanced_subsample",
            n_jobs=2,
            random_state=RANDOM_SEED,
        )
        classifier.fit(train_x, train_y)
        val_x, val_y = subsets["validation"]
        metrics = score(val_y, classifier.predict(val_x))
        trials.append(
            {"max_depth": depth, "min_samples_leaf": leaf, "validation_proxy_agreement": metrics}
        )
        if metrics["f1"] > best_f1:
            best_model, best_f1 = classifier, metrics["f1"]
    test_x, test_y = subsets["test"]
    test_metrics = score(test_y, best_model.predict(test_x))
    follow_x, follow_y, follow_valid = frames["20261008"]
    follow_mask = follow_valid & (partition == 2)
    follow_labels = follow_y[follow_mask]
    if "20261008" in experiment["training_dates"]:
        follow_metrics = {
            "status": "not an independent temporal test: October 8 is the training date"
        }
    elif len(follow_labels) and np.bincount(follow_labels, minlength=2).min() >= 50:
        follow_metrics = score(follow_labels, best_model.predict(follow_x[follow_mask]))
    else:
        follow_metrics = {
            "status": "insufficient clear labels of both classes in held-out blocks",
            "pixels": int(len(follow_labels)),
        }

    destination = ROOT / "outputs/ml"
    predictions = {}
    for date, (features, _, _) in frames.items():
        valid = np.isfinite(features).all(axis=-1)
        prediction = np.full(valid.shape, 255, dtype=np.uint8)
        prediction[valid] = best_model.predict(features[valid])
        predictions[date] = prediction
        write_raster(destination / f"{date}_surface_water.tif", prediction, profile, True)
    before, event = predictions["20260914"], predictions["20260926"]
    paired = (before != 255) & (event != 255)
    change = np.full(before.shape, 255, dtype=np.uint8)
    change[paired] = ((before[paired] == 0) & (event[paired] == 1)).astype(np.uint8)
    write_raster(destination / "candidate_new_water.tif", change, profile, True)
    write_raster(destination / "spatial_partitions.tif", partition, profile, True)
    model_path = ROOT / "models/random_forest.joblib"
    model_path.parent.mkdir(exist_ok=True)
    joblib.dump({"classifier": best_model, "feature_names": FEATURE_NAMES}, model_path)
    report = {
        "model": "RandomForestClassifier",
        "target": "surface water using NASA optical proxy labels",
        "status": "trained",
        "experiment": experiment,
        "label_coverage": coverage,
        "training_pixels": len(train_y),
        "feature_names": FEATURE_NAMES,
        "validation_trials": trials,
        "heldout_spatial_test_proxy_agreement": test_metrics,
        "heldout_spatial_and_later_date_proxy_agreement": follow_metrics,
        "feature_importances": dict(zip(FEATURE_NAMES, best_model.feature_importances_.tolist())),
        "candidate_new_water_km2": float(
            (change == 1).sum() * abs(profile["transform"].a * profile["transform"].e) / 1e6
        ),
        "limitations": [
            "Not human-verified ground truth",
            "Single study area; no cross-region test",
            "Label and radar acquisitions differ in time; consult experiment configuration",
            "Predictions on dates without labels are exploratory, not validated temporal transfer",
            "Unmasked nonwater labels may include ancillary masking effects",
            "Maps include training/validation regions; only reserved blocks contribute to test scores",
            "Not calibrated probabilities or operational flood warnings",
        ],
    }
    save_json(ROOT / "reports/ml_training.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--labels-dir", type=Path, default=ROOT / "data/raw/opera")
    parser.add_argument("--radar-dir", type=Path, default=ROOT / "data/cleaned")
    parser.add_argument(
        "--experiment", type=Path, help="JSON experiment defining training dates and label manifest"
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        experiment = json.loads(args.experiment.read_text()) if args.experiment else None
        report = train(args.labels_dir, args.radar_dir, experiment)
    except (FileNotFoundError, ValueError) as error:
        parser.exit(2, f"Training not started: {error}\n")
    LOGGER.info(
        "Training complete. Read reports/ml_training.json for held-out proxy-label agreement."
    )
    LOGGER.info("Model: %s", report["model"])


if __name__ == "__main__":
    main()

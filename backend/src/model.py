"""Unsupervised threshold baseline; no supervised classifier is trained.

Otsu threshold uses pooled before/event HH measurements, never the GSI
reference. Candidate new water must be dark after, brighter before, and
decrease by at least the configured dB threshold. Low-backscatter baseline
pixels are only a water proxy, NOT verified permanent water.
"""

from collections import deque

import numpy as np

from .common import CONFIG, ROOT, read_raster, save_json, write_raster


def otsu(values):
    values = np.asarray(values)
    values = values[np.isfinite(values)]
    if values.size < 2 or np.ptp(values) == 0:
        raise ValueError("Need varying finite intensities for Otsu")
    hist, edges = np.histogram(values, bins=256)
    centers = (edges[:-1] + edges[1:]) / 2
    weights = np.cumsum(hist.astype(float))
    means = np.cumsum(hist * centers)
    den = weights * (weights[-1] - weights)
    score = np.full(256, -np.inf)
    good = den > 0
    score[good] = (means[-1] * weights[good] - means[good] * weights[-1]) ** 2 / den[good]
    return float(centers[np.argmax(score)])


def remove_small(mask, minimum=9):
    """Keep 8-connected components with at least minimum pixels."""
    seen = np.zeros(mask.shape, bool)
    out = np.zeros(mask.shape, bool)
    height, width = mask.shape
    for r, c in zip(*np.nonzero(mask)):
        if seen[r, c]:
            continue
        seen[r, c] = True
        queue = deque([(r, c)])
        component = []
        while queue:
            y, x = queue.popleft()
            component.append((y, x))
            for dy in [-1, 0, 1]:
                for dx in [-1, 0, 1]:
                    yy, xx = y + dy, x + dx
                    if 0 <= yy < height and 0 <= xx < width and mask[yy, xx] and not seen[yy, xx]:
                        seen[yy, xx] = True
                        queue.append((yy, xx))
        if len(component) >= minimum:
            yy, xx = zip(*component)
            out[yy, xx] = True
    return out


def detect(before, after, threshold, change_threshold=-3, minimum=9):
    valid = np.isfinite(before) & np.isfinite(after)
    candidate = (
        valid & (before >= threshold) & (after < threshold) & ((after - before) <= change_threshold)
    )
    return remove_small(candidate, minimum), valid


def run():
    before, profile = read_raster(ROOT / "data/cleaned" / f"{CONFIG['before']}_HHHH_dB.tif")
    after, profile2 = read_raster(ROOT / "data/cleaned" / f"{CONFIG['event']}_HHHH_dB.tif")
    assert (
        profile["crs"] == profile2["crs"]
        and profile["transform"] == profile2["transform"]
        and before.shape == after.shape
    )
    threshold = otsu(np.concatenate([before.ravel(), after.ravel()]))
    candidate, valid = detect(
        before, after, threshold, CONFIG["change_threshold_db"], CONFIG["minimum_component_pixels"]
    )
    classes = np.zeros(before.shape, np.uint8)
    classes[valid & (before < threshold) & (after < threshold)] = 1
    classes[valid & (before < threshold) & (after >= threshold)] = 3
    classes[candidate] = 2
    classes[~valid] = 255
    write_raster(ROOT / "outputs/water_change_classes.tif", classes, profile, True)
    write_raster(
        ROOT / "outputs/cleaned_HH_change_dB.tif", np.where(valid, after - before, np.nan), profile
    )
    fitted = {
        "method": "Otsu intensity gate plus temporal decrease and component filtering",
        "supervised_training": False,
        "reference_used_to_fit": False,
        "intensity_threshold_db": threshold,
        "change_threshold_db": CONFIG["change_threshold_db"],
        "minimum_component_pixels": CONFIG["minimum_component_pixels"],
        "classes": {
            "0": "Other valid / unclassified",
            "1": "Low backscatter on both dates (water proxy)",
            "2": "Candidate new open water",
            "3": "Baseline-dark to event-bright (recession proxy)",
            "255": "No usable paired observation",
        },
        "limitations": [
            "Not flood depth or prediction",
            "No calibrated probability",
            "No DEM or land-cover exclusion",
            "HV cleaned and exported but not used in this baseline",
            "Otsu assumes a useful intensity separation; scene-specific threshold needs scrutiny",
        ],
    }
    save_json(ROOT / "models/baseline_parameters.json", fitted)
    return fitted


if __name__ == "__main__":
    run()

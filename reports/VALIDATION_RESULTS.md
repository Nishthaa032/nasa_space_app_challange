# Frozen-model validation results

## Latest outcome
The newly downloaded October 8 adjacent NISAR frame resolves the radar coverage
gap in the fixed northern evaluation area. The Random Forest and its 0.5 decision
threshold were unchanged. The model fingerprint was verified before evaluation.

| Measure | Result |
|---|---:|
| Scored area within the 100 km² rectangle | 78.5452 km² |
| Scored pixels | 196,363 |
| Reference-water pixels | 3,540 |
| Water precision | 0.9247 |
| Water recall | 0.9506 |
| Water F1 | 0.9375 |
| Water IoU | 0.8823 |

| Reference class | Predicted nonwater | Predicted water |
|---|---:|---:|
| Nonwater | 192,549 | 274 |
| Water | 175 | 3,365 |

## What was fixed before evaluation
The 10 × 10 km rectangle is north of the training crop with a 2 km separation.
The spatial protocol was fixed before inspecting its labels. This evaluation
expands coverage within that same rectangle; it does not select a new test area
or tune the model after observing the earlier limited-coverage result.

Frozen model SHA-256:
`b3f9b8d6c76701c299a305605e25fa09465fe1c7857594a76d066bf972547aba`.

## Adjacent-frame preparation
Frame 070 uses mode 4005_DHDH_A and native 10 m spacing, whereas the original
frame 071 uses 2005_DHDH_M at 20 m. Calibrated linear power was averaged on the
aligned 20 m grid, requiring all four native contributors to pass quality masks.
The existing 5 × 5 linear-power smoothing and feature pipeline were then applied.
No fitted normalization or model retraining was performed.

Over the original crop, 143,331 paired pixels show median adjacent-minus-original
HH and HV differences of +0.277 and +0.235 dB respectively. These are diagnostics,
not proof of interchangeable sensor modes. All-feature coverage in the northern
rectangle is 98.4064%; usable optical labels cover 79.2508%. Their intersection
provides the scored area above.

## Earlier checks retained
- August 21 radar / August 20 optical: inconclusive. Reserved blocks have 19,045
  nonwater pixels but only 18 water pixels, below the predeclared minimum of 50
  per class. No performance metric is published; boundaries were not relaxed.
  Optical data precede radar by about 32 hours.
- October 8 frame 071: F1 0.789 over just 0.5564 km² of the same northern
  rectangle. Limited radar coverage motivated obtaining frame 070. This result
  remains in `reports/spatial_validation.json`.
- Development comparison: F1 0.916 on an already-inspected development test.
  This remains a development diagnostic, not an independent validation score.

## Interpretation and limitations
The latest result supports local surface-water mapping on one date. It does not
establish flood-change accuracy, flood depth, forecasting, or transfer across
other regions or events. Optical reference labels are algorithmic estimates,
not human-verified ground truth, and precede radar by about eight hours. Only
clear, high-confidence, homogeneous water/nonwater labels are scored; cloudy,
mixed and vegetated areas may behave differently. Terrain context can favor
persistent water geography and share ancillary biases with the reference.
Neighboring pixels are correlated and do not constitute independent events.
The acquisition-mode difference remains a limitation even after grid alignment.

## Artifacts and reproduction
- `outputs/adjacent_validation/comparison.png`: reference, prediction and errors.
- `outputs/adjacent_validation/`: georeferenced reference, prediction and error rasters.
- `reports/adjacent_validation.json`: full metrics, coverage and provenance.
- `reports/adjacent_frame_audit.json`: input preparation and overlap diagnostics.
- `reports/temporal_validation.json`, `reports/spatial_validation.json`: earlier checks.
- `configs/spatial_validation.json`: fixed northern evaluation protocol.

```sh
PYTHONPATH=backend .venv/bin/python -m src.adjacent_frame
.venv/bin/PYTHONPATH=backend python -m unittest discover -s backend/tests -v
```

The next product milestone is an interactive map with date selection, radar and
predicted-water layers, a comparison view, and visible coverage/limitations.
The currently available data are sufficient for that first prototype. Further
scientific validation should use separately held-out events with suitable labels.

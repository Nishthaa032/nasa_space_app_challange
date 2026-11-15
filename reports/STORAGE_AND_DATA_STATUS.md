# Storage and data status — November 10, 2026

Raw files are archived with SHA-256 verification to external storage (`data/archive/raw/`).
Subfolders: `nisar` (radar), `opera` (water/confidence), `terrain` (DEM), `reference` (GSI).
Copies retain original names. Source downloads and project raw files are retained.
Code and generated outputs stay in the Mac project. See data/manifests/ssd_inventory.json after copy completion.

## Training blocker
All six original OPERA water/confidence TIFFs open and cover the study coordinates, but their crop contains no usable class 0/1 confident labels. September 14 and October 8 are all no-data (255); September 25 contains class 253 and no-data. See optical_label_quality.json. No supervised model has been trained on these data. Catalog footprint/date compatibility did not guarantee useful pixels.

## Additional data
DOWNLOAD_MORE.md lists four new NISAR dates (about 5.8 GB) and four small alternative optical-label candidate files. Extra radar dates improve temporal context, but do not create independent flood events. Optical candidates still need inspection before training.

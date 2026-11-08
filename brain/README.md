# brain/: how the v2.3 predictions are built

Run everything with `FONECTA_KIT=/path/to/FONECTA_CONNECT_SUGGESTS_2026 bash brain/train.sh` (about 25 min).
The file names come from the build order; every file below is used by train.sh or imported by a file that is.

| Step | Files | What it does |
|---|---|---|
| 1. Features and caches | `cache.py` → base rows and candidates (`model.py`, `features.py`); `cache2.py` → owner habits, activity and holiday reviews (`features_x.py` with `reviews_x.py`); `cache3.py` → Poisson closed-day evidence (`an_llr.py`); `cache4.py` → weekend-hours candidates (`extra2.py`); `cache5.py` → extra kit data (`extra4.py`); `cache6.py` → owner diligence (`extra5.py`) | Each reads the kit once per season and saves one feature table to /tmp/fonecta_brain |
| | `te.py` | Fold-safe segment statistics, built inside each training fold |
| 2. Training sets | `v2.py` (`prep`) | Three training sets: base, base + kit extras, base + owner diligence |
| 3. Models, out-of-fold | `v2.py`, `v3.py` (scoring via `harness.py`, which calls the kit's evaluate.py) | Five calibrated models (gradient boosting, LightGBM), 5-fold by business |
| 4. Ensemble | `ens.py` | Averages the five, writes outputs/cv_dev_2026.csv and outputs/cv_backtest_2025.csv (committed copies in receipts/) |
| 5. Final model | `final3.py` | Trains on all businesses, writes predictions_2026.csv, predictions_2026_explained.csv and report.json |

#!/bin/bash
# Rebuilds the v2.2 brain (dev 65.1 / back-test 63.0) and predictions_2026.csv from Fonecta's kit.
# Usage, from the repo root:  FONECTA_KIT=/path/to/FONECTA_CONNECT_SUGGESTS_2026 bash brain/train.sh
# Intermediate caches go to /tmp/t403_*.pkl. Needs a few GB of RAM.
set -eo pipefail
: "${FONECTA_KIT:?set FONECTA_KIT to the starter kit folder}"
ROOT=$(cd "$(dirname "$0")/.." && pwd)
PY=${PYTHON:-$ROOT/.venv/bin/python}
export LOKY_MAX_CPU_COUNT=${LOKY_MAX_CPU_COUNT:-4}
cd "$ROOT/brain"
echo "[1/4] v1 features (model.py) and caches"; $PY model.py >/dev/null
$PY cache.py; $PY cache2.py; $PY cache3.py; $PY cache4.py
echo "[2/4] three calibrated models, out-of-fold"
REPREP=1 CAL=1 TAG=h1cal $PY v2.py | grep -E "OOF" || true
CAL=1 TAG=h1calc CPX='{"max_iter":800,"learning_rate":0.03,"max_leaf_nodes":63,"min_samples_leaf":30}' $PY v2.py | grep -E "OOF" || true
CAL=1 TAG=v3hcal $PY v3.py | grep -E "^v3" || true
echo "[3/4] ensemble -> outputs/cv_dev_2026.csv, outputs/cv_backtest_2025.csv"
WRITE=1 FLAGQ=-1 $PY ens.py h1cal,h1calc,v3hcal | tail -3
(cd "$FONECTA_KIT" && $PY evaluation/evaluate.py --predictions "$ROOT/outputs/cv_dev_2026.csv" | grep Score)
(cd "$FONECTA_KIT" && $PY evaluation/evaluate.py --predictions "$ROOT/outputs/cv_backtest_2025.csv" --labels labels/dev_labels_2025_backtest.csv | grep Score)
echo "[4/4] final model on all businesses -> predictions_2026.csv"
THR_CLOSED=0.1 THR_OPEN=-0.1 $PY final2.py | grep -E "predictions_2026" || true
echo DONE

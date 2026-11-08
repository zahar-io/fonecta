#!/bin/bash
# Rebuilds the v2.3 brain (dev 65.45 / back-test 63.50) and predictions_2026.csv from Fonecta's kit.
# Usage, from the repo root:  FONECTA_KIT=/path/to/FONECTA_CONNECT_SUGGESTS_2026 bash brain/train.sh
# Intermediate caches go to /tmp/fonecta_brain/. Needs a few GB of RAM; about 25 min on an M-series Mac Mini.
set -eo pipefail
: "${FONECTA_KIT:?set FONECTA_KIT to the starter kit folder}"
ROOT=$(cd "$(dirname "$0")/.." && pwd)
PY=${PYTHON:-$ROOT/.venv/bin/python}
export LOKY_MAX_CPU_COUNT=${LOKY_MAX_CPU_COUNT:-4}
C='{"max_iter":800,"learning_rate":0.03,"max_leaf_nodes":63,"min_samples_leaf":30}'
B=/tmp/fonecta_brain; G="OOF|^v3"
cd "$ROOT/brain"; mkdir -p $B "$ROOT/outputs"
echo "[1/5] features and caches"
$PY cache.py; $PY cache2.py; $PY cache3.py; $PY cache4.py; $PY cache5.py >/dev/null; $PY cache6.py >/dev/null
echo "[2/5] three training sets: base (r3), base + kit extras (r4), base + owner diligence (dd)"
prep() { DPKL=$1 XC=$2 XD=$3 $PY -c "import os,pickle,v2; pickle.dump((v2.prep(2026),v2.prep(2025)),open(os.environ['DPKL'],'wb'))"; }
prep $B/D.pkl 0 0; prep $B/D_r4.pkl 1 0; prep $B/Dd.pkl 0 1
echo "[3/5] five calibrated models, out-of-fold"
DPKL=$B/Dd.pkl XC=0 XD=1 CAL=1 TAG=dd_cal $PY v2.py | grep -E "$G" || true
DPKL=$B/Dd.pkl XC=0 XD=1 CAL=1 TAG=dd_calc CPX="$C" $PY v2.py | grep -E "$G" || true
DPKL=$B/D.pkl XC=0 XD=0 CAL=1 SM=lgb TAG=lgb_cal $PY v2.py | grep -E "$G" || true
DPKL=$B/D_r4.pkl XC=1 XD=0 CAL=1 TAG=r4v3cal $PY v3.py | grep -E "$G" || true
DPKL=$B/D.pkl XC=0 XD=0 CAL=1 TAG=v3hcal $PY v3.py | grep -E "$G" || true
echo "[4/5] ensemble -> outputs/cv_dev_2026.csv, outputs/cv_backtest_2025.csv"
DPKL=$B/D.pkl WRITE=1 FLAGQ=-1 $PY ens.py dd_calc,r4v3cal,v3hcal,lgb_cal,dd_cal | tail -3
(cd "$FONECTA_KIT" && $PY evaluation/evaluate.py --predictions "$ROOT/outputs/cv_dev_2026.csv" | grep Score)
(cd "$FONECTA_KIT" && $PY evaluation/evaluate.py --predictions "$ROOT/outputs/cv_backtest_2025.csv" --labels labels/dev_labels_2025_backtest.csv | grep Score)
echo "[5/5] final model on all businesses -> predictions_2026.csv + predictions_2026_explained.csv (read by the app)"
THR_CLOSED=0 THR_OPEN=-0.1 $PY final3.py | grep -E "predictions_2026" || true
echo DONE

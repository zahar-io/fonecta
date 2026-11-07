#!/bin/zsh
cd ~/fonecta-T403/brain
PY=~/fonecta/.venv/bin/python
export LOKY_MAX_CPU_COUNT=8
K=/Users/zahar/zahar-setup/tg-bot/work/T334/pack/Fonecta_SinceAI2026/inner/FONECTA_CONNECT_SUGGESTS_2026
WRITE=1 FLAGQ=-1 $PY ens.py h1cal,h1calc,v3hcal 2>&1 | tail -3
$PY $K/evaluation/evaluate.py --predictions ../outputs/cv_dev_2026.csv | sed -n 2,10p
$PY $K/evaluation/evaluate.py --predictions ../outputs/cv_backtest_2025.csv --labels $K/labels/dev_labels_2025_backtest.csv | sed -n 2,10p
THR_CLOSED=0.1 THR_OPEN=-0.1 $PY final2.py 2>&1 | grep -E "^\[|predictions_2026|Traceback|Error"
$PY $K/evaluation/evaluate.py --predictions ../predictions_2026.csv > /dev/null && echo FORMAT_OK
echo DONE

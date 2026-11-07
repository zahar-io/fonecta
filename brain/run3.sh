#!/bin/zsh
# round 3 pipeline, detached: survives a session restart. Log: /tmp/t403_run3.log
cd ~/fonecta-T403/brain
PY=~/fonecta/.venv/bin/python
export LOKY_MAX_CPU_COUNT=4
cp /tmp/t403_D.pkl /tmp/t403_D_r2.pkl
$PY cache4.py
REPREP=1 CAL=1 TAG=h1cal $PY v2.py 2>&1 | grep -E "OOF|correct_sil"
CAL=1 TAG=h1calc CPX='{"max_iter":800,"learning_rate":0.03,"max_leaf_nodes":63,"min_samples_leaf":30}' $PY v2.py 2>&1 | grep -E "OOF|correct_sil" &
CAL=1 TAG=v3hcal $PY v3.py 2>&1 | grep -E "^v3|correct_sil" &
wait
FLAGQ=-1 $PY ens.py h1cal,h1calc,v3hcal 2>&1 | tail -1
FLAGQ=-1 $PY ens.py h1cal,h1calc,v3hcal,g1cal,g1calc,v3cal 2>&1 | tail -1
echo DONE

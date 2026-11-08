"""Shared building blocks of the brain: one feature row per (business, special day) with its hours candidates
(build), the dev labels (labels) and the 3-way state target (y_state). Training and prediction live in v2.py / v3.py /
ens.py / final3.py; run everything with brain/train.sh."""
from __future__ import annotations

import csv
import json
import os
from datetime import date

import numpy as np
import pandas as pd

from features import KIT, Builder, D

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CAT = ["cc", "seg", "key", "tier"]
CAND_ORDER = ["mall", "ly1", "ps1", "ly2", "ps2", "peer_special", "reg_open_peer_close"]


def build(season):
    b = Builder(season)
    tf = D("evaluation", "targets_2026.csv" if season == 2026 else "targets_2025_backtest.csv")
    rows, meta = [], []
    for r in csv.DictReader(open(tf, encoding="utf-8")):
        d = date.fromisoformat(r["date"])
        f, cands, shown, reg = b.row(r["entity_id"], d, r["day_key"])
        rows.append(f)
        meta.append({"entity_id": r["entity_id"], "date": r["date"], "key": r["day_key"], "split": r["split"],
                     "cands": cands, "shown": shown, "flag": b.bl.explain(r["entity_id"], d, r["day_key"])[0] == "FLAG"})
    X = pd.DataFrame(rows)
    for c in CAT:
        X[c] = X[c].astype("category")
    return b, X, meta


def labels(season):
    p = os.path.join(KIT, "labels", "dev_labels_2026.csv" if season == 2026 else "dev_labels_2025_backtest.csv")
    return {(r["entity_id"], r["date"]): r for r in csv.DictReader(open(p, encoding="utf-8"))}


def y_state(lab, shown):
    t = lab["truth_hours"]
    if t == "closed":
        return 0
    return 1 if t == shown else 2  # 1 SAME, 2 OTHER_OPEN

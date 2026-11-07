"""Train and predict. Usage:
    python model.py                 # 5-fold by entity on dev 2026, writes cv report + outputs/predictions_2026_v1.csv
Outputs: outputs/predictions_2026_v1.csv (scorer format) + outputs/predictions_2026_explained.csv (basis + reasons, read by the app) and brain/report.json
"""
from __future__ import annotations

import csv
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import date

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.model_selection import GroupKFold

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


def fit(X, y):
    m = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.06, max_leaf_nodes=31,
                                       categorical_features="from_dtype", random_state=0)
    m.fit(X, y)
    return m


def cand_stats(meta_idx, meta, L):
    """Per candidate source: how often it equals the truth when the truth is open and differs from shown."""
    hit, tot = Counter(), Counter()
    for i in meta_idx:
        m = meta[i]
        lab = L.get((m["entity_id"], m["date"]))
        if not lab or lab["truth_hours"] in ("closed", m["shown"]):
            continue
        for k, v in m["cands"].items():
            if v == "closed":
                continue
            tot[k] += 1
            hit[k] += v == lab["truth_hours"]
    return {k: (hit[k] + 1) / (tot[k] + 2) for k in tot}


def decide(p, m, cs, thr):
    """p = [P(closed), P(same), P(other)]. Returns action, hours, confidence, basis."""
    if m["flag"]:
        return "FLAG", "", 0.9, "CLOSED_SIGNALS"
    shown = m["shown"]
    best = ("NO_ACTION", "", float(p[1]), None, 0.0)
    if shown != "closed":
        ev = p[0] - (p[1] + p[2])
        if ev > thr["closed"]:
            best = ("SUGGEST", "closed", float(p[0]), "STATE_MODEL", ev)
    opts = [(cs.get(k, 0.0), k, v) for k, v in m["cands"].items() if v not in ("closed", shown)]
    if opts:
        q, k, v = max(opts)
        # +1 exact, ~+0.3 same-state otherwise; -0.5 needless; -1 wrong state (if truth closed and shown open
        # the open suggestion is still wrong state)
        ev = p[2] * (q + (1 - q) * 0.3) - p[1] * 0.5 - p[0] * 1.0
        if ev > max(best[4], thr["open"]):
            best = ("SUGGEST", v, float(p[2] * q), k.upper(), ev)
    return best[:4]


def main():
    thr = {"closed": float(os.environ.get("THR_CLOSED", 0.2)), "open": float(os.environ.get("THR_OPEN", 0.3))}
    b, X, meta = build(2026)
    L = labels(2026)
    dev = [i for i, m in enumerate(meta) if (m["entity_id"], m["date"]) in L]
    y = np.array([y_state(L[(meta[i]["entity_id"], meta[i]["date"])], meta[i]["shown"]) for i in dev])
    groups = [meta[i]["entity_id"] for i in dev]
    oof = np.zeros((len(dev), 3))
    oof_cs = {}
    for tr, te in GroupKFold(n_splits=5).split(dev, y, groups):
        m = fit(X.iloc[[dev[i] for i in tr]], y[tr])
        oof[te] = m.predict_proba(X.iloc[[dev[i] for i in te]])
        cs = cand_stats([dev[i] for i in tr], meta, L)
        for i in te:
            oof_cs[i] = cs
    os.makedirs(os.path.join(ROOT, "outputs"), exist_ok=True)
    cvp = os.path.join(ROOT, "outputs", "cv_dev_2026.csv")
    with open(cvp, "w", newline="", encoding="utf-8") as g:
        w = csv.writer(g)
        w.writerow(["entity_id", "date", "action", "hours", "confidence"])
        for j, i in enumerate(dev):
            a, h, c, _ = decide(oof[j], meta[i], oof_cs[j], thr)
            if a != "NO_ACTION":
                w.writerow([meta[i]["entity_id"], meta[i]["date"], a, h, round(c, 3)])
    # final model on all dev, predict everything
    mfull = fit(X.iloc[dev], y)
    csf = cand_stats(dev, meta, L)
    P = mfull.predict_proba(X)
    out = os.path.join(ROOT, "outputs", "predictions_2026_v1.csv")  # the submitted root file is v2.2 (brain/train.sh)
    expl = os.path.join(ROOT, "outputs", "predictions_2026_explained.csv")
    with open(out, "w", newline="", encoding="utf-8") as g, open(expl, "w", newline="", encoding="utf-8") as g2:
        w, w2 = csv.writer(g), csv.writer(g2)
        w.writerow(["entity_id", "date", "action", "hours", "confidence"])
        w2.writerow(["entity_id", "date", "day_key", "action", "hours", "confidence", "basis", "shown", "p_closed",
                     "p_same", "p_other", "candidates_json"])
        for i, m in enumerate(meta):
            a, h, c, basis = decide(P[i], m, csf, thr)
            if a != "NO_ACTION":
                w.writerow([m["entity_id"], m["date"], a, h, round(c, 3)])
            w2.writerow([m["entity_id"], m["date"], m["key"], a, h, round(c, 3), basis, m["shown"],
                         *[round(float(x), 3) for x in P[i]], json.dumps(m["cands"], ensure_ascii=False)])
    json.dump({"cand_precision": csf, "thr": thr}, open(os.path.join(HERE, "report.json"), "w"), indent=1)
    print("cv file:", cvp)
    print("predictions:", out)


if __name__ == "__main__":
    main()

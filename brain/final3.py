"""T415 v2.3 production run: the 5-model calibrated ensemble picked in T415 (brain/post.py):
  dd_cal  = v2 state model on round-3 data + owner diligence (extra5.py), candidate model B
  dd_calc = same state model, larger candidate model C
  r4v3cal = v3 (fold-safe label statistics) on round-3 data + round-4 kit data (extra4.py)
  v3hcal  = v3 on round-3 data
  lgb_cal = v2 with a LightGBM state model on round-3 data, candidate model B
Probabilities are the mean of the 5; each hours candidate is averaged over the models that scored it (ens.py).
Trained on every dev business; thresholds from the 2025 back-test out-of-fold sweep (THR_CLOSED, THR_OPEN).
Writes predictions_2026.csv + outputs/predictions_2026_v23_explained.csv (the ops app keeps reading the v1 file from model.py)."""
import os, json, csv, pickle, collections, time
import numpy as np, pandas as pd
import harness as H, model as M, v2, v3, te as TEm
from sklearn.ensemble import HistGradientBoostingRegressor as HR
thr = {'closed': float(os.environ["THR_CLOSED"]), 'open': float(os.environ["THR_OPEN"])}
B = {"max_iter": 300, "learning_rate": 0.06, "max_leaf_nodes": 31}
C = {"max_iter": 800, "learning_rate": 0.03, "max_leaf_nodes": 63, "min_samples_leaf": 30}
KW = dict(categorical_features="from_dtype", random_state=0)
DATA = {"r3": ("/tmp/fonecta_brain/D.pkl", "0", "0"), "dd": ("/tmp/fonecta_brain/Dd.pkl", "0", "1"), "r4": ("/tmp/fonecta_brain/D_r4.pkl", "1", "0")}
def load(name):
    p, xc, xd = DATA[name]; os.environ["XC"] = xc; os.environ["XD"] = xd
    D6, _ = pickle.load(open(p, 'rb')); X, meta, L, dev = H.load(2026)
    assert list(X.columns) == list(D6['X'].columns), name
    return D6, X, meta, L, dev
def cats(a, b):
    for c in M.CAT:
        a[c] = a[c].astype(str).astype("category"); b[c] = pd.Categorical(b[c].astype(str), categories=a[c].cat.categories)
Ps = []; byrow = collections.defaultdict(lambda: collections.defaultdict(list)); meta0 = None
def run_v2(name, sm, cands):
    global meta0
    D6, X, meta, L, dev = load(name); meta0 = meta0 or meta
    os.environ["SM"] = sm
    y = D6['y']; g = np.array([meta[i]['entity_id'] for i in dev]); allidx = list(range(len(meta)))
    Xtr = D6['X'].iloc[dev].copy(); Xa = X.copy(); cats(Xtr, Xa)
    m = v2.state_model().fit(Xtr, y); P = v2.calibrate(Xtr, y, g, m.predict_proba(Xa))
    Cc, keys = v2.cand_table(X, meta, allidx); Z = v2.cand_X(Cc, X)
    pos = {i: j for j, i in enumerate(dev)}; msk = y[[pos[r] for r in D6['crow']]] == 2
    for cpx in cands:
        Za, Zb = v2.align(D6['Z'][msk].reset_index(drop=True), Z); cats(Za, Zb)
        ec = HR(**cpx, **KW).fit(Za, D6['tp'][msk]).predict(Zb)
        for (i, h), e in zip(keys, ec): byrow[i][h].append(e)
        Ps.append(P)
    print(name, sm, 'done', len(cands), flush=True)
def run_v3(name):
    os.environ["SM"] = "hgb"
    D6, X, meta, L, dev = load(name)
    y = D6['y']; g = np.array([meta[i]['entity_id'] for i in dev]); allidx = list(range(len(meta)))
    rows, info = TEm.load_rows(2026, L, X, meta, dev); te = TEm.TE(rows, info, set(g))
    rinfo = {i: v3.info_of(X, meta, i) for i in allidx}
    Xtr, Ztr, ktr, _ = v3.fold_tables(D6, te, dev, rinfo)
    Xall, Zall, kall, _ = v3.fold_tables({'X': X, 'meta': meta}, te, allidx, rinfo)
    cats(Xtr, Xall)
    m = v2.state_model().fit(Xtr, y); Ps.append(v2.calibrate(Xtr, y, g, m.predict_proba(Xall)))
    yrow = {i: y[j] for j, i in enumerate(dev)}; msk = np.array([yrow[i] == 2 for i, h in ktr])
    Za, Zb = v2.align(Ztr[msk].reset_index(drop=True), Zall); cats(Za, Zb)
    ec = HR(**B, **KW).fit(Za, v3.pts_of(D6, [ktr[j] for j in np.where(msk)[0]])).predict(Zb)
    for (i, h), e in zip(kall, ec): byrow[i][h].append(e)
    print(name, 'v3 done', flush=True)
t = time.time()
run_v2("dd", "hgb", (B, C))      # dd_cal + dd_calc
run_v2("r3", "lgb", (B,))        # lgb_cal
run_v3("r4")                     # r4v3cal
run_v3("r3")                     # v3hcal
assert len(Ps) == 5
P = np.mean(Ps, 0); meta = meta0
br = {i: [(np.mean(v), h) for h, v in d.items()] for i, d in byrow.items()}
PRI = ["ly1", "ly2", "mall", "ps1", "ps2", "rev_close", "peer_special"]
def basis_of(m, h):
    src = [k for k, v in m['cands'].items() if v == h]
    for k in PRI:
        if k in src: return k.upper()
    return "PATTERN"
out = os.path.join(M.ROOT, "predictions_2026.csv"); expl = os.path.join(M.ROOT, "outputs", "predictions_2026_v23_explained.csv")
n = collections.Counter()
with open(out, "w", newline="", encoding="utf-8") as g, open(expl, "w", newline="", encoding="utf-8") as g2:
    w, w2 = csv.writer(g), csv.writer(g2)
    w.writerow(["entity_id", "date", "action", "hours", "confidence"])
    w2.writerow(["entity_id", "date", "day_key", "action", "hours", "confidence", "basis", "shown", "p_closed", "p_same", "p_other", "candidates_json"])
    for i, m in enumerate(meta):
        a, h, c, basis, ev = v2.decide2(P[i], m, br.get(i, []), thr)
        if basis == "CAND": basis = basis_of(m, h)
        n[(a, basis)] += 1
        if a != "NO_ACTION": w.writerow([m["entity_id"], m["date"], a, h, round(c, 3)])
        w2.writerow([m["entity_id"], m["date"], m["key"], a, h, round(c, 3), basis or "", m["shown"], *[round(float(x), 3) for x in P[i]], json.dumps(m["cands"], ensure_ascii=False)])
json.dump({"model": "v2.3 (T415): calibrated 5-model ensemble (dd_cal, dd_calc, lgb_cal, r4v3cal, v3hcal)", "thr": thr,
           "counts": {f"{k[0]}:{k[1]}": v for k, v in n.items()}}, open(os.path.join(M.HERE, "report.json"), "w"), indent=1)
print(n.most_common()); print(out, round(time.time() - t))

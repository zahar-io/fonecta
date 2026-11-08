"""Extra features: owner-level habit across all special days, last season's activity on the whole
holiday cluster vs a stable autumn baseline, entries already made for this season, seasonal flags.
All from data stamped before the snapshot."""
from collections import defaultdict
from datetime import date, timedelta
import numpy as np, pandas as pd
from baseline import cycle
XMAS = {"DEC23","XMAS_EVE","XMAS_DAY","BOXING_DAY","INTERDAY","NYE","NEW_YEARS_DAY","EPIPHANY_EVE","EPIPHANY"}

def extra(b, meta):
    bl = b.bl; snap = b.snap; si = snap.isoformat()
    # owner entries before snapshot, by entity -> list of (date, key, value)
    keyof = {}
    for r in bl.cal: keyof[(r["country"], r["date"])] = r["day_key"]
    ent_entries = defaultdict(list)
    for (eid, ds), rows in bl.hol.items():
        rr = [x for x in rows if x["entered_at"] < si]
        if not rr: continue
        h = max(rr, key=lambda x: x["entered_at"])["holidayHours"]
        v = "REG" if h.get("isRegularHours") else ("closed" if h.get("isClosed") or not h.get("openIntervals") else "open")
        ent_entries[eid].append((date.fromisoformat(ds), v))
    # analytics baseline: median act per weekday over Oct 1 - Nov 30 of each cycle year
    base = {}
    def ratio(eid, p, col="act"):
        g = b.an.get(eid)
        if g is None: return np.nan
        k = (eid, p.year if p.month >= 2 else p.year - 1, col)
        if k not in base:
            y = k[1]; w = g.loc[(g.index >= pd.Timestamp(y, 10, 1)) & (g.index < pd.Timestamp(y, 12, 1)), col]
            base[k] = w.groupby(w.index.weekday).median().to_dict() if len(w) else {}
        bb = base[k].get(p.weekday()); ts = pd.Timestamp(p)
        if bb is None or ts not in g.index: return np.nan
        return (g.loc[ts, col] + 0.5) / (bb + 0.5)
    # activity in the last 60 days vs the same weeks a year earlier (closed for good -> collapse)
    coll = {}
    S = pd.Timestamp(snap)
    for eid, g in b.an.items():
        r = g.loc[(g.index >= S - pd.Timedelta(days=62)) & (g.index < S), "act"].mean()
        q = g.loc[(g.index >= S - pd.Timedelta(days=427)) & (g.index < S - pd.Timedelta(days=307)), "act"].mean()
        coll[eid] = r / (q + 0.1) if q == q and r == r else np.nan
    # 2025 pilot decisions (sent before the snapshot): owner rejected / accepted the suggestion for that key last season
    import csv as _csv, os as _os
    from features import D as _D
    pil = {}
    for r in _csv.DictReader(open(_D("data", "pilot_decision_log_2025.csv"), encoding="utf-8")):
        if r["sent_at"] < si:
            pil[(r["entity_id"], r["day_key"])] = r
    import reviews_x as RX
    rv = RX.build(_D("data", "reviews.json"), snap)
    out = []
    cache = {}
    for m in meta:
        eid = m["entity_id"]; d = date.fromisoformat(m["date"]); cyc = cycle(d); key = m["key"]
        e = bl.ents[eid]; cc = e["meta"]["countryCode"]
        f = {}
        ce = cache.get((eid, cyc))
        if ce is None:
            ee = ent_entries.get(eid, [])
            prev = [v for (x, v) in ee if cycle(x) == cyc - 1]
            allp = [v for (x, v) in ee if x < snap]
            prevx = [v for (x, v) in ee if cycle(x) == cyc - 1 and keyof.get((cc, x.isoformat())) in XMAS]
            # activity over last season's xmas cluster
            rs = []
            for r in bl.cal:
                if r["country"] == cc and r["day_key"] in XMAS:
                    x = date.fromisoformat(r["date"])
                    if cycle(x) == cyc - 1:
                        rs.append(ratio(eid, x))
            rs = [x for x in rs if x == x]
            ce = {"o_prev_n": len(prev), "o_prev_closed": np.mean([v == "closed" for v in prev]) if prev else np.nan,
                  "o_prev_open": np.mean([v == "open" for v in prev]) if prev else np.nan,
                  "o_all_closed": np.mean([v == "closed" for v in allp]) if allp else np.nan,
                  "o_prevx_closed": np.mean([v == "closed" for v in prevx]) if prevx else np.nan,
                  "an_x_mean": np.mean(rs) if rs else np.nan, "an_x_min": np.min(rs) if rs else np.nan,
                  "an_x_low": np.mean([x < 0.35 for x in rs]) if rs else np.nan}
            cache[(eid, cyc)] = ce
        f.update(ce)
        now = [v for (x, v) in ent_entries.get(eid, []) if cycle(x) == cyc and x != d]
        f["o_now_n"] = len(now); f["o_now_closed"] = np.mean([v == "closed" for v in now]) if now else np.nan
        for back in (1, 2):
            ps = b.prev_dates(cc, key, d, back)
            rr = [ratio(eid, p) for p in ps]; rr = [x for x in rr if x == x]
            f[f"an_k{back}_min"] = min(rr) if rr else np.nan
            f[f"an_k{back}_mean"] = np.mean(rr) if rr else np.nan
            rc = [ratio(eid, p, "GOOGLE_PHONE_CALLS") for p in ps]; rc = [x for x in rc if x == x]
            f[f"an_kc{back}"] = np.mean(rc) if rc else np.nan
            rp = [ratio(eid, p, "PROFILE_VIEWS") for p in ps]; rp = [x for x in rp if x == x]
            f[f"an_kp{back}"] = np.mean(rp) if rp else np.nan
        f["act_collapse"] = coll.get(eid, np.nan)
        p = pil.get((eid, key))
        f["pil_dec"] = {"ACCEPTED": 1, "EDITED": 2, "REJECTED": 3, "NO_RESPONSE": 4}.get(p["decision"], 0) if p else 0
        f["pil_sug_closed"] = int(p["suggested_hours"] == "closed") if p else -1
        f["pil_final_closed"] = int(p["final_hours"] == "closed") if p and p["final_hours"] else -1
        cyc_now = cycle(d); rl = rv.get((eid, key), [])
        for back in (1, 2):
            ll = [x for x in rl if x[0] == cyc_now - back]
            f[f"rv_closed{back}"] = sum(1 for x in ll if x[1] == "closed")
            f[f"rv_open{back}"] = sum(1 for x in ll if x[1] == "open")
            f[f"rv_early{back}"] = sum(1 for x in ll if x[1] == "early")
        ee = [x for x in sorted(rl) if x[1] == "early" and x[0] < cyc_now]
        f["rv_early_min"] = ee[-1][2] if ee else np.nan
        f["reopen"] = int(bool(e.get("hours", {}).get("reopenDate")))
        f["reg_closed_days"] = sum(1 for k in range(7) if bl.regular(eid, d + timedelta(days=k)) == "closed")
        out.append(f)
    return pd.DataFrame(out)

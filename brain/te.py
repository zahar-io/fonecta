"""Fold-safe label statistics. Built only from businesses in the training fold: their labels for the
season and their dev truth history before that season's snapshot. Never from the business being scored."""
import csv, os, collections
from features import KIT, span
SNAP = {2026: "2026-11-06", 2025: "2025-11-06"}

def load_rows(season, L, X, meta, dev):
    """[(eid, level keys, truth, shown)] for every labelled row we may learn from, any entity."""
    info = {}
    for i in dev:
        m = meta[i]; x = X.iloc[i]
        info[m["entity_id"]] = (m["entity_id"][:2], str(x["seg"]), str(x["tier"]))
    rows = []
    for i in dev:
        m = meta[i]; lab = L[(m["entity_id"], m["date"])]
        rows.append((m["entity_id"], m["key"], lab["truth_hours"], m["shown"]))
    for r in csv.DictReader(open(os.path.join(KIT, "labels", "dev_truth_history.csv"), encoding="utf-8")):
        if r["date"] < SNAP[season] and r["entity_id"] in info:
            rows.append((r["entity_id"], r["day_key"], r["truth_hours"], r["displayed_hours_that_day"]))
    return rows, info

def delta(truth, shown):
    s, t = span(shown), span(truth)
    if not s or not t: return None
    return (t[0] - s[0], t[1] - s[1])

class TE:
    def __init__(self, rows, info, ents):
        """ents: entities allowed (training fold)."""
        self.c = collections.defaultdict(collections.Counter)      # level -> state counts
        # inner folds: a training row only sees stats from the other 4/5 of the training businesses
        # (leave-one-out leaks the label inversely through the subtraction)
        self.gof = {e: (sum(map(ord, e)) * 7919) % 5 for e in ents}
        self.e = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))  # group -> level -> counts
        self._cache = {}
        for eid, key, t, sh in rows:
            if eid not in ents: continue
            cc, seg, tier = info[eid]
            st = "closed" if t == "closed" else ("same" if t == sh else "other")
            feats = [("st", st)]
            if st == "other":
                d = delta(t, sh)
                if d: feats.append(("d", d))
                feats.append(("a", t))
                tt = span(t)
                if tt: feats += [("ac", tt[1] % 1440), ("ao", tt[0])]
            for lv in self.levels(cc, seg, tier, key):
                for f in feats:
                    self.c[lv][f] += 1
                    self.e[self.gof[eid]][lv][f] += 1

    @staticmethod
    def levels(cc, seg, tier, key):
        return [("L1", cc, seg, key), ("L2", seg, key), ("L3", cc, tier, key)]

    def get(self, eid, lv):
        g = self.gof.get(eid)
        k = (g, lv)
        if k not in self._cache:
            c = self.c.get(lv, collections.Counter())
            own = self.e.get(g, {}).get(lv) if g is not None else None
            if own:
                c = collections.Counter({x: n * 1.25 for x, n in (c - own).items()})  # rescale 4/5 -> full
            self._cache[k] = c
        return self._cache[k]

    def state_feats(self, eid, cc, seg, tier, key):
        f = {}
        for lv in self.levels(cc, seg, tier, key):
            c = self.get(eid, lv); n = c[("st", "closed")] + c[("st", "same")] + c[("st", "other")]
            k = lv[0]
            f[f"te_{k}_n"] = n
            for s in ("closed", "same", "other"):
                f[f"te_{k}_{s}"] = (c[("st", s)] + 1) / (n + 3)
        return f

    def cand_feats(self, eid, cc, seg, tier, key, h, shown):
        f = {}
        d = delta(h, shown); tt = span(h)
        for lv in self.levels(cc, seg, tier, key)[:2]:
            c = self.get(eid, lv); no = c[("st", "other")] + 1; k = lv[0]
            f[f"tc_{k}_d"] = c[("d", d)] / no if d else 0
            f[f"tc_{k}_a"] = c[("a", h)] / no
            f[f"tc_{k}_ac"] = c[("ac", tt[1] % 1440)] / no if tt else 0
            f[f"tc_{k}_ao"] = c[("ao", tt[0])] / no if tt else 0
        return f

    def top_cands(self, eid, cc, seg, tier, key, shown, k=3):
        """Most common truths for this (country, segment, day) among training businesses."""
        out = {}
        c = self.get(eid, ("L1", cc, seg, key))
        s = span(shown)
        ds = [(n, x[1]) for x, n in c.items() if x[0] == "d"]
        for j, (n, (do, dc)) in enumerate(sorted(ds, reverse=True)[:k]):
            if s:
                o, cl = s[0] + do, s[1] + dc
                if 0 <= o and o + 30 < cl <= o + 1440:
                    out[f"te_d{j}"] = f"{o // 60 % 24:02d}:{o % 60:02d}-{cl // 60 % 24:02d}:{cl % 60:02d}"
        As = [(n, x[1]) for x, n in c.items() if x[0] == "a"]
        for j, (n, a) in enumerate(sorted(As, reverse=True)[:k]):
            out[f"te_a{j}"] = a
        return out

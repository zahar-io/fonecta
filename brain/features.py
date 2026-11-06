"""Feature builder for Connect Suggests. One row per (entity, special date) target.

Every feature uses only data stamped before the snapshot (honest back-test).
Candidates for the hours come from: the owner's past exceptions, the shopping centre, Google/Apple user edits
(publisher suggestions) about past holidays, and peer medians. A model then decides the state and which
candidate to trust.
"""
from __future__ import annotations

import csv
import json
import os
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd

KIT = os.environ.get("KIT", "/Users/zahar/zahar-setup/tg-bot/work/T334/pack/Fonecta_SinceAI2026/inner/FONECTA_CONNECT_SUGGESTS_2026")
sys.path.insert(0, os.path.join(KIT, "examples"))
from baseline import Baseline, day_str, cycle  # noqa: E402  (kit code, MIT)

D = lambda *p: os.path.join(KIT, *p)  # noqa: E731
CLOSED_WORDS = ("closed", "kiinni", "suljettu", "stängt", "stengt", "ovi oli", "door was")


def hm(s):
    return int(s[:2]) * 60 + int(s[3:5])


def span(h):
    """(open_min, close_min) of an hours string, None if closed."""
    if not h or h == "closed" or h == "REGULAR":
        return None
    ivs = h.split(",")
    a, b = hm(ivs[0][:5]), hm(ivs[-1][-5:])
    if b <= a:
        b += 1440
    return a, b


def bl_hol_items(bl):
    return bl.hol.items()


class Builder:
    def __init__(self, season: int):
        self.season = season
        self.bl = Baseline(season)
        self.snap = self.bl.snap
        snap_iso = self.snap.isoformat()
        cutoff_ms = datetime(self.snap.year, self.snap.month, self.snap.day).timestamp() * 1000
        # analytics (2-day lag: only rows before snapshot)
        a = pd.read_parquet(D("data", "analytics_daily.parquet"))
        a["date"] = a["date"].astype(str)
        a = a[a["date"] < snap_iso]
        a["act"] = a["GOOGLE_CUSTOMER_ACTIONS"] + a["GOOGLE_PHONE_CALLS"]
        a["views"] = a["GOOGLE_SEARCH_VIEWS"] + a["GOOGLE_MAP_VIEWS"]
        a["d"] = pd.to_datetime(a["date"])
        self.an = {eid: g.set_index("d")[["act", "views", "GOOGLE_PHONE_CALLS", "PROFILE_VIEWS"]] for eid, g in a.groupby("entity_id")}
        # reviews mentioning closed doors, by entity -> list of dates
        self.rev_closed = defaultdict(list)
        for r in json.load(open(D("data", "reviews.json"), encoding="utf-8"))["response"]["reviews"]:
            if r["publisherDate"] < cutoff_ms and any(w in (r["content"] or "").lower() for w in CLOSED_WORDS):
                self.rev_closed[r["locationId"]].append(datetime.fromtimestamp(r["publisherDate"] / 1000).date())
        # publisher suggestions with holidayHours for specific dates
        self.ps = defaultdict(list)  # (eid, date) -> hours strings
        for s in json.load(open(D("data", "publisher_suggestions.json"), encoding="utf-8"))["response"]["suggestions"]:
            if s["dateCreated"] >= snap_iso or s["fieldName"] != "hours":
                continue
            try:
                sc = json.loads(s["suggestedContent"])
            except Exception:
                continue
            for h in sc.get("holidayHours", []) or []:
                self.ps[(s["locationId"], h["date"])].append(day_str(h))
        # owner diligence: share of special days (before snapshot) with an owner entry made before the day
        cal = self.bl.cal
        self.special_dates = defaultdict(list)
        for r in cal:
            self.special_dates[r["country"]].append(r["date"])
        self.dil = {}
        for eid, e in self.bl.ents.items():
            c = e["meta"]["countryCode"]
            past = [d for d in self.special_dates[c] if d < snap_iso and d >= "2024-01-01"]
            n = sum(1 for d in past if any(x["entered_at"][:10] < d for x in self.bl.hol.get((eid, d), [])))
            self.dil[eid] = n / max(1, len(past))
        # owner's habit: typical (open, close) shift of their special hours vs their regular hours
        self.offset = {}
        by = defaultdict(list)
        for (eid, ds), rows in bl_hol_items(self.bl):
            if ds >= snap_iso:
                continue
            rr = [x for x in rows if x["entered_at"] < snap_iso]
            if not rr:
                continue
            h = max(rr, key=lambda x: x["entered_at"])["holidayHours"]
            if h.get("isClosed") or h.get("isRegularHours") or not h.get("openIntervals"):
                continue
            sp_e = span(day_str(h))
            sp_r = span(self.bl.regular(eid, date.fromisoformat(ds)))
            if sp_e and sp_r:
                by[eid].append((sp_e[0] - sp_r[0], sp_e[1] - sp_r[1]))
        for eid, l in by.items():
            from collections import Counter as _C
            (od, cd), n = _C(l).most_common(1)[0]
            if n >= 2 and n / len(l) >= 0.4 and (od, cd) != (0, 0):
                self.offset[eid] = (od, cd, n / len(l))
        self.contacts = {r["entity_id"]: r for r in csv.DictReader(open(D("data", "customer_contacts.csv"), encoding="utf-8"))} \
            if os.path.exists(D("data", "customer_contacts.csv")) else {}
        self.pilot = defaultdict(lambda: [0, 0])
        for r in csv.DictReader(open(D("data", "pilot_decision_log_2025.csv"), encoding="utf-8")):
            if r["sent_at"] < snap_iso:
                self.pilot[r["entity_id"]][0] += 1
                self.pilot[r["entity_id"]][1] += r["decision"] in ("ACCEPTED", "EDITED")

    # ---- signals ----
    def an_ratio(self, eid, p: date):
        """Activity on day p relative to the same weekday in the 4 weeks before. ~0 means closed."""
        g = self.an.get(eid)
        if g is None:
            return np.nan, np.nan
        ts = pd.Timestamp(p)
        if ts not in g.index:
            return np.nan, np.nan
        ref = [ts - pd.Timedelta(days=7 * k) for k in (1, 2, 3, 4)]
        ref = [r for r in ref if r in g.index]
        if not ref:
            return np.nan, np.nan
        base_a = g.loc[ref, "act"].mean()
        base_c = g.loc[ref, "GOOGLE_PHONE_CALLS"].mean()
        return (g.loc[ts, "act"] + 0.5) / (base_a + 0.5), (g.loc[ts, "GOOGLE_PHONE_CALLS"] + 0.5) / (base_c + 0.5)

    def views_recent(self, eid):
        g = self.an.get(eid)
        if g is None or g.empty:
            return 0.0
        return float(g["views"].iloc[-30:].mean())

    def prev_dates(self, cc, key, d, back=1):
        return [x for x in self.bl.dates_by_key[(cc, key)] if cycle(x) == cycle(d) - back]

    def row(self, eid, d: date, key: str):
        bl = self.bl
        e = bl.ents[eid]
        cc = e["meta"]["countryCode"]
        shown = bl.displayed(eid, d)
        reg = bl.regular(eid, d)
        f = {"cc": cc, "seg": e.get("c_segment", ""), "key": key, "wd": d.weekday(),
             "tier": bl.tiers.get(e["address"]["city"], ""), "shown_closed": int(shown == "closed"),
             "entered_now": int(bl.entry(eid, d, self.snap) is not None), "dil": self.dil.get(eid, 0.0),
             "closed_sig": int(eid in bl.closed_signal), "listing_closed": int(bool(e.get("closed"))),
             "views": self.views_recent(eid), "pilot_n": self.pilot[eid][0], "pilot_acc": self.pilot[eid][1],
             "days_ahead": (d - self.snap).days}
        sp = span(shown)
        f["shown_open"], f["shown_close"] = (sp if sp else (np.nan, np.nan))
        cands = {}
        # owner's own past entries, 1 and 2 cycles back
        for back in (1, 2):
            v, rr = None, (np.nan, np.nan)
            for p in self.prev_dates(cc, key, d, back):
                last = bl.entry(eid, p, self.snap)
                if last is not None:
                    v = bl.regular(eid, d) if last == "REGULAR" else last
                rr = self.an_ratio(eid, p)
                ps = self.ps.get((eid, p.isoformat()))
                if ps:
                    cands.setdefault(f"ps{back}", ps[-1])
                nrev = sum(1 for x in self.rev_closed.get(eid, []) if 0 <= (x - p).days <= 10)
                f[f"rev{back}"] = nrev
            f[f"ly{back}_has"] = int(v is not None)
            f[f"ly{back}_closed"] = int(v == "closed") if v is not None else -1
            f[f"ly{back}_eq_shown"] = int(v == shown) if v is not None else -1
            f[f"an_act{back}"], f[f"an_call{back}"] = rr
            f.setdefault(f"rev{back}", 0)
            if v is not None:
                cands[f"ly{back}"] = v
        f["ps1_has"], f["ps2_has"] = int("ps1" in cands), int("ps2" in cands)
        f["ps1_closed"] = int(cands.get("ps1") == "closed") if "ps1" in cands else -1
        # shopping centre
        mall = e.get("c_shoppingCenterEntityId")
        f["in_mall"] = int(bool(mall))
        m = bl.entry(mall, d, self.snap) if mall else None
        f["mall_has"] = int(m is not None and m != "REGULAR")
        f["mall_closed"] = int(m == "closed") if f["mall_has"] else -1
        if f["mall_has"]:
            cands["mall"] = m
        # peers
        b = bl.bench.get((cc, f["tier"], f["seg"], key))
        for k in ("share_no_exception_entered", "share_entered_closed", "share_entered_special_hours",
                  "share_entered_regular", "closed_share_among_entered"):
            f["p_" + k] = float(b[k]) if b and b.get(k) not in (None, "") else np.nan
        if b and b.get("median_open_special") and b.get("median_close_special"):
            cands["peer_special"] = f"{b['median_open_special']}-{b['median_close_special']}"
        # peer-informed variant: own regular open time + peer special close
        if sp and b and b.get("median_close_special"):
            o = shown.split(",")[0][:5]
            if hm(o) < hm(b["median_close_special"]):
                cands["reg_open_peer_close"] = f"{o}-{b['median_close_special']}"
        off = self.offset.get(eid)
        f["off_share"] = off[2] if off else 0.0
        if off and sp and os.environ.get("OWN_OFFSET", "1") == "1":
            o, c = sp[0] + off[0], sp[1] + off[1]
            if 0 <= o < c <= 1439 + 1440:
                fmt = lambda m: f"{(m // 60) % 24:02d}:{m % 60:02d}"  # noqa: E731
                cands["own_offset"] = f"{fmt(o)}-{fmt(c)}"
        f["n_cands"] = len(cands)
        f["cand_agree"] = int(len(set(cands.values())) == 1) if cands else -1
        return f, cands, shown, reg

"""Kit data not used before, plus a cleaner activity baseline.
- calendar: day_type / day_class / official holiday (coded)
- entity: first category id, number of categories
- listings: status mix and Google update speed
- regular hours: number of changes and days since the last one before the snapshot
- school breaks: date inside a break, day index into it
- local events: events within 1 km on that date, max attendance, event row flag
- weather: only where the snapshot has it (observed or forecast up to ~15 Nov); NaN otherwise
- an_llr2: same Poisson evidence as an_llr, but the reference weeks skip other special days and look back up to 8 weeks
Everything uses data stamped before the snapshot (weather forecast rows are marked available at the snapshot)."""
import csv, json, math
from collections import defaultdict
from datetime import date, timedelta
import numpy as np, pandas as pd
from features import D
from baseline import cycle

def _codes(vals):
    m = {v: i for i, v in enumerate(sorted(set(vals)))}
    return m

def build(b, meta):
    bl = b.bl; snap = b.snap; si = snap.isoformat()
    cal = {(r["country"], r["date"]): r for r in csv.DictReader(open(D("data", "calendar_special_days.csv"), encoding="utf-8"))}
    special = defaultdict(set)
    for (cc, ds) in cal: special[cc].add(ds)
    dt_code = _codes([r["day_type"] for r in cal.values()]); dc_code = _codes([r["day_class"] for r in cal.values()])
    # listings
    lst = defaultdict(list)
    for x in json.load(open(D("data", "listings.json"), encoding="utf-8"))["listings"]: lst[x["entityId"]].append(x)
    # regular hours history
    rh = defaultdict(list)
    for line in open(D("data", "regular_hours_history.jsonl"), encoding="utf-8"):
        r = json.loads(line); ef = r.get("effective_from", "")
        if ef and ef[0].isdigit() and ef < si: rh[r["entity_id"]].append(date.fromisoformat(ef[:10]))
    # school breaks
    sb = [r for r in csv.DictReader(open(D("data", "school_breaks.csv"), encoding="utf-8"))]
    # events
    ev = defaultdict(list)
    for e in json.load(open(D("data", "local_events.json"), encoding="utf-8"))["data"]:
        lon, lat = e["location"]["position"]["coordinates"]
        ev[e["start_time"][:10]].append((lat, lon, e.get("x_expected_attendance") or 0))
    # weather
    wx = {}
    for r in csv.DictReader(open(D("data", "weather_daily.csv"), encoding="utf-8")):
        if r["date"] < si or r["is_forecast"] == "1": wx[(r["city"], r["date"])] = r
    # analytics for the clean baseline
    a = pd.read_parquet(D("data", "analytics_daily.parquet"))
    a["date"] = pd.to_datetime(a["date"].astype(str)); a = a[a["date"] < pd.Timestamp(snap)]
    g = {e: x.set_index("date")[["GOOGLE_CUSTOMER_ACTIONS", "PROFILE_VIEWS"]] for e, x in a.groupby("entity_id")}
    out = []; lcache = {}
    for m in meta:
        eid = m["entity_id"]; ds = m["date"]; d = date.fromisoformat(ds); e = bl.ents[eid]
        cc = e["meta"]["countryCode"]; c = cal.get((cc, ds), {})
        f = {"x4_day_type": dt_code.get(c.get("day_type"), -1), "x4_day_class": dc_code.get(c.get("day_class"), -1),
             "x4_official": int(c.get("official_public_holiday", "0") == "1")}
        cats = e.get("categoryIds") or []
        f["x4_cat"] = int(cats[0]) if cats and str(cats[0]).isdigit() else -1; f["x4_ncat"] = len(cats)
        L = lst.get(eid, [])
        f["x4_nlist"] = len(L); f["x4_live"] = sum(x["status"] == "LIVE" for x in L) / max(len(L), 1)
        f["x4_optout"] = sum(x["status"] == "OPTED_OUT" for x in L)
        gm = next((x for x in L if x["publisherId"] == "GOOGLEMYBUSINESS"), None)
        f["x4_g_speed"] = gm["typicalUpdateSpeedSeconds"] if gm else np.nan
        f["x4_g_live"] = int(bool(gm) and gm["status"] == "LIVE")
        ch = rh.get(eid, [])
        f["x4_rh_n"] = len(ch); f["x4_rh_days"] = (snap - max(ch)).days if ch else 9999
        inb = [r for r in sb if r["country"] == cc and r["start"] <= ds <= r["end"]]
        f["x4_school"] = int(bool(inb)); f["x4_school_day"] = (d - date.fromisoformat(inb[0]["start"])).days if inb else -1
        co = e.get("geocodedCoordinate") or {}; la, lo = co.get("latitude"), co.get("longitude")
        n1 = 0; att = 0
        if la is not None:
            for (ela, elo, at) in ev.get(ds, []):
                dk = 111.2 * math.hypot(ela - la, (elo - lo) * math.cos(math.radians(la)))
                if dk <= 1.0: n1 += 1; att = max(att, at)
        f["x4_ev1km"] = n1; f["x4_ev_att"] = att; f["x4_ev_row"] = int(bool(m.get("event_id")) or m["key"] == "EVENT")
        w = wx.get((e["address"].get("city"), ds))
        f["x4_snow"] = float(w["snow_depth_cm"]) if w else np.nan
        f["x4_precip"] = float(w["precip_mm"]) if w else np.nan
        f["x4_tmax"] = float(w["tmax_c"]) if w else np.nan
        # clean Poisson baseline
        ck = (eid, m["key"], cycle(d))
        if ck not in lcache:
            x = g.get(eid); lc = lo2 = 0.0; n = 0
            if x is not None:
                for back in (1, 2):
                    for p in b.prev_dates(cc, m["key"], d, back):
                        ts = pd.Timestamp(p)
                        if ts not in x.index: continue
                        ref = []
                        for k in range(1, 9):
                            r = ts - pd.Timedelta(days=7 * k)
                            if r in x.index and r.strftime("%Y-%m-%d") not in special[cc]: ref.append(r)
                            if len(ref) == 4: break
                        if not ref: continue
                        lam = x.loc[ref].median() + 0.3; k = x.loc[ts]
                        lc += k.iloc[0] * np.log(0.6) + 0.4 * lam.iloc[0]
                        lo2 += k.iloc[0] * np.log(1.15) - 0.15 * lam.iloc[0] + k.iloc[1] * np.log(1.15) - 0.15 * lam.iloc[1]
                        n += 1
            lcache[ck] = (lc if n else np.nan, lo2 if n else np.nan)
        f["x4_llr_closed"], f["x4_llr_other"] = lcache[ck]
        out.append(f)
    return pd.DataFrame(out)

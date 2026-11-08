"""owner's weekend regular hours and last season's open entries as hours
candidates; per-holiday closed/open state from the owner's own entries last season (habits correlate across holidays)."""
from collections import Counter, defaultdict
from datetime import date, timedelta
import pandas as pd
import features  # noqa: F401 (puts the kit on sys.path)
from baseline import cycle
KEYS = ["DEC23","XMAS_EVE","XMAS_DAY","BOXING_DAY","INTERDAY","NYE","NEW_YEARS_DAY","EPIPHANY_EVE","EPIPHANY",
        "INDEPENDENCE_DAY","ALL_SAINTS","BLACK_FRIDAY","FATHERS_DAY","GOOD_FRIDAY","EASTER_SUNDAY","MIDSUMMER_EVE",
        "MIDSUMMER_DAY","MAY_DAY","ASCENSION","EASTER_MONDAY"]
def build(b, meta):
    bl = b.bl; si = b.snap.isoformat()
    keyof = {(r["country"], r["date"]): r["day_key"] for r in bl.cal}
    ent = defaultdict(list)
    for (eid, ds), rows in bl.hol.items():
        rr = [x for x in rows if x["entered_at"] < si]
        if not rr: continue
        h = max(rr, key=lambda x: x["entered_at"])["holidayHours"]
        if h.get("isRegularHours"): v = "REG"
        elif h.get("isClosed") or not h.get("openIntervals"): v = "closed"
        else: v = ",".join(f"{i['start']}-{i['end']}" for i in h["openIntervals"])
        ent[eid].append((date.fromisoformat(ds), v))
    out, cands = [], []
    cache = {}
    for m in meta:
        eid = m["entity_id"]; d = date.fromisoformat(m["date"]); cyc = cycle(d)
        cc = bl.ents[eid]["meta"]["countryCode"]
        k = (eid, cyc)
        if k not in cache:
            f = {}
            prev = [(keyof.get((cc, x.isoformat())), v) for x, v in ent.get(eid, []) if cycle(x) == cyc - 1]
            pk = {}
            for kk, v in prev:
                if kk: pk.setdefault(kk, []).append(v)
            for kk in KEYS:
                vs = pk.get(kk)
                f["k_" + kk] = -1 if not vs else (0 if all(v == "closed" for v in vs) else (1 if all(v == "REG" for v in vs) else 2))
            opens = [v for _, v in prev if v not in ("closed", "REG")]
            mode = Counter(opens).most_common(1)[0][0] if opens else None
            sun = next((bl.regular(eid, d + timedelta(days=j)) for j in range(7) if (d + timedelta(days=j)).weekday() == 6), None)
            sat = next((bl.regular(eid, d + timedelta(days=j)) for j in range(7) if (d + timedelta(days=j)).weekday() == 5), None)
            cache[k] = (f, {"ly_mode": mode, "sun": sun, "sat": sat})
        f, c = cache[k]
        out.append(f); cands.append({x: v for x, v in c.items() if v and v not in ("closed", m["shown"])})
    return pd.DataFrame(out), cands

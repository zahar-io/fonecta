"""Owner diligence: does this owner enter exceptions at all, how early, and how did they behave on days
they did NOT enter (what Google showed then vs what happened: inferred from activity is too weak, so we use entry
coverage only). All from entries stamped before the snapshot."""
from collections import defaultdict
from datetime import date, datetime
import numpy as np, pandas as pd
from baseline import cycle
XMAS = {"DEC23","XMAS_EVE","XMAS_DAY","BOXING_DAY","INTERDAY","NYE","NEW_YEARS_DAY","EPIPHANY_EVE","EPIPHANY"}

def build(b, meta):
    bl = b.bl; snap = b.snap; si = snap.isoformat()
    days = defaultdict(list)  # country -> [(date, key)] special days before snapshot
    for r in bl.cal:
        if r["date"] < si: days[r["country"]].append((date.fromisoformat(r["date"]), r["day_key"]))
    ent = defaultdict(dict)  # eid -> {date: (lead_days, kind)}
    for (eid, ds), rows in bl.hol.items():
        rr = [x for x in rows if x["entered_at"] < si]
        if not rr or ds >= si: continue
        first = min(rr, key=lambda x: x["entered_at"]); last = max(rr, key=lambda x: x["entered_at"])["holidayHours"]
        lead = (date.fromisoformat(ds) - date.fromisoformat(first["entered_at"][:10])).days
        kind = "REG" if last.get("isRegularHours") else ("closed" if last.get("isClosed") or not last.get("openIntervals") else "open")
        ent[eid][date.fromisoformat(ds)] = (lead, kind, len(rr))
    out = []; cache = {}
    for m in meta:
        eid = m["entity_id"]; d = date.fromisoformat(m["date"]); cyc = cycle(d)
        if (eid, cyc) not in cache:
            cc = bl.ents[eid]["meta"]["countryCode"]; E = ent.get(eid, {})
            f = {}
            for back in (1, 2):
                dd = [(x, k) for x, k in days[cc] if cycle(x) == cyc - back]
                xm = [(x, k) for x, k in dd if k in XMAS]
                hit = [E[x] for x, _ in dd if x in E]; hx = [E[x] for x, _ in xm if x in E]
                f[f"dl_cov{back}"] = len(hit) / len(dd) if dd else np.nan
                f[f"dl_covx{back}"] = len(hx) / len(xm) if xm else np.nan
                f[f"dl_lead{back}"] = float(np.median([h[0] for h in hit])) if hit else np.nan
                f[f"dl_edits{back}"] = float(np.mean([h[2] for h in hit])) if hit else np.nan
                f[f"dl_reg{back}"] = sum(h[1] == "REG" for h in hit) / len(hit) if hit else np.nan
            f["dl_cov_all"] = len(E) / max(len(days[cc]), 1)
            # entries for this cycle already made before the snapshot, any day
            cur = [v for x, v in E.items() if cycle(x) == cyc]
            f["dl_cur_n"] = len(cur)
            f["dl_first_seen"] = (snap - min(E)).days if E else -1
            cache[(eid, cyc)] = f
        out.append(cache[(eid, cyc)])
    return pd.DataFrame(out)

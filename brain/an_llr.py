"""Poisson evidence from last seasons' analytics (T403): on a day the business was closed while the listing said
open, customer actions drop to ~0.6x of the usual weekday; on different-hours days actions and profile views are
~1.15x. Log-likelihood ratios summed over every past occurrence of the same special day (before the snapshot)."""
import numpy as np, pandas as pd
from features import D
from baseline import cycle
def build(b, meta):
    a = pd.read_parquet(D("data", "analytics_daily.parquet"))
    a["date"] = pd.to_datetime(a["date"].astype(str)); a = a[a["date"] < pd.Timestamp(b.snap)]
    g = {e: x.set_index("date")[["GOOGLE_CUSTOMER_ACTIONS", "PROFILE_VIEWS", "GOOGLE_PHONE_CALLS"]] for e, x in a.groupby("entity_id")}
    out = []; cache = {}
    for m in meta:
        eid = m["entity_id"]; key = m["key"]; from datetime import date as _d
        d = _d.fromisoformat(m["date"]); cc = b.bl.ents[eid]["meta"]["countryCode"]
        ck = (eid, key, cycle(d))
        if ck not in cache:
            x = g.get(eid); lc = lo = 0.0; n = 0
            if x is not None:
                for back in (1, 2):
                    for p in b.prev_dates(cc, key, d, back):
                        ts = pd.Timestamp(p)
                        if ts not in x.index: continue
                        ref = [ts - pd.Timedelta(days=7 * k) for k in (1, 2, 3, 4)]
                        ref = [r for r in ref if r in x.index]
                        if not ref: continue
                        lam = x.loc[ref].mean() + 0.3; k = x.loc[ts]
                        lc += k.iloc[0] * np.log(0.6) + 0.4 * lam.iloc[0]
                        lo += k.iloc[0] * np.log(1.15) - 0.15 * lam.iloc[0] + k.iloc[1] * np.log(1.15) - 0.15 * lam.iloc[1]
                        n += 1
            cache[ck] = {"llr_closed": lc if n else np.nan, "llr_other": lo if n else np.nan, "llr_n": n}
        out.append(cache[ck])
    return pd.DataFrame(out)

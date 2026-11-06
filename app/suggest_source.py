"""Suggestion source: which special days will show wrong hours, what to suggest, and why.

Interface (swap freely):
    get_suggestions(entity_id) -> list of {
        entity_id, date, day_key, day_type, action SUGGEST|NO_ACTION|FLAG, hours, shown_hours,
        confidence, reasons: [human-readable strings], basis, evidence: {...}, public_holiday }

Implementations:
  * BaselineSource  - wraps the kit's examples/baseline.py (copy last year -> shopping centre -> peers),
                      plus a no-history fallback (peer hours, asked as a question).
  * BrainCsvSource  - reads the brain's CSV (env BRAIN_PREDICTIONS):
                      entity_id,date,action,hours,confidence,basis,reasons_json
Both read "what Google shows now" from the live Yext entity when the API is reachable (so hours that were
just applied are not suggested again), else from the dataset snapshot."""
from __future__ import annotations

import csv
import json
import sys
import threading
from datetime import date

from . import config, kitdata
from .hours import DAYS, day_str, holiday_entry_str

_BL = None
_BL_LOCK = threading.Lock()
WD = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def baseline():
    """The kit's Baseline (its ROOT is computed from its own file, so no chdir needed)."""
    global _BL
    with _BL_LOCK:
        if _BL is None:
            if config.KIT_EXAMPLES not in sys.path:
                sys.path.insert(0, config.KIT_EXAMPLES)
            from baseline import Baseline  # noqa: E402  (kit file, MIT)
            _BL = Baseline(2026)
    return _BL


def fmt_d(d: date) -> str:
    return f"{WD[d.weekday()]} {d.day}.{d.month}.{d.year}"


def has_history(eid: str) -> bool:
    """Any exception hours ever entered, or any decision in the 2025 pilot."""
    bl = baseline()
    if any(k[0] == eid for k in bl.hol):
        return True
    return any(r["entity_id"] == eid for r in kitdata.pilot_log())


class _Live:
    """What Google shows now, from the live Yext entity (falls back to the dataset snapshot)."""

    def __init__(self, eid, yext=None):
        self.eid, self.ent = eid, None
        if yext is not None:
            try:
                self.ent = yext.get_entity(eid)
            except Exception:
                self.ent = None

    @property
    def source(self):
        return "Yext API (live)" if self.ent else "dataset snapshot (5 Nov)"

    def shown(self, d: date) -> str:
        if not self.ent:
            return baseline().displayed(self.eid, d)
        h = self.ent.get("hours") or {}
        for item in h.get("holidayHours", []):
            if item.get("date") == d.isoformat():
                s = holiday_entry_str(item)
                if s != "REGULAR":
                    return s
        return day_str(h.get(DAYS[d.weekday()]))

    def has_exception(self, d: date) -> bool:
        h = (self.ent or {}).get("hours") or {}
        return any(i.get("date") == d.isoformat() for i in h.get("holidayHours", []))


def _base_item(eid, t, shown):
    d = date.fromisoformat(t["date"])
    cal = kitdata.calendar().get((t["country"], t["date"]), {})
    return {"entity_id": eid, "date": t["date"], "day_key": t["day_key"], "day_type": t["day_type"],
            "event_id": t.get("event_id") or "", "name_en": cal.get("name_en") or t["day_key"].title(),
            "public_holiday": cal.get("official_public_holiday") == "1", "weekday": d.weekday(),
            "shown_hours": shown, "action": "NO_ACTION", "hours": "", "confidence": 0.0, "reasons": [],
            "basis": None, "evidence": {}}


class BaselineSource:
    name = "kit baseline (last year -> shopping centre -> peers) + no-history peer questions"

    def __init__(self, yext=None):
        self.yext = yext

    def get_suggestions(self, eid: str) -> list:
        bl = baseline()
        if eid not in bl.ents:
            return []
        live = _Live(eid, self.yext)
        nohist = not has_history(eid)
        out = []
        for t in kitdata.targets().get(eid, []):
            d = date.fromisoformat(t["date"])
            shown = live.shown(d)
            it = _base_item(eid, t, shown)
            it["shown_source"] = live.source
            act, hrs, basis, ev = bl.explain(eid, d, t["day_key"])
            if live.ent and live.ent.get("closed"):
                act, basis, ev = "FLAG", "CLOSED_SIGNALS", "the listing is marked closed in Yext"
            it["basis"] = basis
            if act == "FLAG":
                it.update(action="FLAG", confidence=0.9,
                          reasons=[f"Closed-for-good signals: {ev}. A human should confirm before any message.",
                                   f"Google still shows {shown} for {fmt_d(d)}."])
                out.append(it)
                continue
            if basis == "LAST_YEAR":
                it["evidence"] = {"last_date": ev[0], "last_hours": ev[1]}
                last = bl.regular(eid, d) if ev[1] == "REGULAR" else ev[1]
                it["evidence"]["last_hours"] = last
                cand, conf = last, 0.85
                reasons = [f"Last year ({fmt_d(date.fromisoformat(ev[0]))}) the owner entered {ev[1]}."]
            elif basis == "SHOPPING_CENTRE":
                cand, conf = hrs, 0.8
                it["evidence"] = {"mall": ev, "mall_hours": hrs}
                reasons = [f"{ev} (the shopping centre it is in) has published {hrs} for this day."]
            elif basis == "PEERS":
                cand, conf = "closed", round(0.35 + 0.35 * float(ev), 2)
                it["evidence"] = {"peer_closed_share": float(ev)}
                reasons = [f"{round(float(ev) * 100)}% of similar businesses nearby that entered this day were "
                           f"closed (peer benchmark)."]
            else:
                cand, conf, reasons = None, 0.0, []
            if act == "SUGGEST" and hrs == shown:  # already live in Yext (e.g. applied earlier)
                act = "NO_ACTION"
            if act == "SUGGEST":
                if nohist:
                    conf = round(conf - 0.1, 2)
                    reasons.append("New customer with no history of their own: confidence lowered, so we ask.")
                it.update(action="SUGGEST", hours=hrs, confidence=conf,
                          reasons=reasons + [self._shown_reason(live, d, shown)])
            elif cand is not None and cand == shown:
                it.update(confidence=conf, reasons=reasons + [f"Google already shows {shown}: nothing to do."])
            elif nohist:
                self._peer_question(eid, t, d, shown, it)
            out.append(it)
        if nohist:  # don't overwhelm a new customer: at most 4 questions, the most-viewed days first
            qs = [i for i in out if i["action"] == "SUGGEST" and i["basis"] == "PEER_HOURS"]
            if len(qs) > 4:
                country = kitdata.entities()[eid]["meta"]["countryCode"]
                qs.sort(key=lambda i: -kitdata.at_risk_views(eid, country, i["day_key"],
                                                              date.fromisoformat(i["date"]))["views"])
                for i in qs[4:]:
                    i.update(action="NO_ACTION", reasons=i["reasons"] + ["Held back: max 4 questions per message."])
        return out

    @staticmethod
    def _shown_reason(live, d, shown):
        if live.has_exception(d) or baseline().entry(live.eid, d, config.SNAPSHOT) not in (None, "REGULAR"):
            return f"Google now shows an exception of {shown} for {fmt_d(d)}."
        return f"No exception hours entered for {fmt_d(d)}, so Google shows the regular hours: {shown}."

    def _peer_question(self, eid, t, d, shown, it):
        """No own history, nothing from the baseline: ask, using what similar businesses entered."""
        p = kitdata.peer_row(eid, t["day_key"])
        if not p or shown == "closed":
            return
        cs = float(p["closed_share_among_entered"] or 0)
        if cs >= 0.6 and float(p["share_entered_closed"] or 0) >= 0.15:
            it.update(action="SUGGEST", hours="closed", basis="PEER_HOURS", confidence=0.45,
                      evidence={"peer_closed_share": cs})
            it["reasons"] = [f"New customer, no history. {round(cs * 100)}% of similar businesses nearby that "
                             f"entered this day were closed.", f"Google shows the regular hours: {shown}.",
                             "Low confidence: phrased as a question."]
        elif float(p["share_entered_special_hours"] or 0) >= 0.2 and p["median_open_special"]:
            ph = f"{p['median_open_special']}-{p['median_close_special']}"
            if ph != shown:
                it.update(action="SUGGEST", hours=ph, basis="PEER_HOURS", confidence=0.4,
                          evidence={"peer_hours": ph, "peer_share": float(p["share_entered_special_hours"])})
                it["reasons"] = [f"New customer, no history. Similar businesses nearby that entered special hours "
                                 f"for this day mostly had {ph} (median of {p['n_entity_days']} business-days).",
                                 f"Google shows the regular hours: {shown}.", "Low confidence: phrased as a question."]


class BrainCsvSource:
    """Predictions from brain/. Two formats are read:
      * entity_id,date,action,hours,confidence,basis,reasons_json            (reasons given by the brain)
      * entity_id,date,day_key,action,hours,confidence,basis,shown,p_closed,p_same,p_other,candidates_json
        (outputs/predictions_2026_explained.csv: reasons are built here from basis + candidates)
    Brain bases: LY1/LY2 (owner's own entry 1/2 seasons back), MALL (shopping centre), PS1/PS2 (Google user
    edit 1/2 seasons back), PEER_SPECIAL (peers' median special hours), STATE_MODEL (classifier: closed),
    CLOSED_SIGNALS (FLAG)."""

    BASIS_MAP = {"LY1": "LAST_YEAR", "LY2": "EARLIER", "MALL": "SHOPPING_CENTRE", "PS1": "PUBLISHER",
                 "PS2": "PUBLISHER", "PEER_SPECIAL": "PEER_HOURS"}

    def __init__(self, path, yext=None):
        self.path, self.yext = path, yext
        self.name = f"brain CSV ({path.split('/')[-1]})"
        self.rows = {}
        with open(path, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                self.rows[(r["entity_id"], r["date"])] = r

    @staticmethod
    def _cands(r):
        try:
            return json.loads(r.get("candidates_json") or "{}") or {}
        except json.JSONDecodeError:
            return {}

    def _explain(self, eid, r, it, d):
        """Map brain basis + candidates to (message basis, evidence, human reasons)."""
        c = self._cands(r)
        b = (r.get("basis") or "").upper()
        hrs = (r.get("hours") or "").strip().lower()
        reasons, ev = [], {}
        prev = kitdata.previous_same_day(it_country(eid), it["day_key"], d)
        if "ly1" in c:
            reasons.append(f"Last season ({fmt_d(prev) if prev else 'last year'}) the owner entered {c['ly1']}.")
        if "ly2" in c:
            reasons.append(f"Two seasons ago the owner entered {c['ly2']}.")
        if "ps1" in c or "ps2" in c:
            reasons.append(f"Google users suggested {c.get('ps1') or c.get('ps2')} for this day in an earlier season.")
        if "mall" in c:
            reasons.append(f"The shopping centre has published {c['mall']} for this day.")
        if "peer_special" in c:
            reasons.append(f"Peers (same type, country, city size) who entered special hours: median {c['peer_special']}.")
        if r.get("p_closed"):
            reasons.append(f"Model: P(closed)={float(r['p_closed']):.2f}, P(same as Google shows)="
                           f"{float(r.get('p_same') or 0):.2f}, P(other hours)={float(r.get('p_other') or 0):.2f}.")
        basis = self.BASIS_MAP.get(b)
        if basis == "LAST_YEAR":
            ev = {"last_hours": c.get("ly1", hrs), "last_date": prev.isoformat() if prev else ""}
        elif basis == "EARLIER":
            ev = {"last_hours": c.get("ly2", hrs)}
        elif basis == "PUBLISHER":
            ev = {"last_hours": c.get("ps1") or c.get("ps2") or hrs}
        elif basis == "SHOPPING_CENTRE":
            ent = kitdata.entities().get(eid, {})
            mall = kitdata.entities().get(ent.get("c_shoppingCenterEntityId") or "", {}).get("name", "Shopping centre")
            ev = {"mall": mall, "mall_hours": c.get("mall", hrs)}
        elif basis == "PEER_HOURS":
            ev = {"peer_hours": c.get("peer_special", hrs)}
        elif b == "STATE_MODEL" or not basis:
            # pick the most concrete evidence that agrees with the suggestion for the customer message
            if hrs and c.get("ly1") == hrs:
                basis, ev = "LAST_YEAR", {"last_hours": hrs, "last_date": prev.isoformat() if prev else ""}
            elif hrs and c.get("ly2") == hrs:
                basis, ev = "EARLIER", {"last_hours": hrs}
            elif hrs and c.get("mall") == hrs:
                ent = kitdata.entities().get(eid, {})
                basis = "SHOPPING_CENTRE"
                ev = {"mall": kitdata.entities().get(ent.get("c_shoppingCenterEntityId") or "", {}).get("name", ""),
                      "mall_hours": hrs}
            elif hrs and (c.get("ps1") == hrs or c.get("ps2") == hrs):
                basis, ev = "PUBLISHER", {"last_hours": hrs}
            else:
                pr = kitdata.peer_row(eid, it["day_key"])
                share = float(pr["closed_share_among_entered"] or 0) if pr else 0
                if hrs == "closed" and share >= 0.5:
                    basis, ev = "PEERS", {"peer_closed_share": share}
                    reasons.append(f"{round(share * 100)}% of similar businesses nearby that entered this day were closed.")
                else:
                    basis = "MODEL"
        return basis, ev, reasons

    def get_suggestions(self, eid: str) -> list:
        live = _Live(eid, self.yext)
        out = []
        for t in kitdata.targets().get(eid, []):
            d = date.fromisoformat(t["date"])
            r = self.rows.get((eid, t["date"]))
            shown = live.shown(d) if live.ent or not (r and r.get("shown")) else r["shown"]
            it = _base_item(eid, t, shown)
            it["shown_source"] = live.source if live.ent or not (r and r.get("shown")) else "brain CSV (snapshot)"
            if r:
                act = (r.get("action") or "NO_ACTION").upper()
                hrs = (r.get("hours") or "").strip().lower()
                conf = float(r.get("confidence") or 0.6)
                if "reasons_json" in r:
                    try:
                        reasons = [str(x) for x in json.loads(r.get("reasons_json") or "[]")]
                    except json.JSONDecodeError:
                        reasons = [r.get("reasons_json")]
                    basis, ev = r.get("basis") or "BRAIN", {}
                else:
                    basis, ev, reasons = self._explain(eid, r, it, d)
                if act == "FLAG":
                    reasons = ["Closed-for-good signals (reviews / Google edits): a human should confirm before any "
                               "message."] + reasons
                if act == "SUGGEST" and hrs == shown:
                    act = "NO_ACTION"
                    reasons = reasons + [f"Google already shows {shown}."]
                it.update(action=act, hours=hrs, confidence=conf, basis=basis, evidence=ev, reasons=reasons,
                          brain_basis=r.get("basis"))
                if act == "SUGGEST":
                    it["reasons"].append(BaselineSource._shown_reason(live, d, shown) if live.ent else
                                         f"Google now shows {shown} for {fmt_d(d)}.")
            out.append(it)
        return out


def it_country(eid: str) -> str:
    return kitdata.entities().get(eid, {}).get("meta", {}).get("countryCode", "FI")


def get_source(yext=None):
    p = config.brain_predictions()
    return BrainCsvSource(p, yext) if p else BaselineSource(yext)


def get_suggestions(entity_id: str, yext=None) -> list:
    return get_source(yext).get_suggestions(entity_id)

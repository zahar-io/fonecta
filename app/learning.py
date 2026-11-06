"""What Connect learns per owner: audit trail of every decision, preferences learned from edits and
declines, standing permissions, and priors seeded from the 2025 pilot log.

Stored as one JSON file (app/var/learning.json). Small, readable, easy to swap for SQLite later."""
from __future__ import annotations

import json
import os
import statistics
import threading
from collections import defaultdict
from datetime import date, datetime, timezone
from functools import lru_cache

from . import config, kitdata
from .hours import minutes

LOCK = threading.RLock()
DECLINE_REASONS = {
    "open_as_usual": "We're open as usual",
    "different_hours": "Different hours",
    "not_this_year": "Not this year",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def season(d: str) -> int:
    x = date.fromisoformat(d)
    return x.year if x.month >= 2 else x.year - 1


# ------------------------------------------------------------------ pilot priors (read-only kit data)
@lru_cache(maxsize=1)
def pilot_priors() -> dict:
    ent = defaultdict(lambda: {"n": 0, "ACCEPTED": 0, "EDITED": 0, "REJECTED": 0, "NO_RESPONSE": 0,
                               "permission": False, "edits": [], "rejects": []})
    ch = defaultdict(lambda: [0, 0])
    for r in kitdata.pilot_log():
        e = ent[r["entity_id"]]
        e["n"] += 1
        e[r["decision"]] = e.get(r["decision"], 0) + 1
        e["permission"] |= r["standing_permission_granted"] == "True"
        ch[r["channel"]][0] += 1
        ch[r["channel"]][1] += r["decision"] != "NO_RESPONSE"
        if r["decision"] == "EDITED" and r["final_hours"]:
            e["edits"].append({"day_key": r["day_key"], "suggested": r["suggested_hours"], "final": r["final_hours"]})
        if r["decision"] == "REJECTED":
            e["rejects"].append({"day_key": r["day_key"], "suggested": r["suggested_hours"],
                                 "comment": r["owner_comment"], "date": r["date"]})
    total = sum(v[0] for v in ch.values()) or 1
    rates = {k: {"sent": v[0], "replied": v[1], "reply_rate": round(v[1] / v[0], 2) if v[0] else None}
             for k, v in ch.items()}
    acc = sum(e["ACCEPTED"] for e in ent.values()) / max(1, sum(e["n"] for e in ent.values()))
    return {"entities": dict(ent), "channels": rates, "global_accept_rate": round(acc, 3), "total": total}


def offset_of(suggested: str, final: str):
    """(open delta, close delta) in minutes between two single-interval hours strings, else None."""
    if not suggested or not final or "closed" in (suggested, final) or "," in suggested or "," in final:
        return None
    (a1, b1), (a2, b2) = suggested.split("-"), final.split("-")
    return minutes(a2) - minutes(a1), minutes(b2) - minutes(b1)


# ------------------------------------------------------------------ the store
class Learning:
    def __init__(self, path: str | None = None):
        self.path = path or os.path.join(config.var_dir(), "learning.json")
        self.data = {"decisions": [], "prefs": {}}
        if os.path.exists(self.path):
            with open(self.path, encoding="utf-8") as f:
                self.data = json.load(f)

    def save(self):
        with LOCK:
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=1)
            os.replace(tmp, self.path)

    def clear(self):
        with LOCK:
            self.data = {"decisions": [], "prefs": {}}
            self.save()

    def prefs(self, eid: str) -> dict:
        p = self.data["prefs"].setdefault(eid, {})
        for k, v in (("suppress", {}), ("day_hours", {}), ("offsets", []), ("lower", {}), ("approved", 0)):
            p.setdefault(k, v)
        return p

    # ---------------------------------------------------------------- audit trail
    def record(self, entry: dict):
        with LOCK:
            self.data["decisions"].append({"at": now_iso(), **entry})
            self.save()

    def audit(self, eid: str) -> list:
        return [d for d in self.data["decisions"] if d.get("entity_id") == eid]

    # ---------------------------------------------------------------- permissions
    def has_permission(self, eid: str) -> bool:
        p = self.data["prefs"].get(eid, {})
        if "permission" in p:
            return bool(p["permission"])
        c = kitdata.contacts().get(eid)
        return bool(c and c["standing_permission_holidays"])

    def permission_source(self, eid: str) -> str | None:
        p = self.data["prefs"].get(eid, {})
        if p.get("permission"):
            return f"granted by the owner on the decision page ({p.get('permission_at', '')[:10]})"
        if "permission" in p:
            return None
        c = kitdata.contacts().get(eid)
        if c and c["standing_permission_holidays"]:
            return "CRM: standing_permission_holidays=1 (granted in the 2025 pilot)"
        return None

    def set_permission(self, eid: str, value: bool):
        with LOCK:
            p = self.prefs(eid)
            p["permission"] = bool(value)
            p["permission_at"] = now_iso()
            self.save()

    # ---------------------------------------------------------------- learning from decisions
    def learn(self, eid: str, item: dict, decision: str, final_hours: str | None = None, reason: str | None = None):
        """decision: approve | edit | decline (item = the suggestion dict that was shown)."""
        with LOCK:
            p = self.prefs(eid)
            k = item["day_key"]
            if decision == "approve":
                p["approved"] += 1
                p["lower"].pop(k, None)
            elif decision == "edit" and final_hours:
                if final_hours != item.get("hours"):
                    p["day_hours"][k] = {"hours": final_hours, "from": item.get("hours"), "date": item["date"],
                                         "at": now_iso()}
                    off = offset_of(item.get("hours"), final_hours)
                    if off and off != (0, 0):
                        p["offsets"].append({"open": off[0], "close": off[1], "day_key": k, "at": now_iso()})
                p["lower"].pop(k, None)
                p["suppress"].pop(k, None)
            elif decision == "decline":
                if reason in ("open_as_usual", "not_this_year"):
                    p["suppress"][k] = {"reason": reason, "season": season(item["date"]), "at": now_iso(),
                                        "date": item["date"], "suggested": item.get("hours")}
                else:
                    p["lower"][k] = round(min(0.5, p["lower"].get(k, 0) + (0.3 if reason == "different_hours"
                                                                             else 0.2)), 2)
            self.save()

    # ---------------------------------------------------------------- apply to a fresh suggestion
    def adjust(self, eid: str, s: dict) -> dict:
        """Apply what we know about this owner to one suggestion dict (returns a new dict)."""
        s = dict(s)
        s["reasons"] = list(s.get("reasons", []))
        s.setdefault("learned", [])
        if s["action"] != "SUGGEST":
            return s
        k = s["day_key"]
        p = self.data["prefs"].get(eid, {})
        pri = pilot_priors()["entities"].get(eid)

        # 1. explicit "no" for this kind of day
        sup = (p.get("suppress") or {}).get(k)
        if sup and (sup["reason"] == "open_as_usual" or sup["season"] == season(s["date"])):
            s["action"], s["suppressed"] = "NO_ACTION", True
            label = DECLINE_REASONS[sup["reason"]]
            s["learned"].append(f"Not suggested: on {sup['at'][:10]} the owner declined {k} ({label}).")
            return s
        if pri:
            for r in pri["rejects"]:
                if r["day_key"] == k and r["suggested"] == s.get("hours"):
                    s["action"], s["suppressed"] = "NO_ACTION", True
                    s["learned"].append(f"Not suggested: in the 2025 pilot the owner rejected {s.get('hours')} for "
                                        f"{k}" + (f" (\"{r['comment']}\")" if r["comment"] else "") + ".")
                    return s

        # 2. the owner's own edited hours for this kind of day
        dh = (p.get("day_hours") or {}).get(k)
        if dh and dh["hours"] != s.get("hours"):
            s["learned"].append(f"Last time the owner changed {k} from {dh['from']} to {dh['hours']}; "
                                f"suggesting their hours instead of {s.get('hours')}.")
            s["hours"], s["basis"] = dh["hours"], "OWNER_EDIT"
            s["confidence"] = max(s.get("confidence", 0.6), 0.88)
        else:
            # 3. a consistent edit pattern (e.g. always closes 1 h earlier than suggested)
            offs = list(p.get("offsets") or [])
            if pri:
                offs += [dict(zip(("open", "close"), o)) for o in
                         (offset_of(e["suggested"], e["final"]) for e in pri["edits"]) if o]
            if offs and s.get("hours") and s["hours"] != "closed" and s.get("basis") != "OWNER_EDIT":
                do = int(statistics.median(o["open"] for o in offs))
                dc = int(statistics.median(o["close"] for o in offs))
                if do or dc:
                    from .hours import shift
                    new = shift(s["hours"], do, dc)
                    if new != s["hours"]:
                        s["learned"].append(f"Adjusted {s['hours']} -> {new}: the owner's past edits moved "
                                            f"opening {do:+d} min and closing {dc:+d} min.")
                        s["hours"] = new
                        s["adjusted"] = True

        # 4. softer confidence after a decline without a clear reason / "different hours"
        low = (p.get("lower") or {}).get(k)
        if low:
            s["confidence"] = round(max(0.05, s.get("confidence", 0.6) - low), 2)
            s["learned"].append(f"Confidence lowered by {low} after an earlier decline for {k}: we ask instead.")

        # 5. pilot prior: owners who usually accept get slightly more confident suggestions
        if pri and pri["n"] >= 3:
            rate = pri["ACCEPTED"] / pri["n"]
            delta = round(max(-0.1, min(0.1, (rate - pilot_priors()["global_accept_rate"]) * 0.2)), 2)
            if delta:
                s["confidence"] = round(min(0.97, max(0.05, s.get("confidence", 0.6) + delta)), 2)
        if p.get("approved"):
            s["confidence"] = round(min(0.97, s.get("confidence", 0.6) + 0.02 * min(p["approved"], 3)), 2)
        return s

    # ---------------------------------------------------------------- what Connect learned (console)
    def summary(self, eid: str) -> list:
        out = []
        pri = pilot_priors()["entities"].get(eid)
        if pri:
            out.append(f"2025 pilot: {pri['n']} suggestions: {pri['ACCEPTED']} accepted, {pri['EDITED']} edited, "
                       f"{pri['REJECTED']} rejected, {pri['NO_RESPONSE']} no reply.")
            for r in pri["rejects"]:
                out.append(f"2025 pilot: rejected {r['suggested']} for {r['day_key']}"
                           + (f" (\"{r['comment']}\")" if r["comment"] else "") + " -> won't suggest that again.")
            for e in pri["edits"]:
                out.append(f"2025 pilot: edited {e['day_key']} {e['suggested']} -> {e['final']} -> "
                           f"we shift similar suggestions the same way.")
        else:
            out.append("No 2025 pilot history: new to suggestions, so we ask rather than assume.")
        src = self.permission_source(eid)
        out.append(f"Standing permission for public holidays: {'YES, ' + src if src else 'no'}.")
        p = self.data["prefs"].get(eid, {})
        for k, v in (p.get("suppress") or {}).items():
            out.append(f"Declined {k} ({DECLINE_REASONS[v['reason']]}, {v['at'][:10]}) -> "
                       + ("won't suggest it again." if v["reason"] == "open_as_usual" else
                          f"quiet for the {v['season']} season."))
        for k, v in (p.get("day_hours") or {}).items():
            out.append(f"Edited {k}: {v['from']} -> {v['hours']} ({v['at'][:10]}) -> next time we suggest "
                       f"{v['hours']}.")
        if p.get("offsets"):
            do = int(statistics.median(o["open"] for o in p["offsets"]))
            dc = int(statistics.median(o["close"] for o in p["offsets"]))
            out.append(f"Edit pattern: opening {do:+d} min, closing {dc:+d} min vs our suggestions "
                       f"({len(p['offsets'])} edit(s)) -> applied to similar suggestions.")
        for k, v in (p.get("lower") or {}).items():
            out.append(f"Declined {k} without a clear reason -> confidence -{v}, we ask instead of suggesting.")
        if p.get("approved"):
            out.append(f"Approved {p['approved']} suggestion(s) as sent -> slightly more confident next time.")
        return out

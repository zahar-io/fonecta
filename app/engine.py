"""The loop: 1 Detect -> 2 Suggest -> 3 Contact -> 4 Decide -> 5 Apply (+ standing permission, undo, learning).

Nothing is written to Yext unless one of these authorities is present:
  * owner_decision      - the owner approved or edited (decision page, WhatsApp button, simulator)
  * standing_permission - the owner allowed "handle public holidays", the day is an official public holiday and
                          the suggestion is confident (>= 0.75); the owner is informed with a one-tap Undo
  * owner_undo          - the owner asked to undo an earlier change"""
from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import date, datetime, timedelta

from . import channels, config, kitdata, messages, links as tokens
from .learning import Learning, now_iso
from .suggest_source import get_source
from .yext import YextClient, YextError, detect_client, get_applier

LOCK = threading.RLock()
ASK_BELOW = 0.6          # lower confidence -> phrase as a question
AUTO_MIN_CONF = 0.75     # standing permission only covers confident suggestions
AUTHORITIES = ("owner_decision", "standing_permission", "owner_undo")


class NotAllowed(RuntimeError):
    pass


class Engine:
    def __init__(self, yext: YextClient | None = None, learning: Learning | None = None, state_path=None,
                 detect: YextClient | None = None):
        self.yext = yext or YextClient()
        self.detect_yext = detect or (yext if yext is not None else detect_client())
        self.applier = get_applier(self.yext)
        # owner simulator + reset only exist on the kit mock
        self.mock = self.detect_yext if self.detect_yext.is_mock else self.yext
        self.learning = learning or Learning()
        self.state_path = state_path or os.path.join(config.var_dir(), "state.json")
        self.state = {"cases": {}}
        if os.path.exists(self.state_path):
            with open(self.state_path, encoding="utf-8") as f:
                self.state = json.load(f)
        self.writes = []  # in-memory log of Yext writes this process made (with authority)

    # ---------------------------------------------------------------- persistence
    def save(self):
        with LOCK:
            tmp = self.state_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.state, f, ensure_ascii=False, indent=1)
            os.replace(tmp, self.state_path)

    def cases(self) -> list:
        return list(self.state["cases"].values())

    def case(self, cid: str) -> dict:
        c = self.state["cases"].get(cid)
        if not c:
            raise KeyError(cid)
        return c

    def cases_for(self, eid: str) -> list:
        return sorted([c for c in self.cases() if c["entity_id"] == eid], key=lambda c: c["created_at"])

    # ---------------------------------------------------------------- context
    @staticmethod
    def contact(eid: str) -> dict:
        return kitdata.contacts().get(eid) or {"contact_first_name": "", "preferred_channel": "EMAIL",
                                               "preferred_language": "en", "best_contact_window": "10-12",
                                               "standing_permission_holidays": False,
                                               "opted_out_of_suggestions": False, "mobile": "", "email": ""}

    def ctx(self, c: dict) -> dict:
        evs = {}
        for it in c["items"]:
            if it.get("event_id"):
                ev = kitdata.local_events().get(it["event_id"])
                if ev:
                    evs[it["event_id"]] = (ev.get("name") or {}).get(c["lang"]) or (ev.get("name") or {}).get("en")
                elif it.get("event_name"):
                    evs[it["event_id"]] = it["event_name"]
        return {"lang": c["lang"], "first": c["first"] or c["name"], "name": c["name"],
                "views": c.get("views30"), "events": evs}

    @staticmethod
    def send_time(window: str, now: datetime | None = None) -> str:
        """Next moment inside the owner's best contact window (Helsinki time)."""
        try:
            from zoneinfo import ZoneInfo
            tz = ZoneInfo(config.TZ)
        except Exception:
            tz = None
        now = now or datetime.now(tz)
        try:
            a, b = (int(x) for x in window.split("-"))
        except Exception:
            return now.isoformat(timespec="minutes")
        if a <= now.hour < b:
            return now.isoformat(timespec="minutes")
        start = now.replace(hour=a, minute=0, second=0, microsecond=0)
        if now.hour >= b:
            start += timedelta(days=1)
        return start.isoformat(timespec="minutes")

    # ---------------------------------------------------------------- 1+2 detect & suggest
    def suggestions(self, eid: str) -> list:
        """Source suggestions with learning applied and the mode decided (suggest / ask)."""
        out = []
        country = (kitdata.entities().get(eid) or {}).get("meta", {}).get("countryCode", "FI")
        for s in get_source(self.detect_yext).get_suggestions(eid):
            s = self.learning.adjust(eid, s)
            if s["action"] == "SUGGEST" and s["hours"] == s["shown_hours"]:
                s["action"] = "NO_ACTION"
            s["mode"] = "ask" if s["action"] == "SUGGEST" and s["confidence"] < ASK_BELOW else "suggest"
            s["shown_is_exception"] = any("exception of" in r for r in s.get("reasons", []))
            if s["action"] != "NO_ACTION":
                s["at_risk"] = kitdata.at_risk_views(eid, country, s["day_key"], date.fromisoformat(s["date"]))
            out.append(s)
        out.extend(self.event_suggestions(eid, {s["date"] for s in out if s["action"] != "NO_ACTION"}))
        return out

    # ---------------------------------------------------------------- live data: events nearby
    EVENT_TXT = {"fi": "{name} ({venue}, {dist} m päässä) päättyy noin klo {end}.",
                 "sv": "{name} ({venue}, {dist} m bort) slutar runt {end}.",
                 "nb": "{name} ({venue}, {dist} m unna) slutter rundt {end}.",
                 "en": "{name} ({venue}, {dist} m away) ends around {end}."}
    LATE_SEGMENTS = ("bar_pub", "restaurant", "pizzeria")

    def event_suggestions(self, eid: str, taken: set) -> list:
        if os.environ.get("LIVE_EVENTS", "1") != "1":
            return []
        from . import events
        ent = kitdata.entities().get(eid) or {}
        if ent.get("c_segment") not in self.LATE_SEGMENTS:
            return []
        geo = ent.get("geocodedCoordinate") or {}
        if not geo:
            return []
        lang = messages.lang_of(os.environ.get("DEMO_LANG") or self.contact(eid)["preferred_language"])
        out = []
        days = int(os.environ.get("EVENT_DAYS", "3"))
        for k in range(1, days + 1):
            d = config.SNAPSHOT + timedelta(days=k)
            if d.isoformat() in taken:
                continue
            try:
                evs = (events.helsinki(geo["latitude"], geo["longitude"], d)
                       if ent["address"]["city"] == "Helsinki" else [])
            except Exception:
                evs = []
            evs += events.curated(geo["latitude"], geo["longitude"], d)
            day = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"][d.weekday()]
            h = (ent.get("hours") or {}).get(day) or {}
            if h.get("isClosed") or not h.get("openIntervals"):
                continue
            o, c = h["openIntervals"][0]["start"], h["openIntervals"][-1]["end"]
            late = events.late_suggestion(c, evs, d)
            if not late:
                continue
            ev = late["event"]
            end = ev["end"][11:16] if ev["end"][:10] == d.isoformat() else ev.get("evening_end", "")
            txt = {lg: t.format(name=ev["name"], venue=ev["venue"], dist=ev["distance_m"], end=end)
                   for lg, t in self.EVENT_TXT.items()}
            out.append({"entity_id": eid, "date": d.isoformat(), "day_key": "EVENT", "day_type": "EVENT",
                        "event_id": "live:" + str(ev["id"]), "event_name": ev["name"], "name_en": ev["name"],
                        "public_holiday": False, "weekday": d.weekday(), "shown_hours": f"{o}-{c}",
                        "action": "SUGGEST", "hours": f"{o}-{late['new_close']}", "confidence": 0.5,
                        "mode": "ask", "basis": "LIVE_EVENT", "shown_is_exception": False,
                        "reasons": [txt[lang], f"Source: {ev['source']}." + (f" {ev['url']}" if ev.get("url") else ""),
                                    txt["en"] if lang != "en" else "Open later = more customers; the owner decides."],
                        "evidence": {"event": ev}, "at_risk": {"views": 0}})
        return out

    def run_detection(self, ids=None) -> list:
        ids = ids or (config.DEMO_IDS + [x for x in os.environ.get("DEMO_EXTRA", "FI-00125").split(",") if x])
        made = []
        for eid in ids:
            if eid not in kitdata.entities():
                continue
            with LOCK:
                made.append(self._detect_one(eid))
        self.save()
        return made

    def _decided_dates(self, eid):
        return {i["date"] for c in self.cases_for(eid) for i in c["items"]
                if i["status"] in ("approved", "edited", "declined", "auto-applied", "undone", "kept")}

    def _detect_one(self, eid: str) -> str:
        # an open, unsent case is refreshed; a sent one is left alone (never message an owner twice)
        for c in self.cases_for(eid):
            if c["status"] in ("pending", "flagged", "quiet", "opted out"):
                del self.state["cases"][c["id"]]
            elif c["status"] == "sent":
                return c["id"]
        ent = kitdata.entities()[eid]
        con = self.contact(eid)
        decided = self._decided_dates(eid)
        sugg = self.suggestions(eid)
        items = [dict(s, status="flagged" if s["action"] == "FLAG" else "pending")
                 for s in sugg if s["action"] in ("SUGGEST", "FLAG") and s["date"] not in decided]
        quiet = [s for s in sugg if s["action"] == "NO_ACTION"]
        cid = f"c-{eid}-{uuid.uuid4().hex[:6]}"
        v = kitdata.views_last_30_days(eid)
        c = {"id": cid, "entity_id": eid, "name": ent["name"], "city": ent["address"]["city"],
             "segment": ent.get("c_segment"), "country": ent["meta"]["countryCode"],
             "first": os.environ.get("DEMO_FIRST") or con["contact_first_name"],
             "lang": messages.lang_of(os.environ.get("DEMO_LANG") or con["preferred_language"]),
             "channel_pref": con["preferred_channel"], "window": con["best_contact_window"],
             "to_phone": con.get("mobile"), "to_email": con.get("email"),
             "opted_out": con["opted_out_of_suggestions"], "created_at": now_iso(), "items": items,
             "quiet": [{k: q.get(k) for k in ("date", "day_key", "shown_hours", "basis", "reasons", "learned",
                                              "suppressed")} for q in quiet],
             "views30": v["search_map"], "views30_range": [v["start"], v["end"]],
             "priority": sum(i.get("at_risk", {}).get("views", 0) for i in items if i["action"] == "SUGGEST"),
             "send_at": self.send_time(con["best_contact_window"]), "outbox": [], "applied": [],
             "source": get_source(self.detect_yext).name, "status": "pending"}
        self.state["cases"][cid] = c
        if c["opted_out"]:
            for i in items:
                if i["status"] == "pending":
                    i["status"] = "opted out"
        elif self.learning.has_permission(eid):
            self._auto_apply(c)
        self._refresh(c)
        return cid

    # ---------------------------------------------------------------- status
    @staticmethod
    def _refresh(c: dict):
        st = [i["status"] for i in c["items"]]
        if c.get("opted_out") and any(i["action"] == "SUGGEST" for i in c["items"]):
            c["status"] = "opted out"
        elif not st:
            c["status"] = "quiet"
        elif all(s == "flagged" for s in st):
            c["status"] = "flagged"
        elif "pending" in st:
            c["status"] = "pending"
        elif "sent" in st:
            c["status"] = "sent"
        elif "undone" in st:
            c["status"] = "undone"
        elif "edited" in st:
            c["status"] = "edited"
        elif "approved" in st:
            c["status"] = "approved"
        elif "auto-applied" in st:
            c["status"] = "auto-applied"
        else:
            c["status"] = "declined"

    # ---------------------------------------------------------------- the only way to write
    def _write(self, eid: str, changes: dict, authority: dict) -> dict:
        if authority.get("kind") not in AUTHORITIES:
            raise NotAllowed("no write without an owner decision, a standing permission or an owner undo")
        if authority["kind"] == "owner_decision" and not authority.get("decision_id"):
            raise NotAllowed("owner decision without an id")
        res = self.applier.apply(eid, changes)
        self.writes.append({"at": now_iso(), "entity_id": eid, "changes": changes, "authority": authority})
        return res

    def where_live(self, eid: str) -> list:
        try:
            return self.yext.where_live(eid)
        except YextError:
            return []

    # ---------------------------------------------------------------- standing permission
    def _auto_apply(self, c: dict):
        eid = c["entity_id"]
        todo = [i for i in c["items"] if i["status"] == "pending" and i["action"] == "SUGGEST"
                and i.get("public_holiday") and i["confidence"] >= AUTO_MIN_CONF and i["mode"] == "suggest"]
        if not todo:
            return
        changes = {i["date"]: i["hours"] for i in todo}
        try:
            res = self._write(eid, changes, {"kind": "standing_permission",
                                             "source": self.learning.permission_source(eid)})
        except (YextError, NotImplementedError) as ex:
            c["error"] = f"auto-apply failed: {ex}"
            return
        for i in todo:
            i["status"] = "auto-applied"
            i["final_hours"] = i["hours"]
        c["applied"].append({"at": now_iso(), "authority": "standing_permission", "changes": changes,
                             "previous": res["previous"], "warnings": res.get("warnings")})
        live = self.where_live(eid)
        c["live"] = live
        undo = tokens.sign({"c": c["id"], "e": eid, "u": 1})
        c["undo_token"] = undo
        text = messages.auto_applied(self.ctx(c), [dict(i, final_hours=i["hours"]) for i in todo], live,
                                     f"{config.public_base()}/s/{undo}")
        self._deliver_text(c, text, "inform (auto-applied)")
        for i in todo:
            self.learning.record({"entity_id": eid, "case_id": c["id"], "type": "auto-applied", "date": i["date"],
                                  "day_key": i["day_key"], "suggestion": i["hours"], "basis": i["basis"],
                                  "confidence": i["confidence"], "reasons": i["reasons"], "final_hours": i["hours"],
                                  "authority": "standing_permission", "channel": self._chan_name(c),
                                  "message": text})

    # ---------------------------------------------------------------- 3 contact
    def _chan(self, c: dict, via: str | None = None):
        if via == "whatsapp":
            return channels.WhatsAppCloudChannel() if channels.wa_configured() else channels.PreviewChannel("WHATSAPP")
        if c.get("via") == "whatsapp" and channels.wa_configured():
            return channels.WhatsAppCloudChannel()
        return channels.channel_for(c["channel_pref"])

    def _chan_name(self, c, via=None):
        ch = self._chan(c, via)
        return "whatsapp" if ch.real else f"preview:{c['channel_pref'] if via != 'whatsapp' else 'WHATSAPP'}"

    def _deliver_text(self, c: dict, text: str, kind: str):
        ch = self._chan(c)
        res = ch.send_text(c.get("to_phone"), text)
        c["outbox"].append({"at": now_iso(), "kind": kind, "channel": self._chan_name(c), "text": text,
                            "result": res})

    def compose(self, c: dict) -> dict | None:
        items = [i for i in c["items"] if i["status"] in ("pending", "sent") and i["action"] == "SUGGEST"]
        if not items:
            return None
        tok = c.get("token") or tokens.sign({"c": c["id"], "e": c["entity_id"]})
        c["token"] = tok
        return messages.compose(self.ctx(c), items, f"{config.public_base()}/s/{tok}")

    def send(self, cid: str, via: str | None = None) -> dict:
        with LOCK:
            c = self.case(cid)
            if c.get("opted_out"):
                raise NotAllowed("owner opted out of suggestions: nothing is sent")
            if c["status"] not in ("pending", "sent"):
                raise NotAllowed(f"case is {c['status']}: nothing to send")
            msg = self.compose(c)
            if not msg:
                raise NotAllowed("nothing to send")
            if via:
                c["via"] = via
            ch = self._chan(c, via)
            tok = c["token"]
            per_date = ch.real and os.environ.get("WA_PER_DATE", "1") == "1"
            if per_date:  # each decision gets its own message; only back-to-back days (or one event) share one
                res = None
                for grp in self.groups([i for i in c["items"] if i["status"] == "pending" and i["action"] == "SUGGEST"]):
                    ds = [i["date"] for i in grp]
                    t1 = tokens.sign({"c": c["id"], "e": c["entity_id"], "ds": ds})
                    m1 = messages.compose(self.ctx(c), grp, f"{config.public_base()}/s/{t1}")
                    try:
                        from .cards import hours_card
                        m1["wa"]["image"] = hours_card(c["name"], [dict(i, entity_id=c["entity_id"]) for i in grp], c["lang"])
                    except Exception:
                        pass
                    res = ch.send_suggestion(c.get("to_phone"), m1, [f"a:{t1}", f"e:{t1}", f"d:{t1}"])
                    for i in grp:
                        i["token"] = t1
                    c["outbox"].append({"at": now_iso(), "kind": "suggestion " + ", ".join(ds),
                                        "channel": self._chan_name(c, via), "text": m1["text"], "result": res})
            else:
                res = ch.send_suggestion(c.get("to_phone"), msg, [f"a:{tok}", f"e:{tok}", f"d:{tok}"])
                c["outbox"].append({"at": now_iso(), "kind": "suggestion", "channel": self._chan_name(c, via),
                                    "text": msg["text"], "result": res})
            c["message"] = msg
            for i in c["items"]:
                if i["status"] == "pending" and i["action"] == "SUGGEST":
                    i["status"] = "sent"
            self.learning.record({"entity_id": c["entity_id"], "case_id": cid, "type": "sent",
                                  "channel": self._chan_name(c, via), "message": msg["text"],
                                  "suggestions": [{k: i.get(k) for k in ("date", "day_key", "hours", "mode",
                                                                         "confidence", "basis", "reasons")}
                                                  for i in c["items"] if i["status"] == "sent"]})
            self._refresh(c)
            self.save()
            return {"case": cid, "result": res, "message": msg}

    def owner_request(self, eid: str, changes: dict, channel: str = "whatsapp chat") -> dict:
        """The owner asked for a change in their own words and confirmed it with Save: write it, log it, confirm."""
        with LOCK:
            did = uuid.uuid4().hex[:10]
            res = self._write(eid, changes, {"kind": "owner_decision", "decision_id": did, "channel": channel})
            for d, h in changes.items():
                self.learning.record({"entity_id": eid, "type": "owner request", "decision_id": did, "date": d,
                                      "final_hours": h, "channel": channel})
            return {"previous": res.get("previous"), "live": self.where_live(eid)}

    def shown_on(self, eid: str, d: str) -> str:
        """What Google shows for a date right now, read from Yext (exception if any, else the weekday hours)."""
        from .hours import day_str
        try:
            hours = (self.yext.get_entity(eid, "hours") or {}).get("hours") or {}
        except Exception:
            return "?"
        for h in hours.get("holidayHours") or []:
            if h.get("date") == d and not h.get("isRegularHours"):
                return day_str(h)
        wd = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"][date.fromisoformat(d).weekday()]
        return day_str(hours.get(wd) or {})

    @staticmethod
    def groups(items: list) -> list:
        """Back-to-back days (e.g. 24-26 Dec) or the same event go in one message (max 4); everything else alone."""
        out = []
        for it in sorted(items, key=lambda i: i["date"]):
            if out:
                last = out[-1][-1]
                gap = (date.fromisoformat(it["date"]) - date.fromisoformat(last["date"])).days
                same_event = it.get("event_id") and it.get("event_id") == last.get("event_id")
                if (gap == 1 or same_event) and len(out[-1]) < 4:
                    out[-1].append(it)
                    continue
            out.append([it])
        return out

    # ---------------------------------------------------------------- 4 decide + 5 apply
    def decide(self, cid: str, decisions: dict, reason: str | None = None, permission: bool = False,
               channel: str = "page") -> dict:
        """decisions: {date: {"action": approve|edit|decline, "hours": "..."}}. Unlisted open dates are left."""
        with LOCK:
            c = self.case(cid)
            eid = c["entity_id"]
            open_items = {i["date"]: i for i in c["items"] if i["status"] in ("pending", "sent")
                          and i["action"] == "SUGGEST"}
            did = uuid.uuid4().hex[:10]
            changes, applied, edited_any, declined = {}, [], False, []
            for d, dec in decisions.items():
                it = open_items.get(d)
                if not it:
                    continue
                act = dec.get("action")
                if act == "edit":
                    h = (dec.get("hours") or "").strip().lower()
                    from .hours import is_valid
                    if not is_valid(h):
                        raise ValueError(f"invalid hours for {d}: {h!r}")
                    if h == it["hours"]:
                        act = "approve"
                    else:
                        changes[d] = h
                        edited_any = True
                        applied.append((it, "edit", h))
                        continue
                if act == "approve":
                    changes[d] = it["hours"]
                    applied.append((it, "approve", it["hours"]))
                elif act == "decline":
                    declined.append(it)
            res = None
            if changes:
                res = self._write(eid, changes, {"kind": "owner_decision", "decision_id": did, "channel": channel})
                c["applied"].append({"at": now_iso(), "authority": "owner_decision", "decision_id": did,
                                     "changes": changes, "previous": res["previous"],
                                     "warnings": res.get("warnings")})
            for it, act, h in applied:
                it["status"] = "edited" if act == "edit" else "approved"
                it["final_hours"] = h
                self.learning.learn(eid, it, act, h)
            for it in declined:
                it["status"] = "declined"
                it["decline_reason"] = reason
                self.learning.learn(eid, it, "decline", reason=reason)
            if permission:
                self.learning.set_permission(eid, True)
            for it, act, h in applied:
                self._audit_decision(c, it, "edited" if act == "edit" else "approved", h, channel, did)
            for it in declined:
                self._audit_decision(c, it, "declined", None, channel, did, reason)
            out = {"case": cid, "applied": [{"date": it["date"], "final_hours": h, "action": a}
                                            for it, a, h in applied],
                   "declined": [it["date"] for it in declined], "permission": permission}
            if applied:
                live = self.where_live(eid)
                c["live"] = live
                text = messages.confirmation(self.ctx(c), [dict(it, final_hours=h) for it, _, h in applied], live,
                                             edited_any, kept=len(declined), permission=permission)
                out.update(live=live, confirmation=text)
                self._deliver_text(c, text, "confirmation")
            elif declined:
                text = messages.declined(self.ctx(c))
                out["confirmation"] = text
                self._deliver_text(c, text, "decline ack")
            self._refresh(c)
            self.save()
            return out

    def _audit_decision(self, c, it, decision, final, channel, did, reason=None):
        self.learning.record({"entity_id": c["entity_id"], "case_id": c["id"], "type": "decision",
                              "decision_id": did, "date": it["date"], "day_key": it["day_key"],
                              "suggestion": it["hours"], "mode": it.get("mode"), "basis": it.get("basis"),
                              "confidence": it.get("confidence"), "reasons": it.get("reasons"),
                              "channel": channel, "message": (c.get("message") or {}).get("text"),
                              "decision": decision, "final_hours": final, "decline_reason": reason})

    def decide_all(self, cid: str, action: str, reason=None, permission=False, channel="page") -> dict:
        c = self.case(cid)
        decs = {i["date"]: {"action": action} for i in c["items"] if i["status"] in ("pending", "sent")
                and i["action"] == "SUGGEST"}
        return self.decide(cid, decs, reason=reason, permission=permission, channel=channel)

    def decline_reason(self, cid: str, reason: str):
        """Owner tapped a reason chip after 'No thanks': update learning for the declined dates."""
        with LOCK:
            c = self.case(cid)
            for it in c["items"]:
                if it["status"] == "declined":
                    it["decline_reason"] = reason
                    self.learning.learn(c["entity_id"], it, "decline", reason=reason)
            self.learning.record({"entity_id": c["entity_id"], "case_id": cid, "type": "decline reason",
                                  "decline_reason": reason})
            self.save()

    # ---------------------------------------------------------------- undo (auto-applied changes)
    def undo(self, cid: str, channel="page") -> dict:
        with LOCK:
            c = self.case(cid)
            eid = c["entity_id"]
            batch = next((a for a in reversed(c["applied"]) if a["authority"] == "standing_permission"
                          and not a.get("undone")), None)
            if not batch:
                return {"case": cid, "undone": []}
            restore = {d: batch["previous"].get(d) for d in batch["changes"]}
            self._write(eid, restore, {"kind": "owner_undo", "case": cid})
            batch["undone"] = now_iso()
            dates = list(batch["changes"])
            for it in c["items"]:
                if it["date"] in dates and it["status"] == "auto-applied":
                    it["status"] = "undone"
                    self.learning.learn(eid, it, "decline", reason=None)
                    self._audit_decision(c, it, "undone", None, channel, "undo")
            text = messages.undone(self.ctx(c))
            self._deliver_text(c, text, "undo ack")
            self._refresh(c)
            self.save()
            return {"case": cid, "undone": dates, "confirmation": text}

    # ---------------------------------------------------------------- owner simulator (mock only)
    def simulate(self, cid: str) -> dict:
        c = self.case(cid)
        if c["status"] == "pending":
            self.send(cid)
        decs, sim = {}, []
        for it in c["items"]:
            if it["status"] != "sent":
                continue
            try:
                r = self.mock.owner_response(c["entity_id"], it["date"], it["hours"], c["channel_pref"])
            except YextError as ex:
                sim.append({"date": it["date"], "error": str(ex)})
                continue
            sim.append({"date": it["date"], **r})
            if r["decision"] == "ACCEPTED":
                decs[it["date"]] = {"action": "approve"}
            elif r["decision"] == "EDITED":
                decs[it["date"]] = {"action": "edit", "hours": r["final_hours"]}
            elif r["decision"] == "REJECTED":
                decs[it["date"]] = {"action": "decline"}
        out = self.decide(cid, decs, channel="owner simulator") if decs else {"case": cid}
        out["simulator"] = sim
        c = self.case(cid)
        c.setdefault("simulations", []).append({"at": now_iso(), "answers": sim})
        self.save()
        return out

    # ---------------------------------------------------------------- escalation (hierarchy)
    @staticmethod
    def approvers(eid: str) -> list:
        """Who may approve for a business, in escalation order. Owner first, then backups from
        app/var/approvers.json {"FI-D0001": [{"name": "Mikko (manager)", "phone": "+358...", "lang": "fi"}]}."""
        path = os.path.join(config.var_dir(), "approvers.json")
        extra = []
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                extra = json.load(f).get(eid, [])
        return extra

    def escalate(self, cid: str, force: bool = False) -> dict:
        """No answer within ESCALATE_HOURS (default 24): send the same suggestion to the next approver.
        Any approver's tap decides (the link is the same case), and the audit trail records who."""
        with LOCK:
            c = self.case(cid)
            if c["status"] != "sent":
                raise NotAllowed(f"case is {c['status']}: nothing to escalate")
            sent_at = next((o["at"] for o in c["outbox"] if o["kind"] == "suggestion"), None)
            hours = float(os.environ.get("ESCALATE_HOURS", "24"))
            if not force and sent_at and datetime.fromisoformat(sent_at) > datetime.fromisoformat(now_iso()) - timedelta(hours=hours):
                return {"case": cid, "escalated": False, "why": f"waiting: less than {hours:g} h since sent"}
            level = c.get("escalation", 0)
            chain = self.approvers(c["entity_id"])
            if level >= len(chain):
                return {"case": cid, "escalated": False, "why": "no more approvers: Connect support takes it"}
            who = chain[level]
            msg = dict(self.compose(c))
            if c["first"]:
                nm = who.get("name", "").split(" ")[0]
                for k in ("body", "text"):
                    head, _, rest = msg[k].partition("\n")
                    msg[k] = head.replace(c["first"], nm) + "\n" + rest
            note = {"fi": f"{c['first'] or c['name']} ei ole vielä vastannut, joten kysymme sinulta.",
                    "sv": f"{c['first'] or c['name']} har inte svarat än, så vi frågar dig.",
                    "nb": f"{c['first'] or c['name']} har ikke svart ennå, så vi spør deg.",
                    "en": f"{c['first'] or c['name']} hasn't answered yet, so we're asking you."}[c["lang"]]
            text = msg["text"].replace("\n", "\n" + note + "\n", 1)
            ch = self._chan(c)
            tok = c["token"]
            res = ch.send_suggestion(who.get("phone"), dict(msg, body=msg["body"].replace("\n", "\n" + note + "\n", 1), text=text),
                                     [f"a:{tok}", f"e:{tok}", f"d:{tok}"])
            c["outbox"].append({"at": now_iso(), "kind": f"escalation to {who.get('name')}",
                                "channel": self._chan_name(c), "text": text, "result": res})
            c["escalation"] = level + 1
            self.learning.record({"entity_id": c["entity_id"], "case_id": cid, "type": "escalated",
                                  "to": who.get("name"), "level": level + 1})
            self.save()
            return {"case": cid, "escalated": True, "to": who.get("name")}

    # ---------------------------------------------------------------- urgent: call the owner
    def urgent_call(self, cid: str, force: bool = False) -> dict:
        from . import call
        with LOCK:
            c = self.case(cid)
            if c["status"] != "sent":
                raise NotAllowed(f"case is {c['status']}: nothing to call about")
            open_items = sorted([i for i in c["items"] if i["status"] == "sent"], key=lambda i: i["date"])
            first = open_items[0]
            due_h = (datetime.fromisoformat(first["date"]) - datetime.combine(config.SNAPSHOT, datetime.min.time())
                     ).total_seconds() / 3600
            within = float(os.environ.get("URGENT_WITHIN_H", "48"))
            if not force and due_h > within:
                return {"case": cid, "called": False, "why": f"not urgent: first date is {due_h:.0f} h away"}
            if c.get("called"):
                return {"case": cid, "called": False, "why": "already called once: we never call twice"}
            lang = c["lang"]
            d = date.fromisoformat(first["date"])
            what = messages.bullet(first, lang, first.get("event_name")).lstrip("• ")
            text = call.script(lang, first=c["first"] or c["name"], name=c["name"],
                               when=f"{messages.WD_LONG[lang][d.weekday()]} {messages.dm(d, lang)}", what=what)
            res = call.place(text, f"Connect Suggests demo: urgent hours suggestion for {c['name']} ({first['date']}). "
                                   f"Explain it in {lang} and ask the owner to tap Approve in the message.")
            c["called"] = now_iso()
            c["outbox"].append({"at": now_iso(), "kind": "urgent call", "channel": res.get("transport"), "text": text,
                                "result": res})
            self.learning.record({"entity_id": c["entity_id"], "case_id": cid, "type": "urgent call",
                                  "transport": res.get("transport"), "dialled": res.get("dialled")})
            self.save()
            return {"case": cid, "called": True, **res}

    # ---------------------------------------------------------------- reset
    def reset(self, keep_learning: bool = False) -> dict:
        with LOCK:
            try:
                r = self.mock.reset()
            except YextError as ex:
                r = {"error": str(ex)}
            self.state = {"cases": {}}
            self.writes = []
            if not keep_learning:
                self.learning.clear()
            self.save()
            return {"mock": r, "kept_learning": keep_learning}

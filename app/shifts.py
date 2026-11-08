"""Staff-shift check: the evening before, look at tomorrow's schedule (a shift platform's API in production,
app/data/shifts_demo.json here) and tell the owner if nobody has claimed the shift that opens the business.
FYI only: the owner decides (message the team, close tomorrow, or ignore). Nothing changes without a tap."""
from __future__ import annotations

import json
import os
from datetime import date, timedelta

from . import config

PATH = os.path.join(os.path.dirname(__file__), "data", "shifts_demo.json")


def _data() -> dict:
    with open(PATH, encoding="utf-8") as f:
        return json.load(f)


def schedule(eid: str, day: date, state: dict | None = None) -> list:
    """Tomorrow's shifts for a business: the weekly pattern plus any change (a dropped shift) from the platform."""
    biz = _data().get(eid)
    if not biz:
        return []
    from . import kitdata
    from .hours import minutes
    wd = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"][day.weekday()]
    iv = ((kitdata.entities().get(eid, {}).get("hours") or {}).get(wd) or {}).get("openIntervals") or []
    if not iv:
        return []
    o, c = minutes(iv[0]["start"]), minutes(iv[-1]["end"])
    mid = (o + c) // 2 // 30 * 30
    hm = lambda m: f"{m // 60:02d}:{m % 60:02d}"  # noqa: E731
    rows = [{"start": hm(o - 30), "end": hm(mid), "role": "Opening barista", "who": biz["staff"]["opening"],
             "opens_at": hm(o)},
            {"start": hm(mid), "end": hm(c), "role": "Closing barista", "who": biz["staff"]["closing"]}]
    ov = ((state or {}).get("shift_overrides", {}).get(eid, {}) or biz.get("overrides", {})).get(day.isoformat(), {})
    for r in rows:
        if r["start"] in ov:
            r["who"] = ov[r["start"]]
    return rows


def opening_gap(eid: str, day: date, state: dict | None = None) -> dict | None:
    """The first shift of the day with nobody on it, if any."""
    rows = sorted(schedule(eid, day, state), key=lambda r: r["start"])
    return next((r for r in rows[:1] if not r.get("who")), None)


def alert_text(first: str, name: str, day: date, gap: dict) -> str:
    wd = day.strftime("%A")
    return (f"Heads-up, {first}: nobody has claimed tomorrow's opening shift at {name} "
            f"({wd} {_ampm(gap['start'])}–{_ampm(gap['end'])}, {gap['role'].lower()}).\n\n"
            f"Just so you know before tonight. Want me to set {name} to closed tomorrow morning on Google, "
            f"or will you sort it?")


def _ampm(h: str) -> str:
    """24-hour time, never am/pm: '9:00' -> '09:00'."""
    hh, mm = (int(x) for x in h.split(":"))
    return f"{hh:02d}:{mm:02d}"


def tomorrow() -> date:
    try:
        from datetime import datetime
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo(config.TZ)).date() + timedelta(days=1)
    except Exception:
        return date.today() + timedelta(days=1)

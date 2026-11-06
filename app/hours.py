"""Hours strings ('closed' | '10:00-15:00' | '10:00-14:00,17:00-22:00') <-> Yext objects, and the merge."""
from __future__ import annotations

import copy
import re

DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
_IV = re.compile(r"^([01]\d|2[0-3]):[0-5]\d-([01]\d|2[0-3]):[0-5]\d$")


def is_valid(s: str) -> bool:
    s = (s or "").strip().lower()
    if s == "closed":
        return True
    parts = s.split(",")
    return bool(parts) and all(_IV.match(p) and p[:5] != p[6:] for p in parts)


def to_yext_day(s: str) -> dict:
    s = s.strip().lower()
    if s == "closed":
        return {"isClosed": True}
    return {"openIntervals": [{"start": a, "end": b} for a, b in (iv.split("-") for iv in s.split(","))]}


def day_str(obj) -> str:
    if not obj or obj.get("isClosed"):
        return "closed"
    return ",".join(f"{i['start']}-{i['end']}" for i in obj.get("openIntervals", [])) or "closed"


def holiday_entry_str(item: dict) -> str:
    """Holiday entry -> 'REGULAR' | 'closed' | intervals."""
    if item.get("isRegularHours"):
        return "REGULAR"
    return day_str(item)


def merge_holiday_hours(hours_obj: dict, changes: dict, today: str | None = None) -> dict:
    """Return a NEW full hours object with holidayHours for `changes` {iso date: hours string or None} set.
    None removes that date's exception (used by undo when there was nothing before). Weekday hours and
    unrelated future holiday dates are kept untouched. Yext replaces the whole holidayHours list on PUT and
    rejects past dates, so: past dates (< today) are dropped, one entry per date, sorted by date."""
    out = copy.deepcopy(hours_obj or {})
    hol, seen = [], set()
    for h in out.get("holidayHours", []):
        d = h.get("date")
        if d in changes or d in seen or (today and d < today):
            continue
        seen.add(d)
        hol.append(h)
    for d, s in changes.items():
        if s is None:
            continue
        if isinstance(s, dict):  # a raw previous entry (undo)
            item = {k: v for k, v in s.items() if k != "date"}
            hol.append({"date": d, **item})
        else:
            hol.append({"date": d, **to_yext_day(s)})
    out["holidayHours"] = sorted(hol, key=lambda h: h["date"])
    return out


def minutes(t: str) -> int:
    return int(t[:2]) * 60 + int(t[3:5])


def hhmm(m: int) -> str:
    m %= 1440
    return f"{m // 60:02d}:{m % 60:02d}"


def shift(s: str, open_delta: int = 0, close_delta: int = 0) -> str:
    """Shift a single-interval hours string by minutes (keeps 'closed' and split hours unchanged)."""
    if s == "closed" or "," in s:
        return s
    a, b = s.split("-")
    na, nb = hhmm(minutes(a) + open_delta), hhmm(minutes(b) + close_delta)
    return f"{na}-{nb}" if na != nb else s


def nice(s: str, lang: str = "en", closed_word: str = "closed") -> str:
    """'07:30-13:00' -> '7.30–13' (fi/sv/nb) or '7:30–13' (en)."""
    if s == "closed":
        return closed_word
    sep = ":" if lang == "en" else "."

    def t(x):
        hh, mm = x.split(":")
        return str(int(hh)) + ("" if mm == "00" else sep + mm)
    return ", ".join("–".join(t(x) for x in iv.split("-")) for iv in s.split(","))

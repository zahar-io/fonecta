"""Live data bonus: events next to a business -> "stay open later?" suggestions.

Sources
* Helsinki LinkedEvents (api.hel.fi/linkedevents/v1, CC BY 4.0): live, Helsinki region only.
* Curated events (app/data/curated_events.json): public events we add by hand where no open API exists.
  Turku's LinkedEvents endpoints (api.turku.fi, linkedevents-api.turku.fi) did not answer on 7 Nov 2026.
What we learned is written up in docs/LIVE_SOURCES.md.
"""
from __future__ import annotations

import json
import math
import os
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
UA = "flovr-connect-suggests-hackathon/1.0"
LATE_SEGMENTS = {"bar", "pub", "restaurant", "nightclub", "cafe", "sauna", "fast_food", "pizzeria", "kiosk", "bistro"}
MAX_DURATION_H = 8      # skip exhibitions and season-long entries
RADIUS_M = 1000


def dist_m(a, b) -> float:
    (la1, lo1), (la2, lo2) = a, b
    x = math.radians(lo2 - lo1) * math.cos(math.radians((la1 + la2) / 2))
    y = math.radians(la2 - la1)
    return 6371000 * math.hypot(x, y)


def _local(ts: str) -> datetime:
    """LinkedEvents times are UTC ('Z'); Helsinki is UTC+2 in Nov-Mar."""
    d = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return (d + timedelta(hours=2)).replace(tzinfo=None)


_DAY_CACHE: dict = {}


def _helsinki_day(day: date, timeout: int = 20) -> list:
    """All Helsinki-region events starting that day (one paged fetch per day, cached)."""
    if day in _DAY_CACHE:
        return _DAY_CACHE[day]
    q = {"start": f"{day.isoformat()}T12:00", "end": f"{(day + timedelta(days=1)).isoformat()}T00:00",
         "max_duration": f"{MAX_DURATION_H}h", "bbox": "24.80,60.12,25.20,60.30",
         "include": "location", "page_size": 100, "sort": "start_time"}
    url = "https://api.hel.fi/linkedevents/v1/event/?" + urllib.parse.urlencode(q)
    rows = []
    for _ in range(8):  # up to 800 events
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=timeout) as r:
            data = json.load(r)
        rows += data.get("data", [])
        url = (data.get("meta") or {}).get("next")
        if not url:
            break
    _DAY_CACHE[day] = rows
    return rows


def helsinki(lat: float, lon: float, day: date, radius_m: int = RADIUS_M, timeout: int = 20) -> list:
    out = []
    for e in _helsinki_day(day, timeout):
        try:
            st, en = _local(e["start_time"]), _local(e["end_time"] or e["start_time"])
        except Exception:
            continue
        if en <= st:  # end time missing or equal to start: assume a typical 2.5 h show
            en = st + timedelta(hours=2, minutes=30)
        if st.date() != day or (en - st) > timedelta(hours=MAX_DURATION_H) or st.hour < 15:
            continue
        loc = e.get("location") or {}
        pos = (loc.get("position") or {}).get("coordinates")
        if not pos:
            continue
        d = dist_m((lat, lon), (pos[1], pos[0]))
        if d > radius_m:
            continue
        name = e.get("name") or {}
        out.append({"id": e.get("id"), "name": name.get("fi") or name.get("en") or name.get("sv") or "event",
                    "venue": (loc.get("name") or {}).get("fi") or "", "start": st.isoformat(timespec="minutes"),
                    "end": en.isoformat(timespec="minutes"), "distance_m": int(d), "source": "Helsinki LinkedEvents (live)"})
    return out


def curated(lat: float, lon: float, day: date, radius_m: int = 3000) -> list:
    path = os.path.join(HERE, "data", "curated_events.json")
    if not os.path.exists(path):
        return []
    out = []
    for e in json.load(open(path, encoding="utf-8")):
        st, en = datetime.fromisoformat(e["start"]), datetime.fromisoformat(e["end"])
        if not (st.date() <= day <= en.date()):
            continue
        d = dist_m((lat, lon), (e["lat"], e["lon"]))
        if d <= radius_m:
            out.append(dict(e, distance_m=int(d), source="curated public event (manual)"))
    return out


def late_suggestion(close: str, events: list, day: date) -> dict | None:
    """If the biggest evening event ends after the business closes, propose closing 1 h after it ends."""
    if not events or not close:
        return None
    ev = max(events, key=lambda e: (e.get("expected_attendance") or 0, e["end"]))
    end = datetime.fromisoformat(ev["end"])
    if end.date() != day:  # multi-day event: use the evening programme end
        end = datetime.combine(day, datetime.strptime(ev.get("evening_end", "22:00"), "%H:%M").time())
    c_h, c_m = (int(x) for x in close.split(":"))
    if c_h < 6:  # already open past midnight
        return None
    target = end + timedelta(hours=1)
    close_dt = datetime.combine(day, datetime.strptime(close, "%H:%M").time())
    if target <= close_dt or target - close_dt > timedelta(hours=2):
        return None  # nothing to gain, or too big a change to propose
    if datetime.fromisoformat(ev["start"]) < close_dt - timedelta(hours=1) and end.date() == day:
        return None  # the crowd is out before closing time anyway
    return {"event": ev, "new_close": target.strftime("%H:%M")}

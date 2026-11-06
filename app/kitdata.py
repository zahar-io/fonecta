"""Read-only access to the starter-kit data files (cached)."""
from __future__ import annotations

import csv
import json
import os
from collections import defaultdict
from datetime import date, timedelta
from functools import lru_cache

from . import config


def _csv(name):
    with open(os.path.join(config.KIT_DATA, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))


@lru_cache(maxsize=1)
def contacts() -> dict:
    out = {}
    for r in _csv("customer_contacts.csv"):
        r["standing_permission_holidays"] = r["standing_permission_holidays"] == "1"
        r["opted_out_of_suggestions"] = r["opted_out_of_suggestions"] == "1"
        out[r["entity_id"]] = r
    return out


@lru_cache(maxsize=1)
def calendar() -> dict:
    """(country, iso date) -> row."""
    return {(r["country"], r["date"]): r for r in _csv("calendar_special_days.csv")}


@lru_cache(maxsize=1)
def dates_by_key() -> dict:
    out = defaultdict(list)
    for (c, d), r in calendar().items():
        out[(c, r["day_key"])].append(date.fromisoformat(d))
    return out


@lru_cache(maxsize=1)
def targets() -> dict:
    out = defaultdict(list)
    with open(config.TARGETS_CSV, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            out[r["entity_id"]].append(r)
    return out


@lru_cache(maxsize=1)
def entities() -> dict:
    with open(os.path.join(config.KIT_DATA, "entities.json"), encoding="utf-8") as f:
        return {e["meta"]["id"]: e for e in json.load(f)["response"]["entities"]}


@lru_cache(maxsize=1)
def listings_local() -> dict:
    with open(os.path.join(config.KIT_DATA, "listings.json"), encoding="utf-8") as f:
        out = defaultdict(list)
        for l in json.load(f)["listings"]:
            out[l["entityId"]].append(l)
    return out


@lru_cache(maxsize=1)
def peers() -> dict:
    return {(r["country"], r["city_tier"], r["segment"], r["day_key"]): r for r in _csv("peer_benchmarks.csv")}


@lru_cache(maxsize=1)
def city_tiers() -> dict:
    return {r["city"]: r["city_tier"] for r in _csv("cities.csv")}


@lru_cache(maxsize=1)
def pilot_log() -> list:
    return _csv("pilot_decision_log_2025.csv")


@lru_cache(maxsize=1)
def local_events() -> dict:
    p = os.path.join(config.KIT_DATA, "local_events.json")
    with open(p, encoding="utf-8") as f:
        raw = json.load(f)
    items = raw.get("data") if isinstance(raw, dict) else raw
    out = {}
    for ev in items or []:
        eid = ev.get("id") or ev.get("@id")
        if eid:
            out[str(eid)] = ev
    return out


def peer_row(eid: str, day_key: str):
    e = entities().get(eid)
    if not e:
        return None
    tier = city_tiers().get(e["address"]["city"])
    return peers().get((e["meta"]["countryCode"], tier, e.get("c_segment"), day_key))


def previous_same_day(country: str, day_key: str, d: date) -> date | None:
    """The same special day one season earlier (e.g. Christmas Eve 2025 for Christmas Eve 2026)."""
    cyc = lambda x: x.year if x.month >= 2 else x.year - 1  # noqa: E731
    prev = [x for x in dates_by_key().get((country, day_key), []) if cyc(x) == cyc(d) - 1]
    return min(prev, key=lambda x: abs((x - (d - timedelta(days=364))).days)) if prev else None


# ------------------------------------------------------------------ analytics (pandas, lazily, per entity)
@lru_cache(maxsize=256)
def _analytics_for(eid: str):
    import pandas as pd
    df = pd.read_parquet(os.path.join(config.KIT_DATA, "analytics_daily.parquet"),
                         filters=[("entity_id", "==", eid)])
    df["date"] = df["date"].astype(str)
    return df.set_index("date")


def views_last_30_days(eid: str) -> dict:
    """Sum of Google search + map views and profile views over the last 30 days in the data."""
    try:
        df = _analytics_for(eid)
    except Exception:
        return {"search_map": None, "profile": None, "start": None, "end": None}
    if df.empty:
        return {"search_map": None, "profile": None, "start": None, "end": None}
    end = date.fromisoformat(max(df.index))
    start = end - timedelta(days=29)
    sel = df[df.index >= start.isoformat()]
    return {"search_map": int(sel["GOOGLE_SEARCH_VIEWS"].sum() + sel["GOOGLE_MAP_VIEWS"].sum()),
            "profile": int(sel["PROFILE_VIEWS"].sum()), "start": start.isoformat(), "end": end.isoformat()}


def at_risk_views(eid: str, country: str, day_key: str, d: date) -> dict:
    """Search+map views expected on that day: same special day last year, else same weekday 52 weeks ago,
    else the entity's recent daily mean (last 28 days)."""
    try:
        df = _analytics_for(eid)
    except Exception:
        return {"views": 0, "basis": "no analytics"}
    if df.empty:
        return {"views": 0, "basis": "no analytics"}
    col = lambda r: int(r["GOOGLE_SEARCH_VIEWS"] + r["GOOGLE_MAP_VIEWS"])  # noqa: E731
    prev = previous_same_day(country, day_key, d)
    if prev is not None and prev.isoformat() in df.index:
        return {"views": col(df.loc[prev.isoformat()]), "basis": f"same day last year ({prev.isoformat()})"}
    p364 = (d - timedelta(days=364)).isoformat()
    if p364 in df.index:
        return {"views": col(df.loc[p364]), "basis": f"same weekday last year ({p364})"}
    tail = df.sort_index().tail(28)
    mean = (tail["GOOGLE_SEARCH_VIEWS"] + tail["GOOGLE_MAP_VIEWS"]).mean()
    return {"views": int(round(float(mean))), "basis": "recent daily mean (28 days)"}

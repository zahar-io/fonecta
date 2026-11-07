"""Per-business rules the owner can read and change in the chat ("settings", "call after 15 minutes", ...)."""
from __future__ import annotations

import re

DEFAULTS = {"call_after_min": 30, "backup_after_min": 15, "window": "09-22", "summary": True,
            "summary_every": "weekly", "monitor_off": []}
NAMES = {"call_after_min": "Call after", "backup_after_min": "Then ask the backup after", "window": "Hours to send messages",
         "summary": "Reviews summary"}


def get(state: dict, eid: str) -> dict:
    s = dict(DEFAULTS)
    s.update((state.get("settings") or {}).get(eid) or {})
    return s


def render(s: dict, monitored: list, backup: str | None) -> str:
    on = [m for m in monitored if m not in s["monitor_off"]]
    off = [m for m in monitored if m in s["monitor_off"]]
    a, b = s["window"].split("-")
    lines = ["*Your Connect settings*", "",
             f"1. *Call* after *{s['call_after_min']} min* without an answer",
             f"2. *Backup approver*: {backup or 'none'}" + (f", asked *{s['backup_after_min']} min* after the call" if backup else ""),
             f"3. *Hours to send messages*: *{int(a)}–{int(b)}*",
             f"4. *Reviews summary*: *{'ON' if s['summary'] else 'OFF'}*" + (f", {s['summary_every']}" if s["summary"] else ""),
             f"5. *Monitoring* ({len(on)}): " + ", ".join(on) + (f"\n   _paused: {', '.join(off)}_" if off else ""),
             "", "_Change anything by writing it, e.g. \"call after 15 minutes\", \"send messages 8-20\", "
                 "\"summary daily\", \"stop monitoring Bing\"._"]
    return "\n".join(lines)


def parse_change(text: str, monitored: list) -> dict | None:
    """-> {key: value} for a settings change, or None."""
    t = (text or "").lower()
    ch = {}
    m = re.search(r"backup[^0-9]*(\d+)\s*(min|minute|h|hour)", t)
    if m:
        ch["backup_after_min"] = int(m.group(1)) * (60 if m.group(2).startswith("h") else 1)
    m = re.search(r"\bcall[^0-9]*(\d+)\s*(min|minute|h|hour)", t)
    if m and "backup" not in t:
        ch["call_after_min"] = int(m.group(1)) * (60 if m.group(2).startswith("h") else 1)
    m = re.search(r"(?:send|message|hours|window|between)[^0-9]*(\d{1,2})(?::00)?\s*(?:-|–|to|and)\s*(\d{1,2})", t)
    if m and 0 <= int(m.group(1)) < int(m.group(2)) <= 24:
        ch["window"] = f"{int(m.group(1)):02d}-{int(m.group(2)):02d}"
    if "summary" in t or "review" in t:
        if re.search(r"\b(off|stop|disable|no)\b", t):
            ch["summary"] = False
        elif re.search(r"\b(on|start|enable)\b", t):
            ch["summary"] = True
        for every in ("daily", "weekly", "monthly"):
            if every in t:
                ch["summary_every"], ch["summary"] = every, True
    for svc in monitored:
        if svc.lower().split(" (")[0] in t:
            if re.search(r"\b(stop|pause|remove|don't|dont|no)\b", t):
                ch.setdefault("monitor_pause", []).append(svc)
            elif re.search(r"\b(start|resume|add|watch)\b", t):
                ch.setdefault("monitor_resume", []).append(svc)
    return ch or None


def describe(ch: dict) -> str:
    out = []
    for k, v in ch.items():
        if k == "call_after_min":
            out.append(f"call after *{v} min*")
        elif k == "backup_after_min":
            out.append(f"ask the backup *{v} min* after the call")
        elif k == "window":
            a, b = v.split("-")
            out.append(f"send messages *{int(a)}–{int(b)}*")
        elif k == "summary":
            out.append(f"reviews summary *{'ON' if v else 'OFF'}*")
        elif k == "summary_every":
            out.append(f"summary *{v}*")
        elif k == "monitor_pause":
            out.append("pause monitoring *" + ", ".join(v) + "*")
        elif k == "monitor_resume":
            out.append("resume monitoring *" + ", ".join(v) + "*")
    return "; ".join(out)


def apply(state: dict, eid: str, ch: dict):
    cur = state.setdefault("settings", {}).setdefault(eid, {})
    off = set(get(state, eid)["monitor_off"])
    for k, v in ch.items():
        if k == "monitor_pause":
            off |= set(v)
        elif k == "monitor_resume":
            off -= set(v)
        else:
            cur[k] = v
    cur["monitor_off"] = sorted(off)

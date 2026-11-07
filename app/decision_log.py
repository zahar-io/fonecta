"""Decision log: every suggestion, answer and change in one table (SQLite app/var/decisions.db).
This is the one connection a Connect UI would need: read /api/decisions, or the table itself."""
from __future__ import annotations

import html
import json

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse

from . import kitdata
from .learning import db_rows, local_dt

router = APIRouter()
E_ = html.escape
WHAT = {"sent": "Suggestion sent", "decision": "Owner decided", "owner request": "Owner asked (own words)",
        "auto-applied": "Applied (standing permission)", "review reply": "Review reply", "escalated": "Sent to backup",
        "urgent call": "Phone call", "decline reason": "Decline reason", "undo": "Undone by owner", "shift alert": "Staff shift alert", "busy day": "Busy day nearby", "watch added": "Owner asked to watch a page", "watched event": "Event spotted on a watched page"}


def _when(at):
    t = local_dt(at or "")
    return t.strftime("%a %d %b %H:%M") if t else (at or "")


def _detail(r):
    d = json.loads(r.get("data") or "{}")
    if r["type"] == "sent":
        return "; ".join(f"{s['date']}: {s['hours']}" for s in d.get("suggestions") or [])
    if r["type"] == "decision":
        out = f"{d.get('date')}: suggested {d.get('suggestion')} → {d.get('decision')}"
        if d.get("final_hours") and d.get("final_hours") != d.get("suggestion"):
            out += f", final {d['final_hours']}"
        return out
    if r["type"] == "owner request":
        return f"{d.get('date')}: {d.get('final_hours')}"
    if r["type"] == "review reply":
        return f"{d.get('decision')}: “{(d.get('final') or '')[:90]}”"
    if r["type"] == "decline reason":
        return d.get("decline_reason") or ""
    if r["type"] == "auto-applied":
        return f"{d.get('date')}: {d.get('hours') or d.get('final_hours') or ''}"
    return ""


@router.get("/api/decisions")
def api_decisions(eid: str | None = None, limit: int = 200):
    rows = db_rows(eid, min(limit, 1000))
    for r in rows:
        r["data"] = json.loads(r.get("data") or "{}")
    return JSONResponse(rows)


@router.get("/log", response_class=HTMLResponse)
def log_page(eid: str = "FI-D0001"):
    ent = kitdata.entities().get(eid, {})
    rows = db_rows(eid)
    trs = "".join(
        f"<tr><td>{E_(_when(r['at']))}</td><td><b>{E_(WHAT.get(r['type'], r['type']))}</b></td>"
        f"<td>{E_(_detail(r))}</td><td>{E_(r.get('channel') or '')}</td></tr>" for r in rows) or \
        "<tr><td colspan=4 style='color:#888'>No decisions yet.</td></tr>"
    return f"""<!doctype html><html><head><meta charset=utf-8><title>Decision log</title><style>
body{{margin:0;font-family:-apple-system,Helvetica,Arial,sans-serif;background:#f3f0fa;color:#1d1b26}}
.top{{background:#5b3fa0;color:#fff;padding:16px 30px;font-size:22px}}.top span{{opacity:.75;font-size:16px;margin-left:12px}}
.wrap{{padding:26px 30px}}h1{{margin:0 0 4px;font-size:34px}}.sub{{color:#666;font-size:18px;margin-bottom:18px}}
table{{width:100%;border-collapse:collapse;background:#fff;border-radius:14px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.08)}}
td,th{{text-align:left;padding:12px 16px;border-bottom:1px solid #eee;font-size:18px;vertical-align:top}}
th{{background:#ece8f6;color:#5b3fa0;font-size:15px;text-transform:uppercase;letter-spacing:1px}}
</style><meta http-equiv=refresh content=5></head><body>
<div class=top>Connect Suggests · Decision log<span>demo UI on synthetic data · every answer from WhatsApp, calls and links</span></div>
<div class=wrap><h1>{E_(ent.get('name', eid))}</h1>
<div class=sub>Who decided what, when, on which channel. Stored in one table (decisions.db), readable at /api/decisions.</div>
<table><tr><th>When (Helsinki)</th><th>What</th><th>Details</th><th>Channel</th></tr>{trs}</table></div></body></html>"""

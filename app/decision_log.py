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


ICON = {"sent": ("💬", "#5b3fa0"), "decision": ("✅", "#188038"), "owner request": ("✍️", "#188038"),
        "auto-applied": ("⚡", "#188038"), "review reply": ("⭐", "#b06000"), "escalated": ("👥", "#5b3fa0"),
        "urgent call": ("📞", "#5b3fa0"), "call": ("📞", "#5b3fa0"), "decline reason": ("🙅", "#b3261e"),
        "undo": ("↩️", "#5b3fa0"), "shift alert": ("🧑‍🍳", "#b06000"), "watch added": ("👀", "#5b3fa0"),
        "watched event": ("🎟️", "#5b3fa0")}


def _d(x):
    try:
        from datetime import date
        return date.fromisoformat(str(x)).strftime("%a %d %b")
    except Exception:
        return str(x or "")


def _h(x):
    x = str(x or "")
    return "closed" if x == "closed" else x.replace("-", "–").replace(":00", "")


CH = {"wa-call": "Call", "whatsapp": "WhatsApp", "whatsapp chat": "WhatsApp", "console": "Console", "whatsapp (shift alert)": "WhatsApp"}


def _plain(r):
    """One friendly line per decision for the phone view."""
    d = json.loads(r.get("data") or "{}")
    t = r["type"]
    if t == "decision":
        dec = d.get("decision")
        if dec == "decline":
            return "Said no thanks", f"{_d(d.get('date'))} · remembered for next year"
        if d.get("final_hours") and d.get("final_hours") != d.get("suggestion"):
            return "Edited the suggestion", f"{_d(d.get('date'))} → {_h(d.get('final_hours'))}"
        return "Approved", f"{_d(d.get('date'))} → {_h(d.get('final_hours') or d.get('suggestion'))} · live on Google"
    if t == "owner request":
        return "Asked in his own words", f"{_d(d.get('date'))} → {_h(d.get('final_hours'))}"
    if t == "auto-applied":
        return "Handled for him", f"{_d(d.get('date'))} → {_h(d.get('hours') or d.get('final_hours'))} · with Undo"
    if t in ("urgent call", "call"):
        return "Connect called him", "No reply to the message, so it rang"
    if t == "shift alert":
        return "Shift alert", f"Nobody on the opening shift · {_d(d.get('date'))}"
    if t == "watched event":
        return "Event nearby", ((d.get("event") or {}).get("title") or "")[:60]
    if t == "sent":
        n = len(d.get("suggestions") or [])
        return "Suggestion sent", f"{n} date{'s' if n != 1 else ''} · with the reason"
    if t == "review reply":
        return "Replied to a review", (d.get("final") or "")[:60] + ("…" if len(d.get("final") or "") > 60 else "")
    return WHAT.get(t, t), _detail(r)[:70]


@router.get("/log/phone", response_class=HTMLResponse)
def log_phone(eid: str = "FI-D0001"):
    """Phone view of the same log: what the owner (or Connect's app) would show."""
    ent = kitdata.entities().get(eid, {})
    cards = []
    for r in db_rows(eid, 30):
        ic, col = ICON.get(r["type"], ("•", "#5b3fa0"))
        a, b = _plain(r)
        cards.append(f"<div class=c><div class=i style='background:{col}1a;color:{col}'>{ic}</div><div class=t>"
                     f"<div class=a>{E_(a)}</div><div class=b>{E_(b)}</div></div>"
                     f"<div class=w>{E_(_when(r['at']).split(' ', 1)[-1])}<br><span>{E_(CH.get(r.get('channel') or '', 'SMS preview' if 'preview' in (r.get('channel') or '') else (r.get('channel') or '').title()))}</span></div></div>")
    body = "".join(cards) or "<div class=e>No decisions yet.</div>"
    return f"""<!doctype html><html><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>Decisions</title><style>
body{{margin:0;font-family:-apple-system,Helvetica,Arial,sans-serif;background:#f3f0fa;color:#1d1b26}}
.h{{background:#5b3fa0;color:#fff;padding:54px 20px 18px}}.h .k{{font-size:13px;opacity:.8;letter-spacing:1px;text-transform:uppercase}}
.h .n{{font-size:26px;font-weight:800;margin-top:4px}}.h .s{{font-size:14px;opacity:.85;margin-top:4px}}
.l{{padding:14px 12px}}.c{{display:flex;gap:12px;align-items:center;background:#fff;border-radius:18px;padding:14px;margin-bottom:10px;box-shadow:0 1px 3px rgba(40,20,90,.08)}}
.i{{width:44px;height:44px;border-radius:14px;display:flex;align-items:center;justify-content:center;font-size:22px;flex:none}}
.t{{flex:1;min-width:0}}.a{{font-size:17px;font-weight:700}}.b{{font-size:14px;color:#555;margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.w{{font-size:12px;color:#888;text-align:right;flex:none}}.w span{{color:#5b3fa0;font-weight:600}}.e{{color:#888;padding:30px;text-align:center}}
</style><meta http-equiv=refresh content=5></head><body>
<div class=h><div class=k>Fonecta Connect · decisions</div><div class=n>{E_(ent.get('name', eid))}</div>
<div class=s>Every answer from WhatsApp, calls and links, in one place</div></div><div class=l>{body}</div></body></html>"""


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

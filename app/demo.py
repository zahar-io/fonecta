"""Presenter view for the live demo: one business, the five steps, big type. Uses the same engine as the console.
/demo?eid=FI-D0001   (left: what Connect knows and does · right: the owner's real phone page, live)"""
from __future__ import annotations

import html
import json

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from . import kitdata
from .hours import nice

router = APIRouter()
E = html.escape


def _eng():
    from .main import eng
    return eng()


def _case(eid):
    cs = _eng().cases_for(eid)
    return cs[-1] if cs else None


CSS = """
*{box-sizing:border-box}body{margin:0;font-family:-apple-system,Helvetica,Arial,sans-serif;background:#f3f0fa;color:#1d1b26}
.top{background:#5b3fa0;color:#fff;padding:16px 30px;display:flex;align-items:center;gap:24px;font-size:22px}
.steps{display:flex;gap:10px;margin-left:auto}.st{padding:8px 16px;border-radius:20px;background:rgba(255,255,255,.18);font-size:18px}
.st.on{background:#fff;color:#5b3fa0;font-weight:700}
.wrap{display:flex;gap:30px;padding:26px 30px}.left{flex:1}.right{width:430px;flex:none}
.card{background:#fff;border-radius:16px;padding:22px 26px;margin-bottom:18px;box-shadow:0 1px 3px rgba(0,0,0,.08)}
h1{margin:0 0 6px;font-size:40px}.sub{color:#666;font-size:20px}
.row{display:flex;align-items:center;gap:18px;padding:12px 0;border-bottom:1px solid #eee;font-size:24px}
.d{width:190px;font-weight:700}.g{width:150px;color:#b3261e;text-decoration:line-through}.s{width:170px;color:#188038;font-weight:700}
.why{flex:1;font-size:18px;color:#444}.btn{border:0;border-radius:12px;padding:16px 26px;font-size:22px;cursor:pointer;background:#5b3fa0;color:#fff}
.btn.g2{background:#ece8f6;color:#5b3fa0}iframe{width:410px;height:820px;border:12px solid #1d1b26;border-radius:36px;background:#fff}
pre{white-space:pre-wrap;font-family:inherit;font-size:20px;margin:0}.k{color:#5b3fa0;font-weight:700;font-size:18px;letter-spacing:1px;text-transform:uppercase}
code{font-size:18px}
"""


def _row(it):
    why = (it.get("reasons") or [""])[0]
    sug = "closed" if it["hours"] == "closed" else nice(it["hours"])
    flag = " (ask)" if it.get("mode") == "ask" else ""
    return (f"<div class=row><div class=d>{E(it['date'])}<div class=sub>{E(it['day_key'].replace('_', ' ').title())}</div></div>"
            f"<div class=g>{E(nice(it.get('shown_hours') or ''))}</div><div class=s>{E(sug)}{flag}</div>"
            f"<div class=why>{E(why)} <span class=sub>· {int(it.get('confidence', 0) * 100)}% sure · "
            f"{int((it.get('at_risk') or {}).get('views', 0))} views at risk</span></div></div>")


@router.get("/demo", response_class=HTMLResponse)
def demo(eid: str = "FI-D0001"):
    e = _eng()
    c = _case(eid)
    if c is None:
        e.run_detection([eid])
        c = _case(eid)
    ent = kitdata.entities().get(eid, {})
    sugg = [i for i in c["items"] if i["action"] == "SUGGEST"]
    sent = c["status"] not in ("pending",)
    decided = any(i["status"] in ("approved", "edited", "declined", "auto-applied") for i in c["items"])
    step = 5 if decided else (4 if sent else 2)
    steps = "".join(f"<div class='st{' on' if n == step or (n < step) else ''}'>{n} · {t}</div>"
                    for n, t in ((1, "Detect"), (2, "Suggest"), (3, "Contact"), (4, "Decide"), (5, "Apply")))
    left = (f"<div class=card><div class=k>1 · Detect · 2 · Suggest</div><h1>{E(c['name'])}</h1>"
            f"<div class=sub>{E(str(ent.get('c_segment', '')).replace('_', ' '))} · {E(c['city'])} · owner {E(c['first'])} · "
            f"prefers {E(c['channel_pref'])} in {E(c['lang'])} · {int(c.get('views30') or 0):,} search views in 30 days</div>"
            f"<div style='margin-top:14px'><div class=row style='font-size:16px;color:#888'><div class=d>Date</div>"
            f"<div class=g style='text-decoration:none;color:#888'>Google shows</div><div class=s style='color:#888'>Connect suggests</div>"
            f"<div class=why>Why</div></div>{''.join(_row(i) for i in sugg)}</div></div>")
    if not sent:
        left += (f"<form method=post action='/demo/send?eid={E(eid)}'><button class=btn>3 · Send to {E(c['first'] or 'owner')} "
                 f"({E(c['channel_pref'].title())}, {E(c['lang'])})</button></form>"
                 + (f"<form method=post action='/demo/send?eid={E(eid)}&via=whatsapp' style='margin-top:12px'>"
                    f"<button class=btn style='background:#128c7e'>3 · Send via WhatsApp (real phone)</button></form>"
                    if __import__("app.channels", fromlist=["wa_configured"]).wa_configured() else ""))
        right = "<div class=card><div class=k>Owner's phone</div><p class=sub>Nothing sent yet.</p></div>"
    else:
        right = f"<div class=k style='margin-bottom:8px'>4 · Owner's phone (live, no login)</div><iframe id=ph src='/s/{E(c['token'])}'></iframe>"
    if decided:
        try:
            hh = (e.yext.get_entity(eid, "hours").get("hours") or {}).get("holidayHours") or []
        except Exception as ex:  # show the error rather than pretend
            hh = [{"error": str(ex)[:120]}]
        learned = "".join(f"<li>{E(x)}</li>" for x in e.learning.summary(eid)[-4:])
        left += (f"<div class=card><div class=k>5 · Apply · live from the Yext API</div>"
                 f"<pre><code>GET entities/{E(eid)} → hours.holidayHours\n{E(json.dumps(hh, ensure_ascii=False, indent=1))}</code></pre></div>"
                 f"<div class=card><div class=k>Learning</div><ul style='font-size:20px'>{learned}</ul></div>")
    left += (f"<form method=post action='/demo/reset?eid={E(eid)}' style='margin-top:10px'>"
             f"<button class='btn g2'>Reset this business</button></form>")
    poll = ("<script>let s=%d;setInterval(async()=>{const r=await fetch('/demo/state?eid=%s');const j=await r.json();"
            "if(j.step!==s){location.reload()}},2000)</script>") % (step, E(eid))
    return HTMLResponse(f"<!doctype html><html><head><meta charset=utf-8><title>Connect Suggests · demo</title><style>{CSS}</style></head>"
                        f"<body><div class=top><b>Connect Suggests</b><span>Fonecta Connect × Flovr · live demo</span>"
                        f"<div class=steps>{steps}</div></div><div class=wrap><div class=left>{left}</div>"
                        f"<div class=right>{right}</div></div>{poll}</body></html>")


@router.get("/demo/state")
def demo_state(eid: str = "FI-D0001"):
    c = _case(eid)
    if not c:
        return JSONResponse({"step": 2})
    decided = any(i["status"] in ("approved", "edited", "declined", "auto-applied") for i in c["items"])
    return JSONResponse({"step": 5 if decided else (4 if c["status"] != "pending" else 2)})


@router.post("/demo/send")
def demo_send(eid: str = "FI-D0001", via: str | None = None):
    c = _case(eid)
    _eng().send(c["id"], via)
    return RedirectResponse(f"/demo?eid={eid}", 303)


@router.post("/demo/reset")
def demo_reset(eid: str = "FI-D0001"):
    e = _eng()
    c = _case(eid)
    if c:  # undo this business's writes in Yext, forget its case and what was learned from it
        prev = {}
        for a in c.get("applied", []):
            for d in a["changes"]:
                prev.setdefault(d, a["previous"].get(d))
        if prev:
            try:
                e._write(eid, prev, {"kind": "owner_undo", "case": c["id"]})
            except Exception:
                pass
        for x in e.cases_for(eid):
            del e.state["cases"][x["id"]]
        e.learning.data["prefs"].pop(eid, None)
        e.learning.save()
        e.save()
    e.run_detection([eid])
    return RedirectResponse(f"/demo?eid={eid}", 303)

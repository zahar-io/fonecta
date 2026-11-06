"""Web layer: Fonecta ops console (/), the owner's no-login decision page (/s/<link>) and the WhatsApp webhook.

Run:  .venv/bin/python -m uvicorn app.main:app --port 8800
"""
from __future__ import annotations

import html
import json
import os

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse

from . import channels, config, links, messages
from .engine import Engine, NotAllowed
from .hours import is_valid, nice

app = FastAPI(title="Connect Suggests – Flovr")
ENGINE: Engine | None = None


def eng() -> Engine:
    global ENGINE
    if ENGINE is None:
        ENGINE = Engine()
    return ENGINE


E = html.escape
PURPLE = "#5b3fa0"
CSS = f"""
*{{box-sizing:border-box}} body{{font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;margin:0;color:#1d1b26;background:#f6f4fb}}
header{{background:{PURPLE};color:#fff;padding:14px 22px;display:flex;justify-content:space-between;align-items:center}}
header b{{font-size:18px}} main{{padding:18px 22px;max-width:1300px;margin:auto}}
.card{{background:#fff;border-radius:12px;padding:14px 16px;margin:0 0 14px;box-shadow:0 1px 3px rgba(0,0,0,.08)}}
.btn{{display:inline-block;border:0;border-radius:8px;padding:8px 14px;font-size:14px;cursor:pointer;text-decoration:none;margin:2px}}
.p{{background:{PURPLE};color:#fff}} .s{{background:#ece8f6;color:{PURPLE}}} .g{{background:#fff;border:1px solid #ccc;color:#333}}
table{{border-collapse:collapse;width:100%;font-size:13px}} td,th{{padding:6px 8px;border-bottom:1px solid #eee;text-align:left;vertical-align:top}}
.tag{{display:inline-block;padding:2px 8px;border-radius:10px;font-size:12px;background:#eee}}
.t-pending{{background:#fff3cd}} .t-sent{{background:#dbeafe}} .t-approved,.t-edited,.t-auto-applied{{background:#d1fae5}}
.t-declined,.t-undone{{background:#fde2e2}} .t-flagged{{background:#fbd5f5}} .t-quiet{{background:#eee}} .t-opted{{background:#e5e7eb}}
.muted{{color:#777;font-size:12px}} .reasons li{{margin:2px 0}} pre{{white-space:pre-wrap;font-family:inherit;margin:0}}
.phone{{width:330px;background:#e5ddd5;border-radius:22px;padding:12px;border:8px solid #222}}
.bubble{{background:#fff;border-radius:8px;padding:8px 10px;font-size:13px;margin:6px 0;box-shadow:0 1px 1px rgba(0,0,0,.1)}}
.wabtn{{background:#fff;border-radius:8px;text-align:center;color:#128c7e;padding:7px;margin:3px 0;font-size:14px}}
.mock{{font-size:11px;color:#555;text-align:center}}
"""


def page(title: str, body: str, owner: bool = False) -> HTMLResponse:
    head = (f"<header><b>{'Fonecta Connect' if owner else 'Connect Suggests · ops console'}</b>"
            f"<span class=muted style='color:#e8e2f7'>{'' if owner else 'Flovr · demo on synthetic data'}</span></header>")
    meta = "<meta name=viewport content='width=device-width,initial-scale=1'>"
    return HTMLResponse(f"<!doctype html><html><head><meta charset=utf-8>{meta}<title>{E(title)}</title>"
                        f"<style>{CSS}</style></head><body>{head}<main>{body}</main></body></html>")


# ------------------------------------------------------------------ console
def item_row(it: dict, lang="en") -> str:
    rs = "".join(f"<li>{E(r)}</li>" for r in it.get("reasons") or [])
    risk = it.get("at_risk") or {}
    sug = "FLAG: needs a human" if it["action"] == "FLAG" else E(nice(it.get("final_hours") or it["hours"]))
    return (f"<tr><td>{E(it['date'])}<br><span class=muted>{E(it['day_key'])}</span></td>"
            f"<td>{E(nice(it.get('shown_hours') or ''))}</td><td><b>{sug}</b>"
            f"{'<br><span class=muted>ask, not suggest</span>' if it.get('mode') == 'ask' else ''}</td>"
            f"<td>{it.get('confidence', 0):.2f}</td><td>{E(str(it.get('basis') or ''))}</td>"
            f"<td><ul class=reasons>{rs}</ul></td><td>{int(risk.get('views', 0)):,}</td>"
            f"<td><span class='tag t-{E(it['status'].split()[0])}'>{E(it['status'])}</span></td></tr>")


def phone_mock(c: dict) -> str:
    out = [o for o in c.get("outbox", [])]
    if not out:
        return ""
    bubbles = []
    for o in out[-3:]:
        txt = o["text"].split("\n")
        btns = ""
        if o["kind"] == "suggestion" and c.get("message"):
            btns = "".join(f"<div class=wabtn>{E(b)}</div>" for b in c["message"]["buttons"])
        bubbles.append(f"<div class=bubble><pre>{E(chr(10).join(txt))}</pre></div>{btns}")
    real = any(o["channel"] == "whatsapp" for o in out)
    label = "Sent via WhatsApp Cloud API" if real else f"Mock preview · {E(c['channel_pref'])} (nothing sent)"
    return f"<div class=phone><div class=mock>{label}</div>{''.join(bubbles)}</div>"


@app.get("/", response_class=HTMLResponse)
def console():
    e = eng()
    cases = sorted(e.cases(), key=lambda c: -c.get("priority", 0))
    wa = "WhatsApp: connected" if channels.wa_configured() else "WhatsApp: not configured (previews only)"
    top = (f"<div class=card><form method=post action=/api/detect style='display:inline'><button class='btn p'>"
           f"1 · Run detection for the 17 demo businesses</button></form>"
           f"<form method=post action=/api/reset style='display:inline'><button class='btn g'>Reset demo</button></form>"
           f" <span class=muted>{E(wa)} · Yext: {E(config.yext_base())} · source: "
           f"{E(cases[0]['source']) if cases else '-'}</span></div>")
    rows = []
    for c in cases:
        items = "".join(item_row(i) for i in c["items"]) or "<tr><td colspan=8 class=muted>Nothing to change: stay quiet.</td></tr>"
        acts = ""
        if c["status"] in ("pending", "sent"):
            acts += (f"<form method=post action=/api/send/{E(c['id'])} style='display:inline'><button class='btn p'>3 · Send</button></form>"
                     f"<form method=post action=/api/send/{E(c['id'])}?via=whatsapp style='display:inline'><button class='btn s'>Send via WhatsApp</button></form>"
                     f"<form method=post action=/api/simulate/{E(c['id'])} style='display:inline'><button class='btn g'>Simulate owner</button></form>")
        if c["status"] == "sent" and e.approvers(c["entity_id"]):
            acts += (f"<form method=post action=/api/escalate/{E(c['id'])} style='display:inline'>"
                     f"<button class='btn g'>No answer? Escalate (demo: skip the {os.environ.get('ESCALATE_HOURS', '24')} h wait)</button></form>")
        if c.get("token"):
            acts += f"<a class='btn s' target=_blank href='/s/{E(c['token'])}'>4 · Owner's page</a>"
        learned = "".join(f"<li>{E(x)}</li>" for x in e.learning.summary(c["entity_id"]))
        rows.append(
            f"<div class=card><div style='display:flex;gap:18px;flex-wrap:wrap'><div style='flex:1;min-width:600px'>"
            f"<h3 style='margin:0'>{E(c['name'])} <span class=muted>{E(c['entity_id'])} · {E(c['city'])} · "
            f"{E(str(c.get('segment')))}</span> <span class='tag t-{E(c['status'].split()[0])}'>{E(c['status'])}</span></h3>"
            f"<div class=muted>Owner {E(c['first'] or '-')} · prefers {E(c['channel_pref'])} in {E(c['lang'])} · "
            f"window {E(c['window'])} · {int(c.get('views30') or 0):,} search+map views in the last 30 days · "
            f"priority {int(c.get('priority', 0)):,} views at risk</div>"
            f"<table><tr><th>Date</th><th>Google shows</th><th>Suggest</th><th>Conf.</th><th>Basis</th><th>Why</th>"
            f"<th>Views at risk</th><th>Status</th></tr>{items}</table><div style='margin-top:8px'>{acts}</div>"
            f"<details><summary class=muted>What Connect has learned about this owner</summary><ul>{learned}</ul></details>"
            f"<details><summary class=muted>Audit trail</summary><pre class=muted>"
            f"{E(json.dumps(e.learning.audit(c['entity_id'])[-8:], ensure_ascii=False, indent=1))}</pre></details>"
            f"</div>{phone_mock(c)}</div></div>")
    return page("Connect Suggests", top + "".join(rows))


@app.post("/api/detect")
def api_detect():
    eng().run_detection()
    return RedirectResponse("/", 303)


@app.post("/api/reset")
def api_reset():
    eng().reset()
    return RedirectResponse("/", 303)


@app.post("/api/send/{cid}")
def api_send(cid: str, via: str | None = None):
    try:
        eng().send(cid, via)
    except NotAllowed as ex:
        raise HTTPException(409, str(ex))
    return RedirectResponse("/", 303)


@app.post("/api/escalate/{cid}")
def api_escalate(cid: str):
    try:
        eng().escalate(cid, force=True)
    except NotAllowed as ex:
        raise HTTPException(409, str(ex))
    return RedirectResponse("/", 303)


@app.post("/api/simulate/{cid}")
def api_simulate(cid: str):
    eng().simulate(cid)
    return RedirectResponse("/", 303)


@app.get("/api/cases")
def api_cases():
    return JSONResponse(eng().cases())


# ------------------------------------------------------------------ owner page (no login)
def load_link(link: str) -> tuple:
    try:
        body = links.verify(link)
    except Exception:
        raise HTTPException(403, "This link has expired or isn't valid.")
    try:
        return body, eng().case(body["c"])
    except KeyError:
        raise HTTPException(404, "This suggestion no longer exists.")


T = {
    "fi": ("Hyväksy", "Muokkaa", "Ei kiitos", "Hoida pyhäpäivien aukioloajat puolestani jatkossa (ilmoitamme aina)",
           "Tallenna", "kiinni"),
    "sv": ("Godkänn", "Ändra", "Nej tack", "Sköt helgdagarnas öppettider åt mig framöver (vi meddelar alltid)",
           "Spara", "stängt"),
    "nb": ("Godkjenn", "Endre", "Nei takk", "Ta deg av åpningstidene på helligdager for meg fremover (vi gir alltid beskjed)",
           "Lagre", "stengt"),
    "en": ("Approve", "Edit", "No thanks", "Handle public holidays for me from now on (we'll always tell you)",
           "Save", "closed"),
}
CHIPS = {
    "fi": {"open_as_usual": "Olemme auki normaalisti", "different_hours": "Eri aukioloajat", "not_this_year": "Ei tänä vuonna"},
    "sv": {"open_as_usual": "Vi har öppet som vanligt", "different_hours": "Andra öppettider", "not_this_year": "Inte i år"},
    "nb": {"open_as_usual": "Vi har åpent som vanlig", "different_hours": "Andre åpningstider", "not_this_year": "Ikke i år"},
    "en": {"open_as_usual": "We're open as usual", "different_hours": "Different hours", "not_this_year": "Not this year"},
}
WHY = {"fi": "Miksi ei? (vapaaehtoinen, auttaa meitä ehdottamaan paremmin)",
       "sv": "Varför inte? (frivilligt, hjälper oss att föreslå bättre)",
       "nb": "Hvorfor ikke? (valgfritt, hjelper oss å foreslå bedre)",
       "en": "Why not? (optional, helps us suggest better)"}
THANKS = {"fi": "Kiitos, merkitty. Muistamme tämän ensi kerralla.", "sv": "Tack, noterat. Vi minns det till nästa gång.",
          "nb": "Takk, notert. Vi husker det til neste gang.", "en": "Thanks, noted. We'll remember this next time."}


def times(h: str) -> tuple:
    if not h or h == "closed":
        return "", ""
    return h.split(",")[0][:5], h.split(",")[-1][-5:]


@app.get("/s/{link}", response_class=HTMLResponse)
def owner_page(link: str):
    body, c = load_link(link)
    lang = c["lang"]
    ap, ed, no, perm, save, closed = T.get(lang, T["en"])
    if body.get("u"):
        return page("Undo", f"<div class=card><pre>{E((c.get('outbox') or [{}])[-1].get('text', ''))}</pre>"
                            f"<form method=post action='/s/{E(link)}/undo'><button class='btn g'>Undo this change</button></form></div>", True)
    open_items = [i for i in c["items"] if i["status"] in ("pending", "sent") and i["action"] == "SUGGEST"]
    if not open_items:
        last = (c.get("outbox") or [{}])[-1].get("text", "")
        return page("Done", f"<div class=card><h3>{E(c['name'])}</h3><pre>{E(last)}</pre></div>", True)
    msg = c.get("message") or eng().compose(c)
    rows = ""
    for it in sorted(open_items, key=lambda i: i["date"]):
        o, cl = times(it["hours"])
        d = it["date"]
        rows += (f"<div class=card><b>{E(messages.bullet(it, lang))}</b>"
                 f"<div style='margin-top:6px'>"
                 f"<label><input type=radio name='a_{d}' value=approve checked> {ap}</label> &nbsp;"
                 f"<label><input type=radio name='a_{d}' value=edit> {ed}</label> &nbsp;"
                 f"<label><input type=radio name='a_{d}' value=decline> {no}</label></div>"
                 f"<div class=muted style='margin-top:6px'>{ed}: <input type=time name='o_{d}' value='{o}'> – "
                 f"<input type=time name='c_{d}' value='{cl}'> <label><input type=checkbox name='x_{d}' "
                 f"{'checked' if it['hours'] == 'closed' else ''}> {closed}</label></div></div>")
    html_ = (f"<div class=card><pre>{E(msg['body'])}</pre></div><form method=post action='/s/{E(link)}'>{rows}"
             f"<div class=card><label><input type=checkbox name=perm> {E(perm)}</label></div>"
             f"<button class='btn p' style='font-size:16px;padding:12px 20px'>{save}</button></form>")
    return page(c["name"], html_, True)


@app.post("/s/{link}", response_class=HTMLResponse)
async def owner_decide(link: str, request: Request):
    _, c = load_link(link)
    form = await request.form()
    decs = {}
    for it in c["items"]:
        d = it["date"]
        a = form.get(f"a_{d}")
        if not a:
            continue
        if a == "edit":
            if form.get(f"x_{d}"):
                h = "closed"
            else:
                h = f"{form.get(f'o_{d}', '')}-{form.get(f'c_{d}', '')}"
            if not is_valid(h):
                raise HTTPException(400, f"Please check the hours for {d}.")
            decs[d] = {"action": "edit", "hours": h}
        else:
            decs[d] = {"action": a}
    out = eng().decide(c["id"], decs, permission=bool(form.get("perm")), channel="page")
    chips = ""
    if out.get("declined"):
        lang = c["lang"] if c["lang"] in CHIPS else "en"
        chips = f"<div class=card><b>{E(WHY[lang])}</b><br>" + "".join(
            f"<form method=post action='/s/{E(link)}/reason' style='display:inline'><input type=hidden name=r value={k}>"
            f"<button class='btn s'>{E(v)}</button></form>" for k, v in CHIPS[lang].items()) + "</div>"
    return page("Thanks", f"<div class=card><pre>{E(out.get('confirmation', ''))}</pre></div>{chips}", True)


@app.post("/s/{link}/reason", response_class=HTMLResponse)
def owner_reason(link: str, r: str = Form(...)):
    _, c = load_link(link)
    if r in CHIPS["en"]:
        eng().decline_reason(c["id"], r)
    return page("Thanks", f"<div class=card>{E(THANKS.get(c['lang'], THANKS['en']))}</div>", True)


@app.post("/s/{link}/undo", response_class=HTMLResponse)
def owner_undo(link: str):
    body, c = load_link(link)
    if not body.get("u"):
        raise HTTPException(403, "Not an undo link.")
    out = eng().undo(c["id"])
    return page("Undone", f"<div class=card><pre>{E(out.get('confirmation', 'Nothing to undo.'))}</pre></div>", True)


# ------------------------------------------------------------------ WhatsApp webhook
@app.get("/webhook/whatsapp")
def wa_verify(request: Request):
    q = request.query_params
    if q.get("hub.mode") == "subscribe" and q.get("hub.verify_token") == os.environ.get("WA_VERIFY_TOKEN", ""):
        return PlainTextResponse(q.get("hub.challenge", ""))
    raise HTTPException(403)


@app.post("/webhook/whatsapp")
async def wa_hook(request: Request):
    payload = await request.json()
    for frm, bid in channels.parse_webhook(payload):
        if not bid or ":" not in bid:
            continue
        kind, link = bid.split(":", 1)
        try:
            body, c = load_link(link)
        except HTTPException:
            continue
        if kind == "a":
            eng().decide_all(c["id"], "approve", channel="whatsapp")
        elif kind == "d":
            eng().decide_all(c["id"], "decline", channel="whatsapp")
        elif kind == "e":
            e = eng()
            e._deliver_text(c, messages.edit_prompt(e.ctx(c), f"{config.public_base()}/s/{link}"), "edit link")
            e.save()
    return {"ok": True}

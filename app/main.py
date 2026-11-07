"""Web layer: Fonecta ops console (/), the owner's no-login decision page (/s/<link>) and the WhatsApp webhook.

Run:  .venv/bin/python -m uvicorn app.main:app --port 8800
"""
from __future__ import annotations

import html
import re
import json
import os

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse

from . import channels, config, links, messages
from .engine import Engine, NotAllowed
from .hours import is_valid, nice

app = FastAPI(title="Connect Suggests – Flovr")
ENGINE: Engine | None = None
from .demo import router as demo_router  # noqa: E402
app.include_router(demo_router)
from .decision_log import router as log_router  # noqa: E402
app.include_router(log_router)
PUBLIC_PREFIXES = ("/s/", "/r/", "/webhook/")


@app.middleware("http")
async def console_gate(request: Request, call_next):
    """When exposed through a tunnel, only owner links and the webhook are public; the console needs ?k=<key> once."""
    key = os.environ.get("APP_CONSOLE_KEY")
    path = request.url.path
    if key and not path.startswith(PUBLIC_PREFIXES):
        if request.query_params.get("k") == key:
            resp = await call_next(request)
            resp.set_cookie("ck", key, httponly=True, samesite="lax")
            return resp
        if request.cookies.get("ck") != key:
            return PlainTextResponse("Not found", status_code=404)
    return await call_next(request)


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


# ------------------------------------------------------------------ "how it will look" card (preview, not a screenshot)
PREVIEW = {"fi": ("Esikatselu: näin ilmoituksenne näkyy hauissa", "Kiinni", "Auki", "Erikoisaukioloajat"),
           "sv": ("Förhandsvisning: så här visas er profil i sökningar", "Stängt", "Öppet", "Avvikande öppettider"),
           "nb": ("Forhåndsvisning: slik vises oppføringen i søk", "Stengt", "Åpent", "Spesielle åpningstider"),
           "en": ("Preview: how your listing will show in search", "Closed", "Open", "Special hours")}


def maps_card(c: dict, applied: list) -> str:
    from datetime import date as _d
    lang = c["lang"] if c["lang"] in PREVIEW else "en"
    title, closed_w, open_w, special = PREVIEW[lang]
    ent = __import__("app.kitdata", fromlist=["entities"]).entities().get(c["entity_id"]) or {}
    addr = ", ".join(x for x in ((ent.get("address") or {}).get("line1"), c.get("city")) if x)
    rows = ""
    for a in sorted(applied, key=lambda a: a["date"])[:5]:
        d = _d.fromisoformat(a["date"])
        h = a.get("final_hours") or a.get("hours")
        st = (f"<b style='color:#d93025'>{closed_w}</b>" if h == "closed"
              else f"<b style='color:#188038'>{open_w}</b> {E(nice(h))}")
        rows += (f"<div style='display:flex;justify-content:space-between;padding:3px 0'>"
                 f"<span>{E(messages.day_name(a, lang, a.get('event_name')))} {E(messages.dm(d, lang))}</span>"
                 f"<span>{st}</span></div>")
    return (f"<div class=card style='max-width:380px;border:1px solid #dadce0;box-shadow:none'>"
            f"<div class=muted style='margin-bottom:6px'>{E(title)}</div>"
            f"<div style='font-size:20px'>{E(c['name'])}</div>"
            f"<div class=muted>{E(str(c.get('segment') or '').replace('_', ' ').title())} · {E(addr)}</div>"
            f"<div style='margin-top:8px;font-size:13px'><div class=muted>{E(special)}</div>{rows}</div></div>")


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


def review_block(e, eid: str) -> str:
    rc = (e.state.get("reviews") or {}).get(eid)
    btn = (f"<form method=post action=/api/reviews/{E(eid)} style='display:inline'>"
           f"<button class='btn g'>Reviews: check new + weekly summary</button></form>")
    if not rc:
        return f"<div id=rev-{E(eid)} style='margin-top:6px'>{btn}</div>"
    msg = rc.get("message", "")
    lk = f" <a class='btn s' target=_blank href='/r/{E(rc['link'])}'>Owner's review page</a>" if rc.get("link") else ""
    return (f"<div id=rev-{E(eid)} class=card style='background:#faf9fd'>{btn}{lk} <span class='tag'>{E(rc.get('status', ''))}</span>"
            f"<pre style='margin-top:6px'>{E(msg)}</pre><div class=muted>{E(rc.get('weekly', ''))}</div>"
            f"{'<div class=muted>' + E(rc.get('result', '')) + '</div>' if rc.get('result') else ''}</div>")


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
        if c["status"] == "sent" and not c.get("called"):
            acts += (f"<form method=post action=/api/call/{E(c['id'])} style='display:inline'>"
                     f"<button class='btn g'>Urgent: call the owner</button></form>")
        if c.get("token"):
            acts += f"<a class='btn s' target=_blank href='/s/{E(c['token'])}'>4 · Owner's page</a>"
        learned = "".join(f"<li>{E(x)}</li>" for x in e.learning.summary(c["entity_id"]))
        rows.append(
            f"<div class=card id='case-{E(c['entity_id'])}'><div style='display:flex;gap:18px;flex-wrap:wrap'><div style='flex:1;min-width:600px'>"
            f"<h3 style='margin:0'>{E(c['name'])} <span class=muted>{E(c['entity_id'])} · {E(c['city'])} · "
            f"{E(str(c.get('segment')))}</span> <span class='tag t-{E(c['status'].split()[0])}'>{E(c['status'])}</span></h3>"
            f"<div class=muted>Owner {E(c['first'] or '-')} · prefers {E(c['channel_pref'])} in {E(c['lang'])} · "
            f"window {E(c['window'])} · {int(c.get('views30') or 0):,} search+map views in the last 30 days · "
            f"priority {int(c.get('priority', 0)):,} views at risk</div>"
            f"<table><tr><th>Date</th><th>Google shows</th><th>Suggest</th><th>Conf.</th><th>Basis</th><th>Why</th>"
            f"<th>Views at risk</th><th>Status</th></tr>{items}</table><div style='margin-top:8px'>{acts}</div>"
            f"<details><summary class=muted>What Connect has learned about this owner</summary><ul>{learned}</ul></details>"
            + review_block(e, c["entity_id"]) +
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


@app.post("/api/call/{cid}")
def api_call(cid: str):
    try:
        eng().urgent_call(cid, force=True)
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
    open_items = [i for i in c["items"] if i["status"] in ("pending", "sent") and i["action"] == "SUGGEST"
                  and (not (body.get("ds") or body.get("d")) or i["date"] in (body.get("ds") or [body.get("d")]))]
    if not open_items:
        last = (c.get("outbox") or [{}])[-1].get("text", "")
        return page("Done", f"<div class=card><h3>{E(c['name'])}</h3><pre>{E(last)}</pre></div>", True)
    msg = messages.compose(eng().ctx(c), open_items, f"{config.public_base()}/s/{link}")
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
    card = ""
    if out.get("applied"):
        it = {i["date"]: i for i in c["items"]}
        card = maps_card(c, [dict(it.get(a["date"], {}), **a) for a in out["applied"]])
    return page("Thanks", f"<div class=card><pre>{E(out.get('confirmation', ''))}</pre></div>{card}{chips}", True)


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


# ------------------------------------------------------------------ reviews: same loop, second use case
def _reviews_for(eid):
    import json as _j
    if not hasattr(_reviews_for, "all"):
        with open(os.path.join(config.KIT_DATA, "reviews.json"), encoding="utf-8") as f:
            _reviews_for.all = _j.load(f)["response"]["reviews"]
    return sorted([r for r in _reviews_for.all if r["locationId"] == eid], key=lambda r: -r["publisherDate"])


@app.post("/api/reviews/{eid}")
def api_reviews(eid: str):
    """Newest unanswered bad review -> draft reply -> owner message; plus the weekly summary of good ones."""
    from datetime import datetime as _dt
    from . import reviews as rv
    e = eng()
    con = e.contact(eid)
    lang = messages.lang_of(con["preferred_language"])
    name = (__import__("app.kitdata", fromlist=["entities"]).entities().get(eid) or {}).get("name", eid)
    snap = _dt.combine(config.SNAPSHOT, _dt.min.time())
    rs = [r for r in _reviews_for(eid) if r["publisherDate"] < snap.timestamp() * 1000]  # only what Connect knew
    bad = next((r for r in rs if rv.is_bad(r) and (r.get("content") or "").strip() and not r.get("comments")), None)
    out = {"entity_id": eid, "name": name, "lang": lang, "created_at": e.learning and __import__("app.learning", fromlist=["now_iso"]).now_iso()}
    if bad:
        d = rv.draft_reply(bad, name, lang)
        link = links.sign({"r": eid, "id": bad["id"]})
        out.update(review=bad, draft=d, link=link, status="sent",
                   message=rv.owner_message(bad, d, lang) + f"\n{config.public_base()}/r/{link}")
    if rs:
        out["weekly"] = rv.weekly_summary(rs, lang, snap)
    e.state.setdefault("reviews", {})[eid] = out
    e.save()
    return RedirectResponse("/#rev-" + eid, 303)


def _review_case(link):
    try:
        body = links.verify(link)
        return body, eng().state["reviews"][body["r"]]
    except Exception:
        raise HTTPException(403, "This link has expired or isn't valid.")


@app.get("/r/{link}", response_class=HTMLResponse)
def review_page(link: str):
    _, rc = _review_case(link)
    r = rc["review"]
    if rc["status"] != "sent":
        return page("Done", f"<div class=card>{E(rc.get('result', rc['status']))}</div>", True)
    return page(rc["name"], f"<div class=card><b>{'★' * int(r.get('rating') or 0)}</b> "
                f"<span class=muted>{E(r.get('authorName', ''))} · {E(r.get('publisherId', ''))}</span>"
                f"<p>{E(r.get('content', ''))}</p></div><form method=post action='/r/{E(link)}'><div class=card>"
                f"<textarea name=reply rows=6 style='width:100%;font:inherit'>{E(rc['draft']['reply'])}</textarea></div>"
                f"<button class='btn p' name=a value=post>Post / Julkaise</button>"
                f"<button class='btn g' name=a value=skip>Skip / Ohita</button></form>", True)


@app.post("/r/{link}", response_class=HTMLResponse)
def review_decide(link: str, a: str = Form(...), reply: str = Form("")):
    body, rc = _review_case(link)
    e = eng()
    if rc["status"] != "sent":
        raise HTTPException(409, "Already handled.")
    if a == "post" and reply.strip():
        try:  # Yext Reviews API: POST /reviews/{id}/comments (the kit mock doesn't implement it)
            e.yext._req("POST", f"reviews/{body['id']}/comments", body={"content": reply.strip(), "visibility": "PUBLIC"})
            rc["result"] = "Reply posted via the Yext Reviews API."
        except Exception as ex:
            rc["result"] = f"Reply approved and stored; the Yext mock has no review-comment endpoint ({str(ex)[:60]})."
        rc["status"], rc["final_reply"] = ("edited" if reply.strip() != rc["draft"]["reply"] else "approved"), reply.strip()
    else:
        rc["status"], rc["result"] = "skipped", "Skipped. Nothing was posted."
    e.learning.record({"entity_id": rc["entity_id"], "type": "review reply", "review_id": body["id"],
                       "decision": rc["status"], "draft": rc["draft"]["reply"], "final": rc.get("final_reply")})
    e.save()
    return page("Done", f"<div class=card>{E(rc['result'])}</div>", True)


# ------------------------------------------------------------------ live review monitor
REV_UI = {"head": "New review needs a reply", "why": "Why now: {why}.", "sugg": "Suggested reply:",
          "btn": ("Post reply", "Edit", "Skip"), "type": "Type the reply you want to post:",
          "confirm": "Post this reply?\n\n{r}", "posted": "Done ✅ Your reply is posted under the review.",
          "stored": "Done ✅ Your reply is saved.",
          "skipped": "OK, skipped. It stays in your weekly summary."}


def _review_incoming(eid: str, r: dict):
    """One new review: score it; urgent -> WhatsApp with a drafted reply; otherwise weekly summary."""
    from . import review_monitor as rm
    from . import reviews as rv
    e = eng()
    live = e.state.setdefault("rev_live", {})
    if str(r["id"]) in live:
        return
    c = next((x for x in reversed(e.cases_for(eid))), None)
    views = int((c or {}).get("views30") or 0)
    score, why = rm.urgency(r, views)
    lang = c["lang"] if c else "en"
    name = (c or {}).get("name") or eid
    d = rv.draft_reply(r, name, lang)
    item = {"entity_id": eid, "review": r, "score": score, "why": why, "draft": d["reply"], "status": "summary",
            "cid": (c or {}).get("id")}
    live[str(r["id"])] = item
    if score >= 3 and c and channels.wa_configured():
        tok = links.sign({"rv": str(r["id"])})
        text = (f"{'★' * int(r.get('rating') or 0)}{'☆' * (5 - int(r.get('rating') or 0))}  _{r.get('authorName', '')}_\n"
                f"“{(r.get('content') or '').strip()[:400]}”\n\n{REV_UI['why'].format(why='; '.join(why))}\n\n"
                f"*{REV_UI['sugg']}*\n{d['reply']}")
        payload = {"messaging_product": "whatsapp", "to": _wa().recipient(c.get("to_phone")), "type": "interactive",
                   "interactive": {"type": "button", "header": {"type": "text", "text": REV_UI["head"]},
                                   "body": {"text": text[:1024]}, "footer": {"text": f"{name} · Connect"},
                                   "action": {"buttons": [{"type": "reply", "reply": {"id": f"{k}:{tok}", "title": t}}
                                                          for k, t in zip(("rp", "rx", "rk"), REV_UI["btn"])]}}}
        res = _wa()._transport(f"{channels.GRAPH}/{_wa().phone_id}/messages", payload)
        item["status"] = "sent"
        _log(c, "review alert", text, {"ok": "error" not in res, "error": res.get("error")})
    e.save()


def _review_button(frm, kind, link):
    e = eng()
    try:
        rid = links.verify(link)["rv"]
    except Exception:
        return
    item = e.state.get("rev_live", {}).get(rid)
    if not item or item["status"] not in ("sent", "editing", "confirm"):
        return
    c = e.case(item["cid"])
    if kind == "rk":
        item["status"] = "skipped"
        _log(c, "review skipped", REV_UI["skipped"], _wa().send_text(frm, REV_UI["skipped"]))
    elif kind == "rx":
        item["status"] = "editing"
        e.state.setdefault("rev_edit", {})[frm] = rid
        _log(c, "review edit", REV_UI["type"], _wa().send_text(frm, REV_UI["type"]))
    elif kind == "rp":
        reply = item.get("final") or item["draft"]
        try:
            e.yext._req("POST", f"reviews/{item['review']['id']}/comments", body={"content": reply, "visibility": "PUBLIC"})
            m = REV_UI["posted"]
        except Exception:
            m = REV_UI["stored"]
        item.update(status="posted", final=reply)
        e.learning.record({"entity_id": item["entity_id"], "type": "review reply", "review_id": rid,
                           "decision": "posted", "draft": item["draft"], "final": reply, "channel": "whatsapp"})
        _log(c, "review posted", m, _wa().send_text(frm, m))
    e.save()


def _review_edit_text(frm, text) -> bool:
    e = eng()
    rid = e.state.get("rev_edit", {}).pop(frm, None)
    if not rid:
        return False
    item = e.state["rev_live"][rid]
    item.update(final=text.strip(), status="confirm")
    c = e.case(item["cid"])
    tok = links.sign({"rv": rid})
    _log(c, "review confirm", text, _wa().send_buttons(frm, REV_UI["confirm"].format(r=text.strip()),
                                                         [(f"rp:{tok}", "Post reply"), (f"rk:{tok}", "Skip")]))
    e.save()
    return True


@app.post("/api/reviews/new/{eid}")
def api_review_new(eid: str, rating: int = 1, text: str = ""):
    """Demo: a new review arrives right now (as the monitor would see it from the Yext Reviews API)."""
    import time as _t
    r = {"id": f"live-{int(_t.time())}", "locationId": eid, "rating": rating, "authorName": "Mikko K.",
         "publisherId": "GOOGLEMYBUSINESS", "publisherDate": _t.time() * 1000,
         "content": text or "Came on Saturday at 17:00. Google said open, but the door was locked. Wasted trip with the kids."}
    _review_incoming(eid, r)
    return RedirectResponse(f"/demo?eid={eid}", 303)


def _review_poll():
    """Background check: new reviews from the Yext Reviews API for businesses we talk to on WhatsApp."""
    e = eng()
    seen = e.state.setdefault("rev_seen", {})
    for c in [x for x in e.cases() if any(o.get("channel") == "whatsapp" for o in x.get("outbox", []))]:
        eid = c["entity_id"]
        try:
            rs = e.yext._req("GET", "reviews", {"locationIds": eid, "limit": 20}).get("response", {}).get("reviews", [])
        except Exception:
            continue
        new = [r for r in rs if r.get("publisherDate", 0) > seen.get(eid, 0)]
        if eid not in seen:  # first look: remember where we are, don't alert on history
            seen[eid] = max([r.get("publisherDate", 0) for r in rs] or [0])
            continue
        for r in sorted(new, key=lambda r: r.get("publisherDate", 0)):
            _review_incoming(eid, r)
            seen[eid] = max(seen[eid], r.get("publisherDate", 0))
    e.save()


def _in_window(win: str) -> bool:
    from datetime import datetime as _dt
    try:
        from zoneinfo import ZoneInfo
        h = _dt.now(ZoneInfo(config.TZ)).hour
    except Exception:
        h = _dt.now().hour
    a, b = (int(x) for x in win.split("-"))
    return a <= h < b


def _auto_calls():
    """Per business (its settings): no answer within call_after_min -> one call; still no answer
    backup_after_min after the call -> the same suggestion goes to the backup approver. Only inside the send window."""
    from datetime import datetime as _dt, timedelta as _td
    from . import settings as S
    if os.environ.get("AUTO_CALLS", "0") != "1":
        return
    e = eng()
    now = _dt.fromisoformat(__import__("app.learning", fromlist=["now_iso"]).now_iso())
    for c in e.cases():
        if c["status"] != "sent":
            continue
        st = S.get(e.state, c["entity_id"])
        if not _in_window(st["window"]):
            continue
        sent = [o["at"] for o in c.get("outbox", []) if o["kind"].startswith("suggestion")]
        if not sent:
            continue
        try:
            if not c.get("called") and _dt.fromisoformat(min(sent)) < now - _td(minutes=st["call_after_min"]):
                e.urgent_call(c["id"], force=True)
            elif c.get("called") and not c.get("escalation") and \
                    _dt.fromisoformat(c["called"]) < now - _td(minutes=st["backup_after_min"]):
                e.escalate(c["id"], force=True)
        except Exception:
            pass


def _shift_evening():
    """Once an evening (19:00-21:00 Helsinki), check tomorrow's opening shift for every business with a schedule."""
    if os.environ.get("SHIFT_CHECK", "1") != "1" or not _in_window("19-21"):
        return
    from . import shifts
    for eid in shifts._data():
        if not eid.startswith("_"):
            try:
                shift_check(eid)
            except Exception:
                pass


def _background():
    _review_poll()
    _auto_calls()
    _shift_evening()


@app.on_event("startup")
def _start_monitor():
    if os.environ.get("REVIEW_MONITOR", "1") == "1":
        from .review_monitor import Monitor
        Monitor(_background, int(os.environ.get("REVIEW_POLL_S", "60"))).start()


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
    try:
        from . import wa_call
        wa_call.on_webhook(payload)
    except Exception:
        pass
    try:  # keep a small log of what Meta sends (message types / statuses only, no tokens)
        with open(os.path.join(config.var_dir(), "wa_events.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False)[:4000] + "\n")
    except OSError:
        pass
    for frm, bid in channels.parse_webhook(payload):
        if not bid or ":" not in bid:
            continue
        kind, link = bid.split(":", 1)
        if kind in ("rp", "rx", "rk"):
            _review_button(frm, kind, link)
            continue
        try:
            body, c = load_link(link)
        except HTTPException:
            continue
        if kind in ("rp", "rx", "rk"):
            _review_button(frm, kind, link)
            continue
        if kind in ("a", "d"):
            act = "approve" if kind == "a" else "decline"
            ds = body.get("ds") or ([body["d"]] if body.get("d") else None)
            if ds:  # a per-decision message: decide only its dates
                eng().decide(c["id"], {d: {"action": act} for d in ds}, channel="whatsapp")
            else:
                eng().decide_all(c["id"], act, channel="whatsapp")
        elif kind == "e":  # start an edit conversation in the chat, one date at a time
            ds = body.get("ds") or ([body["d"]] if body.get("d") else
                                    [i["date"] for i in c["items"] if i["status"] == "sent"])
            _edit_ask(c, ds, frm)
    for frm, bid in channels.parse_webhook(payload):
        if bid in ("es", "er"):
            _edit_button(frm, bid)
        elif bid in ("rs", "rc"):
            _request_button(frm, bid)
        elif bid in ("ss", "sc"):
            _settings_button(frm, bid)
        elif bid in ("shc", "shk"):
            _shift_button(frm, bid)
    for frm, text in channels.parse_texts(payload):
        _edit_text(frm, text)
    for frm, media in channels.parse_audio(payload):
        _voice(frm, media)
    return {"ok": True}


HEARD = {"en": "🎙️ Heard: “{t}”", "fi": "🎙️ Kuulin: ”{t}”", "sv": "🎙️ Jag hörde: ”{t}”", "nb": "🎙️ Jeg hørte: «{t}»"}
UNHEARD = {"en": "Sorry, I couldn't make out that voice message. Could you type it?",
           "fi": "En saanut ääniviestistä selvää. Voisitko kirjoittaa sen?",
           "sv": "Jag kunde inte höra röstmeddelandet. Kan du skriva det?",
           "nb": "Jeg fikk ikke med meg talemeldingen. Kan du skrive den?"}


def _voice(frm, media_id):
    from . import voice
    c = _owner_case(frm)
    lang = c["lang"] if c else "en"
    audio = voice.download(media_id)
    text = voice.transcribe(audio, "auto") if audio else None
    if c:
        m = HEARD[lang].format(t=text) if text else UNHEARD[lang]
        _log(c, "voice heard", m, _wa().send_text(frm, m))
        eng().save()
    if text:
        _edit_text(frm, text)


def _edit_state():
    return eng().state.setdefault("wa_edit", {})


def _edit_item(st):
    c = eng().case(st["cid"])
    d = st["dates"][st["i"]]
    return c, next(i for i in c["items"] if i["date"] == d)


def _wa():
    return channels.WhatsAppCloudChannel()


def _log(c, kind, text, res):
    c["outbox"].append({"at": __import__("app.learning", fromlist=["now_iso"]).now_iso(), "kind": kind,
                        "channel": "whatsapp", "text": text, "result": res})


def _edit_ask(c, ds, frm):
    from . import chat_edit
    ds = [d for d in ds if any(i["date"] == d and i["status"] == "sent" for i in c["items"])]
    if not ds:
        return
    _edit_state()[frm] = {"cid": c["id"], "dates": ds, "i": 0, "hours": None}
    c2, it = _edit_item(_edit_state()[frm])
    q = chat_edit.question(it, c["lang"])
    _log(c2, "edit question", q, _wa().send_text(frm, q))
    eng().save()


def _owner_case(frm):
    """The business this phone talks for: the latest case we messaged on WhatsApp."""
    cs = [c for c in eng().cases() if any(o.get("channel") == "whatsapp" for o in c.get("outbox", []))]
    return max(cs, key=lambda c: c["outbox"][-1]["at"]) if cs else None


def _days_text(c, ds):
    from datetime import date as _d
    lang = c["lang"]
    return ", ".join(f"{messages.WD_SHORT[lang][_d.fromisoformat(d).weekday()]} {messages.dm(_d.fromisoformat(d), lang)}"
                     for d in ds)


def _monitored(c):
    return [l.get("publisherName") or l.get("publisherId") for l in eng().where_live(c["entity_id"])]


def _backup_label(eid):
    ch = eng().approvers(eid)
    return f"{ch[0].get('name')} ({ch[0].get('phone')})" if ch else None


def _settings_text(frm, text, c) -> bool:
    from . import settings as S
    e = eng()
    t = text.strip().lower()
    if re.fullmatch(r"(/?settings|rules|my settings|preferences|asetukset)\??", t):
        m = S.render(S.get(e.state, c["entity_id"]), _monitored(c), _backup_label(c["entity_id"]))
        _log(c, "settings", m, _wa().send_text(frm, m))
        e.save()
        return True
    from . import chat_edit
    if chat_edit.parse_request(text, config.SNAPSHOT)[0]:
        return False  # a date in it -> it's an hours request, not a settings change
    ch = S.parse_change(text, _monitored(c))
    if not ch:
        return False
    e.state.setdefault("wa_set", {})[frm] = {"cid": c["id"], "ch": ch}
    m = "Change your settings: " + S.describe(ch) + "?"
    _log(c, "settings confirm", m, _wa().send_buttons(frm, m, [("ss", "Save"), ("sc", "Cancel")]))
    e.save()
    return True


def _settings_button(frm, bid):
    from . import settings as S
    e = eng()
    req = e.state.setdefault("wa_set", {}).pop(frm, None)
    if not req:
        return
    c = e.case(req["cid"])
    if bid == "ss":
        S.apply(e.state, c["entity_id"], req["ch"])
        if req["ch"].get("auto_add"):  # newly pre-approved days that are already waiting get handled now
            with __import__("app.engine", fromlist=["LOCK"]).LOCK:
                e._auto_apply(c, include_sent=True)
                e._refresh(c)
        m = "Saved ✅\n\n" + S.render(S.get(e.state, c["entity_id"]), _monitored(c), _backup_label(c["entity_id"]))
    else:
        m = "OK, nothing changed."
    _log(c, "settings " + ("saved" if bid == "ss" else "cancelled"), m, _wa().send_text(frm, m))
    e.save()


def _free_text(frm, text):
    from . import chat_edit
    e = eng()
    oc = _owner_case(frm)
    if oc and not e.state.get("wa_req", {}).get(frm) and _settings_text(frm, text, oc):
        return
    req = e.state.setdefault("wa_req", {}).get(frm)
    c = e.case(req["cid"]) if req else _owner_case(frm)
    if not c:
        return
    lang = c["lang"]
    ds, h = chat_edit.parse_request(text, config.SNAPSHOT)
    if not (ds and h):  # rules didn't get all of it: ask the light AI model, then validate its answer
        from . import nlu
        from .hours import day_str
        try:
            hours = (e.yext.get_entity(c["entity_id"], "hours") or {}).get("hours") or {}
            regular = {d: day_str(hours.get(d) or {}) for d in nlu.DAYS}
        except Exception:
            regular = {}
        ad, ah = nlu.parse(text, config.SNAPSHOT, regular)
        if ad:
            ds, h = ad, (ah or h)
    if not ds and req and req.get("dates") and not req.get("hours"):
        ds, h = req["dates"], chat_edit.parse_hours(text)
    if not ds:
        m = chat_edit.HELP[lang]
        _log(c, "help", m, _wa().send_text(frm, m))
        e.save()
        return
    e.state["wa_req"][frm] = {"cid": c["id"], "dates": ds, "hours": h}
    if not h:
        m = chat_edit.ASK_HOURS[lang].format(days=_days_text(c, ds))
        _log(c, "request: ask hours", m, _wa().send_text(frm, m))
    else:
        shown = ", ".join(sorted({nice(e.shown_on(c["entity_id"], d)) if e.shown_on(c["entity_id"], d) != "closed"
                                  else messages.T[lang]["closed"] for d in ds}))
        hn = messages.T[lang]["closed"] if h == "closed" else nice(h)
        m = chat_edit.CONFIRM_REQ[lang].format(days=_days_text(c, ds), h=hn, shown=shown)
        b = chat_edit.buttons(lang)
        _log(c, "request: confirm", m, _wa().send_buttons(frm, m, [("rs", b[0]), ("rc", "Cancel" if lang == "en" else b[1])]))
    e.save()


@app.post("/api/shift-gap/{eid}")
def demo_shift_gap(eid: str):
    """Demo: the shift platform reports that tomorrow's opening barista dropped the shift; run the check now."""
    from . import shifts
    day = shifts.tomorrow()
    rows = shifts.schedule(eid, day, eng().state)
    if rows:
        eng().state.setdefault("shift_overrides", {}).setdefault(eid, {})[day.isoformat()] = {rows[0]["start"]: None}
    return JSONResponse(shift_check(eid, force=True))


def shift_check(eid: str, force: bool = False) -> dict:
    """Evening check of tomorrow's opening shift; WhatsApp the owner if nobody is on it (once per date)."""
    from . import shifts
    e = eng()
    day = shifts.tomorrow()
    gap = shifts.opening_gap(eid, day, e.state)
    if not gap:
        return {"gap": None}
    sent = e.state.setdefault("shift_alerts", {})
    key = f"{eid}:{day.isoformat()}"
    if key in sent and not force:
        return {"gap": gap, "sent": False}
    ent = __import__("app.kitdata", fromlist=["entities"]).entities().get(eid, {})
    first = os.environ.get("DEMO_FIRST") or "there"
    to = os.environ.get("WA_TO", "")
    text = shifts.alert_text(first, ent.get("name", eid), day, gap)
    res = _wa().send_buttons(to, text, [("shc", "Close tomorrow AM"), ("shk", "I'll sort it")])
    sent[key] = {"at": __import__("app.learning", fromlist=["now_iso"]).now_iso(), "gap": gap}
    e.state.setdefault("wa_shift", {})[channels.WhatsAppCloudChannel().recipient(to) if to else ""] = \
        {"eid": eid, "date": day.isoformat(), "gap": gap}
    e.learning.record({"entity_id": eid, "type": "shift alert", "date": day.isoformat(),
                       "channel": "whatsapp", "gap": gap})
    e.save()
    return {"gap": gap, "sent": True, "result": res}


def shifts_ampm(h):
    from .shifts import _ampm
    return _ampm(h)


def _shift_button(frm, bid):
    e = eng()
    st = e.state.setdefault("wa_shift", {})
    req = st.pop(frm, None) or (st.pop(next(iter(st)), None) if len(st) == 1 else None)
    if not req:
        return
    eid, d, gap = req["eid"], req["date"], req["gap"]
    if bid == "shk":
        m = "OK, I'll leave tomorrow's hours as they are. Thanks for letting me know."
        e.learning.record({"entity_id": eid, "type": "decision", "date": d, "decision": "shift: owner will sort it",
                           "channel": "whatsapp"})
    else:
        from datetime import date as _d
        from .hours import day_str
        ent = __import__("app.kitdata", fromlist=["entities"]).entities().get(eid, {})
        wd = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"][_d.fromisoformat(d).weekday()]
        usual = day_str((ent.get("hours") or {}).get(wd))
        close_at = gap["end"]
        hours = f"{close_at}-{usual.split('-')[-1]}" if usual and usual != "closed" and "-" in usual else "closed"
        if hours != "closed" and hours.split("-")[0] >= hours.split("-")[1]:
            hours = "closed"
        out = e.owner_request(eid, {d: hours}, channel="whatsapp (shift alert)")
        live = ", ".join(out.get("live") or []) if isinstance(out.get("live"), list) else str(out.get("live") or "")
        m = (("Done. Closed tomorrow on Google" if hours == "closed" else
              f"Done. Tomorrow you open at {shifts_ampm(close_at)} instead")
             + ", so nobody walks up to a locked door."
             + (f" Live on: {live}." if live else ""))
    _wa().send_text(frm, m)
    e.save()


def _request_button(frm, bid):
    e = eng()
    req = e.state.setdefault("wa_req", {}).pop(frm, None)
    if not req or not req.get("hours"):
        return
    c = e.case(req["cid"])
    if bid == "rc":
        m = messages.declined(e.ctx(c))
        _log(c, "request cancelled", m, _wa().send_text(frm, m))
    else:
        out = e.owner_request(c["entity_id"], {d: req["hours"] for d in req["dates"]})
        items = [{"date": d, "day_key": "", "name_en": "", "final_hours": req["hours"], "hours": req["hours"]} for d in req["dates"]]
        try:
            m = messages.confirmation(e.ctx(c), items, out["live"], True)
        except Exception:
            m = "Done! Saved."
        _log(c, "request saved", m, _wa().send_text(frm, m))
    e.save()


def _edit_text(frm, text):
    from . import chat_edit
    if _review_edit_text(frm, text):
        return
    st = _edit_state().get(frm)
    if not st:
        return _free_text(frm, text)
    c, it = _edit_item(st)
    h = chat_edit.parse_hours(text)
    if not h:
        m = chat_edit.not_understood(c["lang"])
        _log(c, "edit retry", m, _wa().send_text(frm, m))
    else:
        st["hours"] = h
        m = chat_edit.confirm(it, c["lang"], h)
        b = chat_edit.buttons(c["lang"])
        _log(c, "edit confirm", m, _wa().send_buttons(frm, m, [("es", b[0]), ("er", b[1])]))
    eng().save()


def _edit_button(frm, bid):
    from . import chat_edit
    st = _edit_state().get(frm)
    if not st or not st.get("hours"):
        return
    c, it = _edit_item(st)
    if bid == "er":
        st["hours"] = None
        m = chat_edit.again(it, c["lang"])
        _log(c, "edit again", m, _wa().send_text(frm, m))
        eng().save()
        return
    eng().decide(c["id"], {it["date"]: {"action": "edit", "hours": st["hours"]}}, channel="whatsapp chat")
    st["i"] += 1
    if st["i"] < len(st["dates"]):
        st["hours"] = None
        c, nxt = _edit_item(st)
        q = chat_edit.question(nxt, c["lang"])
        _log(c, "edit question", q, _wa().send_text(frm, q))
    else:
        _edit_state().pop(frm, None)
    eng().save()

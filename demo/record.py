"""Records the real app (no mock-ups): every clip is the running console / owner page, driven by Playwright.
Usage: .venv/bin/python demo/record.py OUTDIR      (app on :8800, kit mock on :8787)"""
import json
import os
import sys
import time
import urllib.request

from playwright.sync_api import sync_playwright

B = "http://localhost:8800"
OUT = sys.argv[1] if len(sys.argv) > 1 else "/tmp/fonecta_rec"
os.makedirs(OUT, exist_ok=True)


def api(path, method="GET"):
    r = urllib.request.urlopen(urllib.request.Request(B + path, method=method))
    return json.loads(r.read() or b"null") if method == "GET" else r.status


def case(eid):
    return [c for c in api("/api/cases") if c["entity_id"] == eid][0]


MARKS = {}
T0 = [0.0]
CUR = [""]


def mark(label):
    MARKS.setdefault(CUR[0], []).append([label, round(time.time() - T0[0], 2)])


def clip(p, name, w, h, scale, fn):
    CUR[0] = name
    T0[0] = time.time()
    ctx = p.new_context(viewport={"width": w, "height": h}, device_scale_factor=1,
                        record_video_dir=OUT, record_video_size={"width": w, "height": h})
    page = ctx.new_page()
    fn(page)
    path = page.video.path()
    ctx.close()
    os.replace(path, os.path.join(OUT, name + ".webm"))
    with open(os.path.join(OUT, "marks.json"), "w") as f:
        json.dump(MARKS, f, indent=1)
    print("recorded", name, flush=True)


def smooth_scroll_to(page, sel, dur=1.2):
    page.evaluate("""([sel, dur]) => { const el = document.querySelector(sel); if (!el) return;
      const y0 = window.scrollY, y1 = el.getBoundingClientRect().top + window.scrollY - 20, t0 = performance.now();
      return new Promise(res => { function step(t){ const k = Math.min(1,(t-t0)/(dur*1000));
        window.scrollTo(0, y0 + (y1-y0)*(0.5-Math.cos(Math.PI*k)/2)); k<1 ? requestAnimationFrame(step) : res(); }
        requestAnimationFrame(step); }); }""", [sel, dur])


with sync_playwright() as p:
    br = p.chromium.launch()
    api("/api/reset", "POST")

    def s1(page):  # console, detection run live
        page.goto(B + "/")
        page.wait_for_timeout(1500)
        mark("detect")
        page.click("text=Run detection")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(4000)
        for eid in ("FI-D0001",):
            mark("aurora")
            smooth_scroll_to(page, f"#case-{eid}", 1.5)
            page.wait_for_timeout(5000)
    clip(br, "01_console_detect", 1280, 720, 1, s1)

    def s2(page):  # send to Kahvila Aurora: message appears on the (mock) phone
        page.goto(B + "/#case-FI-D0001")
        page.wait_for_timeout(1200)
        mark("send")
        page.locator("#case-FI-D0001 button:has-text('3 · Send')").click()
        page.wait_for_load_state("networkidle")
        smooth_scroll_to(page, "#case-FI-D0001", 0.8)
        page.wait_for_timeout(7000)
    clip(br, "02_send", 1280, 720, 1, s2)

    link = case("FI-D0001")["token"]

    def s3(page):  # the owner's phone: no login, edit one day, decline one, approve the rest
        mark("open")
        page.goto(f"{B}/s/{link}")
        page.wait_for_timeout(3500)
        page.mouse.wheel(0, 300)
        page.wait_for_timeout(1200)
        mark("edit")
        page.check("input[name='a_2026-12-24'][value=edit]")
        page.wait_for_timeout(600)
        page.fill("input[name='o_2026-12-24']", "08:00")
        page.fill("input[name='c_2026-12-24']", "14:00")
        page.wait_for_timeout(900)
        page.check("input[name='a_2026-12-06'][value=decline]")
        page.wait_for_timeout(900)
        page.mouse.wheel(0, 600)
        page.wait_for_timeout(1200)
        mark("save")
        page.click("button.btn.p")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(4000)
        page.mouse.wheel(0, 400)
        page.wait_for_timeout(3000)
        page.click("button:has-text('Ei tänä vuonna')")
        page.wait_for_timeout(2500)
    clip(br, "03_owner_phone", 390, 780, 1, s3)

    def s4(page):  # proof: the hours are in Yext, and what Connect learned
        mark("yext")
        page.goto("http://localhost:8787/v2/accounts/me/entities/FI-D0001?api_key=demo&v=20261101")
        page.wait_for_timeout(1000)
        page.evaluate("""() => { const pre = document.querySelector('pre') || document.body;
            const j = JSON.parse(pre.innerText); const h = j.response.hours.holidayHours;
            document.body.innerHTML = '<div style="font:20px -apple-system,Helvetica;padding:40px"><div style="color:#5b3fa0;font-weight:600">Yext API · GET entities/FI-D0001 · hours.holidayHours</div><pre style="font-size:22px">' + JSON.stringify(h, null, 2) + '</pre></div>'; }""")
        page.wait_for_timeout(5000)
        page.goto(B + "/#case-FI-D0001")
        page.wait_for_timeout(800)
        mark("learned")
        page.locator("#case-FI-D0001 summary:has-text('learned')").click()
        page.wait_for_timeout(5500)
    clip(br, "04_yext_and_learning", 1280, 720, 1, s4)

    def s5(page):  # the cases that should NOT get a normal message
        page.goto(B + "/")
        for eid, wait in (("FI-D0012", 6000), ("FI-D0017", 6000), ("FI-D0011", 4000), ("FI-D0013", 3500)):
            mark(eid)
            smooth_scroll_to(page, f"#case-{eid}", 1.2)
            page.wait_for_timeout(wait)
    clip(br, "05_special_cases", 1280, 720, 1, s5)

    def s6(page):  # escalation, urgent call, reviews, live events
        c = case("SE-D0008")
        api(f"/api/send/{c['id']}", "POST")
        page.goto(B + "/#case-SE-D0008")
        page.wait_for_timeout(1500)
        mark("escalate")
        page.locator("#case-SE-D0008 button:has-text('Escalate')").click()
        page.wait_for_load_state("networkidle")
        smooth_scroll_to(page, "#case-SE-D0008", 0.6)
        page.wait_for_timeout(5000)
        mark("call")
        page.locator("#case-SE-D0008 button:has-text('Urgent')").click()
        page.wait_for_load_state("networkidle")
        smooth_scroll_to(page, "#case-SE-D0008", 0.6)
        page.wait_for_timeout(5000)
        mark("reviews")
        smooth_scroll_to(page, "#case-NO-D0009", 1.0)
        page.locator("#case-NO-D0009 button:has-text('Reviews')").click()
        page.wait_for_load_state("networkidle")
        smooth_scroll_to(page, "#rev-NO-D0009", 0.6)
        page.wait_for_timeout(6000)
        mark("events")
        smooth_scroll_to(page, "#case-FI-00125", 1.2)
        page.wait_for_timeout(1500)
        page.wait_for_timeout(1000)
        page.evaluate("""() => { const r=[...document.querySelectorAll('#case-FI-00125 tr')].find(t=>t.innerText.includes('LIVE_EVENT'));
                           if (r) window.scrollTo({top: r.getBoundingClientRect().top + window.scrollY - 250, behavior: 'smooth'}); }""")
        page.wait_for_timeout(6000)
    clip(br, "06_escalate_call_reviews_events", 1280, 720, 1, s6)
    br.close()

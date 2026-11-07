"""Video v2: records the presenter view (/demo) end to end, then the extra cases from the console. Real app only.
Usage: APP_CONSOLE_KEY=... .venv/bin/python demo/record2.py OUTDIR"""
import json, os, sys, time
from playwright.sync_api import sync_playwright
B = "http://localhost:8800"; K = os.environ.get("APP_CONSOLE_KEY", "")
OUT = sys.argv[1]; os.makedirs(OUT, exist_ok=True)
MARKS = {}
def rec(p, name, fn, w=1600, h=900):
    t0 = time.time(); m = MARKS.setdefault(name, [])
    ctx = p.new_context(viewport={"width": w, "height": h}, record_video_dir=OUT, record_video_size={"width": w, "height": h})
    pg = ctx.new_page(); fn(pg, lambda lab: m.append([lab, round(time.time() - t0, 2)]))
    path = pg.video.path(); ctx.close(); os.replace(path, os.path.join(OUT, name + ".webm"))
    json.dump(MARKS, open(os.path.join(OUT, "marks.json"), "w"), indent=1); print("recorded", name, flush=True)
with sync_playwright() as p:
    br = p.chromium.launch()
    prep = br.new_page(); prep.goto(f"{B}/demo?eid=FI-D0001&k={K}"); prep.click("text=Reset this business"); prep.wait_for_load_state("networkidle"); prep.close()
    def main(pg, mark):
        pg.goto(f"{B}/demo?eid=FI-D0001&k={K}"); mark("detect"); pg.wait_for_timeout(9000)
        mark("send"); pg.click("text=3 · Send"); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(5500)
        f = pg.frame_locator("#ph"); mark("decide")
        f.locator("input[name='a_2026-12-24'][value=edit]").check(); pg.wait_for_timeout(700)
        f.locator("input[name='o_2026-12-24']").fill("08:00"); f.locator("input[name='c_2026-12-24']").fill("14:00"); pg.wait_for_timeout(1200)
        f.locator("input[name='a_2026-12-06'][value=decline]").check(); pg.wait_for_timeout(1500)
        f.locator("button.btn.p").scroll_into_view_if_needed(); pg.wait_for_timeout(800)
        f.locator("button.btn.p").click(); mark("saved"); pg.wait_for_timeout(5000)
        mark("apply"); pg.mouse.wheel(0, 500); pg.wait_for_timeout(6000)
    rec(br, "v2_main", main)
    # the owner's own confirmation screen (preview card) on a phone viewport
    def phone(pg, mark):
        cs = json.loads(pg.request.get(f"{B}/api/cases?k={K}").text())
        c = [x for x in cs if x["entity_id"] == "SE-D0008"][0]
        pg.request.post(f"{B}/api/send/{c['id']}?k={K}")
        cs = json.loads(pg.request.get(f"{B}/api/cases?k={K}").text()); c = [x for x in cs if x["id"] == c["id"]][0]
        pg.goto(f"{B}/s/{c['token']}"); mark("open"); pg.wait_for_timeout(2500); pg.mouse.wheel(0, 2000); pg.wait_for_timeout(800)
        pg.click("button.btn.p"); mark("done"); pg.wait_for_timeout(6000)
    rec(br, "v2_phone_sv", phone, 390, 780)
    br.close()

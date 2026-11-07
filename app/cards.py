"""Header image for WhatsApp suggestions: a small card with the date, Google's wrong hours struck out, ours in green."""
from __future__ import annotations

import os
from datetime import date

from PIL import Image, ImageDraw, ImageFont

from . import config, messages
from .hours import nice

BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
REG = "/System/Library/Fonts/Supplemental/Arial.ttf"
LABELS = {"en": ("Google shows now", "Suggested"), "fi": ("Google näyttää nyt", "Ehdotus"),
          "sv": ("Google visar nu", "Förslag"), "nb": ("Google viser nå", "Forslag")}


def _f(size, bold=True):
    path = BOLD if bold else (REG if os.path.exists(REG) else BOLD)
    return ImageFont.truetype(path, size)


def hours_card(name: str, items, lang: str) -> str:
    """One date: big card. Several back-to-back dates: one row per date."""
    items = items if isinstance(items, list) else [items]
    lang = messages.lang_of(lang)
    lab_now, lab_new = LABELS.get(lang, LABELS["en"])
    closed = messages.T[lang]["closed"]
    W, H = 1200, 630
    im = Image.new("RGB", (W, H), (91, 63, 160))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((50, 50, W - 50, H - 50), 36, fill="white")
    d.text((100, 90), name, font=_f(40, False), fill=(110, 110, 120))
    hrs = lambda h: closed if h == "closed" else nice(h)  # noqa: E731
    if len(items) == 1:
        it = items[0]
        dt = date.fromisoformat(it["date"])
        d.text((100, 145), messages.day_name(it, lang, it.get("event_name")), font=_f(64), fill=(29, 27, 38))
        d.text((100, 225), f"{messages.WD_LONG[lang][dt.weekday()].capitalize()} {messages.dm(dt, lang)}",
               font=_f(40, False), fill=(91, 63, 160))
        rows, y0, fs = [(None, it)], 375, _f(80)
        d.text((100, 330), lab_now, font=_f(32, False), fill=(110, 110, 120))
        d.text((620, 330), lab_new, font=_f(32, False), fill=(110, 110, 120))
        x_now, x_new, step = 100, 620, 0
    else:
        d.text((470, 150), lab_now, font=_f(28, False), fill=(110, 110, 120))
        d.text((760, 150), lab_new, font=_f(28, False), fill=(110, 110, 120))
        rows, y0, fs = [(i, it) for i, it in enumerate(items)], 200, _f(50)
        x_now, x_new, step = 470, 760, 92
    for k, it in rows:
        y = y0 + (k or 0) * step
        if k is not None:
            dt = date.fromisoformat(it["date"])
            d.text((100, y + 8), f"{messages.WD_SHORT[lang][dt.weekday()]} {messages.dm(dt, lang)}", font=_f(38), fill=(29, 27, 38))
        shown = hrs(it["shown_hours"])
        d.text((x_now, y), shown, font=fs, fill=(179, 38, 30))
        w = d.textlength(shown, font=fs)
        mid = y + (45 if k is None else 30)
        d.line((x_now - 4, mid, x_now + w + 4, mid), fill=(179, 38, 30), width=8 if k is None else 6)
        d.text((x_new, y), hrs(it["hours"]), font=fs, fill=(24, 128, 56))
    out = os.path.join(config.var_dir(), "cards")
    os.makedirs(out, exist_ok=True)
    path = os.path.join(out, f"{items[0].get('entity_id', 'x')}_{items[0]['date']}_{len(items)}_{lang}.png")
    im.save(path)
    return path

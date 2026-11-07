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


def hours_card(name: str, it: dict, lang: str) -> str:
    lang = messages.lang_of(lang)
    W, H = 1200, 630
    im = Image.new("RGB", (W, H), (91, 63, 160))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((50, 50, W - 50, H - 50), 36, fill="white")
    dt = date.fromisoformat(it["date"])
    day = messages.day_name(it, lang, it.get("event_name"))
    d.text((100, 95), name, font=_f(40, False), fill=(110, 110, 120))
    d.text((100, 150), f"{day}", font=_f(64), fill=(29, 27, 38))
    d.text((100, 230), f"{messages.WD_LONG[lang][dt.weekday()].capitalize()} {messages.dm(dt, lang)}",
           font=_f(40, False), fill=(91, 63, 160))
    lab_now, lab_new = LABELS.get(lang, LABELS["en"])
    closed = messages.T[lang]["closed"]
    shown = closed if it["shown_hours"] == "closed" else nice(it["shown_hours"])
    new = closed if it["hours"] == "closed" else nice(it["hours"])
    d.text((100, 330), lab_now, font=_f(32, False), fill=(110, 110, 120))
    fs = _f(80)
    d.text((100, 375), shown, font=fs, fill=(179, 38, 30))
    w = d.textlength(shown, font=fs)
    d.line((96, 420, 104 + w, 420), fill=(179, 38, 30), width=8)
    d.text((620, 330), lab_new, font=_f(32, False), fill=(110, 110, 120))
    d.text((620, 375), new, font=fs, fill=(24, 128, 56))
    d.text((535, 385), "→", font=_f(70), fill=(150, 150, 160))
    out = os.path.join(config.var_dir(), "cards")
    os.makedirs(out, exist_ok=True)
    path = os.path.join(out, f"{it.get('entity_id', 'x')}_{it['date']}_{lang}.png")
    im.save(path)
    return path

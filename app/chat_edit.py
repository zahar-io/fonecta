"""Edit by chatting in WhatsApp: tap Edit -> "What hours on Christmas Eve?" -> type "8-14" or "closed" ->
"Save 8–14?" [Save] [Try again] -> written to Yext. One date at a time; nothing is saved without the Save tap."""
from __future__ import annotations

import re

from . import messages
from .hours import is_valid, nice

CLOSED = ("closed", "close", "kiinni", "suljettu", "stängt", "stengt", "off", "shut")
_T = r"(\d{1,2})(?:[:.](\d{2}))?\s*(am|pm)?"
RANGE = re.compile(_T + r"\s*(?:-|–|—|to|till|until|>)\s*" + _T, re.I)


def _hm(h, m, ap):
    h, m = int(h), int(m or 0)
    if ap:
        ap = ap.lower()
        if ap == "pm" and h < 12:
            h += 12
        if ap == "am" and h == 12:
            h = 0
    if h == 24:
        h = 0
    return f"{h:02d}:{m:02d}" if 0 <= h < 24 and 0 <= m < 60 else None


def parse_hours(text: str) -> str | None:
    """'8-14', '8:30–13', '10am to 4pm', '10-14, 17-22', 'closed' -> canonical hours string, else None."""
    t = (text or "").strip().lower()
    if any(w == t or t.startswith(w) for w in CLOSED):
        return "closed"
    ivs = []
    for m in RANGE.finditer(t):
        a, b = _hm(m.group(1), m.group(2), m.group(3)), _hm(m.group(4), m.group(5), m.group(6))
        if not a or not b:
            return None
        if b == "00:00":
            b = "23:59" if a == "00:00" else b
        ivs.append(f"{a}-{b}")
    out = ",".join(ivs)
    return out if ivs and is_valid(out) else None


Q = {"en": ("What hours will you be open on {day}, {wd} {dm}?\nReply like *9-17*, *10am-4pm*, *10-14, 17-22* or *closed*.",
            "Got it: *{day}, {wd} {dm}: {h}*. Save it?", "Sorry, I didn't catch that. Try *9-17* or *closed*.",
            ("Save", "Try again"), "OK, tell me the hours again for {day}."),
     "fi": ("Mihin aikaan olette auki {day}na, {wd} {dm}?\nVastaa esim. *9-17*, *10-14, 17-22* tai *kiinni*.",
            "Selvä: *{day}, {wd} {dm}: {h}*. Tallennetaanko?", "En ymmärtänyt. Kokeile *9-17* tai *kiinni*.",
            ("Tallenna", "Uudestaan"), "OK, kerro {day} aukioloajat uudelleen."),
     "sv": ("Vilka tider har ni öppet på {day}, {wd} {dm}?\nSvara t.ex. *9-17*, *10-14, 17-22* eller *stängt*.",
            "Uppfattat: *{day}, {wd} {dm}: {h}*. Spara?", "Jag förstod inte. Prova *9-17* eller *stängt*.",
            ("Spara", "Försök igen"), "OK, skriv tiderna för {day} igen."),
     "nb": ("Hvilke tider har dere åpent {day}, {wd} {dm}?\nSvar f.eks. *9-17*, *10-14, 17-22* eller *stengt*.",
            "Notert: *{day}, {wd} {dm}: {h}*. Lagre?", "Jeg forsto ikke. Prøv *9-17* eller *stengt*.",
            ("Lagre", "Prøv igjen"), "OK, skriv tidene for {day} på nytt.")}


def _fmt(it, lang):
    from datetime import date
    d = date.fromisoformat(it["date"])
    return {"day": messages.day_name(it, lang, it.get("event_name")), "wd": messages.WD_SHORT[lang][d.weekday()],
            "dm": messages.dm(d, lang)}


def question(it, lang):
    return Q[lang][0].format(**_fmt(it, lang))


def confirm(it, lang, hours):
    h = messages.T[lang]["closed"] if hours == "closed" else nice(hours)
    return Q[lang][1].format(h=h, **_fmt(it, lang))


def not_understood(lang):
    return Q[lang][2]


def buttons(lang):
    return Q[lang][3]


def again(it, lang):
    return Q[lang][4].format(**_fmt(it, lang))

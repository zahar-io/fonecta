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
    if not RANGE.search(t) and re.search(r"\b(" + "|".join(CLOSED) + r")\b", t):
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


Q = {"en": ("✏️ What hours will you be open on {day}, {wd} {dm}?\nReply like *9-17*, *10-14, 17-22* or *closed*.",
            "👍 Got it: *{day}, {wd} {dm}: {h}*. Save it?", "Sorry, I didn't catch that. Try *9-17* or *closed*.",
            ("💾 Save", "↩️ Try again"), "OK, tell me the hours again for {day}."),
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


# ------------------------------------------------------------------ free text: "can you also set 16-22 on 2nd December?"
MONTHS = {m: i + 1 for i, names in enumerate([
    ("jan", "january", "tammikuu", "januari", "januar"), ("feb", "february", "helmikuu", "februari", "februar"),
    ("mar", "march", "maaliskuu", "mars"), ("apr", "april", "huhtikuu"), ("may", "toukokuu", "maj", "mai"),
    ("jun", "june", "kesäkuu", "juni"), ("jul", "july", "heinäkuu", "juli"), ("aug", "august", "elokuu", "augusti"),
    ("sep", "sept", "september", "syyskuu"), ("oct", "october", "lokakuu", "oktober"),
    ("nov", "november", "marraskuu"), ("dec", "december", "joulukuu", "desember")]) for m in names}
_DAY = r"(\d{1,2})(?:st|nd|rd|th|\.)?"
_MON = r"(" + "|".join(sorted(MONTHS, key=len, reverse=True)) + r")[a-zä]*"


def parse_request(text: str, today):
    """-> ([iso dates], hours) or (None, None). Understands '2nd December', 'Dec 2', '2.12.', '24-26 Dec'."""
    from datetime import date as _d
    t = (text or "").lower()
    dates = []
    m = re.search(r"(?<![\d:.\-–])" + _DAY + r"\s*(?:-|–)\s*" + _DAY + r"\s+(?:of\s+)?" + _MON, t)
    if m:
        a, b, mon = int(m.group(1)), int(m.group(2)), MONTHS[m.group(3)]
        dates = [(a + k, mon) for k in range(0, max(0, b - a) + 1)][:7]
        t_wo = t[:m.start()] + " " + t[m.end():]
    else:
        m = (re.search(_DAY + r"\s+(?:of\s+)?" + _MON, t) or re.search(_MON + r"\s+" + _DAY, t)
             or re.search(r"\b(\d{1,2})\.(\d{1,2})\.?(?!\d)", t))
        if not m:
            return None, None
        g = m.groups()
        if g[0].isdigit() and len(g) == 2 and g[1].isdigit():
            dates = [(int(g[0]), int(g[1]))]
        elif g[0].isdigit():
            dates = [(int(g[0]), MONTHS[g[1]])]
        else:
            dates = [(int(g[1]), MONTHS[g[0]])]
        t_wo = t[:m.start()] + " " + t[m.end():]
    out = []
    for day, mon in dates:
        y = today.year if (mon, day) >= (today.month, today.day) else today.year + 1
        try:
            out.append(_d(y, mon, day).isoformat())
        except ValueError:
            return None, None
    return out, parse_hours(t_wo)


HELP = {"en": "I can change your opening hours for a day. Try: *Set 16-22 on 2 December* or *Closed on 24 Dec*.",
        "fi": "Voin muuttaa päivän aukioloajat. Kokeile: *16-22 2. joulukuuta* tai *kiinni 24.12.*",
        "sv": "Jag kan ändra öppettiderna för en dag. Prova: *16-22 den 2 december* eller *stängt 24 dec*.",
        "nb": "Jeg kan endre åpningstidene for en dag. Prøv: *16-22 2. desember* eller *stengt 24. des*."}
ASK_HOURS = {"en": "Which hours for {days}? Reply like *16-22* or *closed*.",
             "fi": "Mitkä aukioloajat {days}? Vastaa esim. *16-22* tai *kiinni*.",
             "sv": "Vilka tider {days}? Svara t.ex. *16-22* eller *stängt*.",
             "nb": "Hvilke tider {days}? Svar f.eks. *16-22* eller *stengt*."}
CONFIRM_REQ = {"en": "📅 *{days}*\n🔴 Google shows: {shown}\n🟢 New hours: *{h}*\n\nSave this change?",
               "fi": "Asetetaanko *{days}*: *{h}*? Google näyttää nyt: {shown}.",
               "sv": "Ändra *{days}* till *{h}*? Google visar nu: {shown}.",
               "nb": "Endre *{days}* til *{h}*? Google viser nå: {shown}."}

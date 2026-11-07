"""Same loop, second use case: reviews (extensibility).

* A new bad review (<= 2 stars, or a complaint keyword) -> the owner gets it with a ready reply in the review's
  language -> Post / Edit / Skip, no login -> the reply goes to Yext (POST /reviews/{id}/comments).
* Every week -> a general summary: count, average, good vs poor, what people liked and what they complained about.
Replies are template-based on purpose: predictable, in fi/sv/nb/en, never inventing facts about the business.
"""
from __future__ import annotations

import re
from collections import Counter
from datetime import datetime, timedelta

BAD = {
    "closed": ("kiinni", "suljettu", "stängt", "stengt", "closed", "locked", "lukossa", "låst"),
    "price": ("kallis", "hinta", "dyrt", "dyr ", "expensive", "overpriced", "too much"),
    "slow": ("hidas", "odot", "jono", "långsam", "vänta", "kö ", "treg", "vente", "slow", "wait"),
    "rude": ("töykeä", "epäkohtelias", "otrevlig", "sur ", "uhøflig", "frekk", "rude", "unfriendly"),
    "quality": ("kylmä", "mauton", "pahaa", "kall", "smaklös", "kald", "smakløs", "cold", "bland", "tasteless"),
}
GOOD = {
    "staff": ("henkilökunta", "palvelu", "personal", "betjening", "personale", "staff", "service"),
    "coffee": ("kahvi", "kaffe", "coffee"),
    "food": ("ruoka", "annos", "lounas", "mat", "lunch", "food", "pizza", "pulla", "bulle", "bolle", "pastr"),
    "atmosphere": ("tunnelma", "viihtyisä", "cosy", "cozy", "mysig", "koselig", "atmosphere"),
    "value": ("hinta-laatu", "prisvärd", "value for money", "god verdi", "edullinen"),
    "speed": ("nopea", "snabb", "rask", "quick", "fast"),
}
WORDS = {"fi": ("ja", "oli", "ei", "mutta", "hyvä", "kiitos", "todella"),
         "sv": ("och", "var", "inte", "men", "bra", "tack", "för"),
         "nb": ("og", "var", "ikke", "men", "bra", "takk", "for"),
         "en": ("and", "was", "not", "but", "good", "thanks", "the")}

REPLY = {
    "fi": {"hi": "Kiitos palautteestanne!", "closed": "Pahoittelemme, että ovemme oli kiinni vaikka netissä luki toisin. "
           "Olemme nyt tarkistaneet aukioloaikamme, jotta näin ei käy uudelleen.",
           "price": "Kiitos, että kerroitte hinnoista. Otamme tämän huomioon.",
           "slow": "Pahoittelemme odottamista. Käymme tämän läpi tiimin kanssa.",
           "rude": "Pahoittelemme kokemustanne. Tämä ei ole tapamme palvella, ja puhumme asiasta tiimin kanssa.",
           "quality": "Pahoittelemme, ettei annos ollut odotusten mukainen. Välitämme palautteen keittiöön.",
           "generic": "Pahoittelemme, ettei käynti ollut odotusten mukainen.",
           "end": "Toivottavasti saamme uuden mahdollisuuden. Terveisin {name}"},
    "sv": {"hi": "Tack för er feedback!", "closed": "Vi beklagar att det var stängt fast det stod öppet på nätet. "
           "Vi har nu gått igenom våra öppettider så att det inte händer igen.",
           "price": "Tack för att ni berättade om priserna. Vi tar med oss det.",
           "slow": "Vi beklagar väntetiden. Vi går igenom det med teamet.",
           "rude": "Vi beklagar er upplevelse. Så vill vi inte bemöta någon, och vi pratar med teamet.",
           "quality": "Vi beklagar att det inte höll måttet. Vi skickar vidare det till köket.",
           "generic": "Vi beklagar att besöket inte blev som ni hoppats.",
           "end": "Vi hoppas få en ny chans. Hälsningar {name}"},
    "nb": {"hi": "Takk for tilbakemeldingen!", "closed": "Beklager at det var stengt selv om det sto åpent på nett. "
           "Vi har nå gått gjennom åpningstidene våre så det ikke skjer igjen.",
           "price": "Takk for at dere sa ifra om prisene. Vi tar det med oss.",
           "slow": "Beklager ventetiden. Vi går gjennom det med teamet.",
           "rude": "Beklager opplevelsen. Slik vil vi ikke møte gjestene våre, og vi tar det opp med teamet.",
           "quality": "Beklager at det ikke var som forventet. Vi gir beskjed til kjøkkenet.",
           "generic": "Beklager at besøket ikke ble som dere håpet.",
           "end": "Vi håper på en ny sjanse. Hilsen {name}"},
    "en": {"hi": "Thank you for your feedback!", "closed": "We're sorry we were closed when the listing said open. "
           "We've now checked our hours so it doesn't happen again.",
           "price": "Thanks for telling us about the prices. We'll take it on board.",
           "slow": "Sorry about the wait. We're going through it with the team.",
           "rude": "We're sorry about your experience. That's not how we want to treat anyone, and we'll talk to the team.",
           "quality": "Sorry it wasn't up to standard. We'll pass this on to the kitchen.",
           "generic": "We're sorry your visit wasn't what you hoped for.",
           "end": "We hope to see you again. Best wishes, {name}"},
}
OWNER = {
    "fi": ("Uusi {stars}★ arvio ({who}): ”{text}”", "Ehdotettu vastaus:", "[Julkaise] [Muokkaa] [Ohita]",
           "Arviot viikolla {start}–{end}: {n} kpl, keskiarvo {avg}★ ({good} hyvää, {poor} heikkoa). Pidettiin: {top}. Moitittiin: {bad}.",
           "Ei uusia arvioita tällä viikolla."),
    "sv": ("Ny {stars}★-recension ({who}): ”{text}”", "Förslag på svar:", "[Publicera] [Ändra] [Hoppa över]",
           "Recensioner {start}–{end}: {n} st, snitt {avg}★ ({good} bra, {poor} svaga). Uppskattat: {top}. Klagomål: {bad}.", "Inga nya recensioner i veckan."),
    "nb": ("Ny {stars}★-anmeldelse ({who}): «{text}»", "Forslag til svar:", "[Publiser] [Endre] [Hopp over]",
           "Anmeldelser {start}–{end}: {n} stk, snitt {avg}★ ({good} gode, {poor} svake). Likt: {top}. Klager: {bad}.", "Ingen nye anmeldelser denne uken."),
    "en": ("New {stars}★ review ({who}): \"{text}\"", "Suggested reply:", "[Post] [Edit] [Skip]",
           "Reviews {start}–{end}: {n}, average {avg}★ ({good} good, {poor} poor). Liked: {top}. Complaints: {bad}.", "No new reviews this week."),
}
TOPIC_NAMES = {
    "fi": {"staff": "henkilökunta", "coffee": "kahvi", "food": "ruoka", "atmosphere": "tunnelma", "value": "hinta-laatu",
           "speed": "nopeus", "closed": "kiinni", "price": "hinnat", "slow": "odotus", "rude": "palvelu",
           "quality": "laatu"},
    "sv": {"staff": "personalen", "coffee": "kaffet", "food": "maten", "atmosphere": "stämningen", "value": "prisvärdheten",
           "speed": "snabbheten", "closed": "stängt", "price": "priserna", "slow": "väntan", "rude": "bemötandet",
           "quality": "kvaliteten"},
    "nb": {"staff": "personalet", "coffee": "kaffen", "food": "maten", "atmosphere": "stemningen", "value": "prisen",
           "speed": "farten", "closed": "stengt", "price": "prisene", "slow": "ventetiden", "rude": "oppførselen",
           "quality": "kvaliteten"},
    "en": {"staff": "staff", "coffee": "coffee", "food": "food", "atmosphere": "atmosphere", "value": "value",
           "speed": "speed", "closed": "locked door", "price": "prices", "slow": "waiting", "rude": "rudeness",
           "quality": "quality"},
}


def lang_of(text: str, default: str = "fi") -> str:
    toks = re.findall(r"[a-zåäöæø]+", (text or "").lower())
    if not toks:
        return default
    scores = {lg: sum(t in w for t in toks) for lg, w in WORDS.items()}
    low = (text or "").lower()
    if any(c in low for c in "æø"):
        scores["nb"] += 3
    if "å" in low and not any(c in low for c in "äö"):
        scores["nb"] += 2
    if any(c in low for c in "äö") and "å" in low:
        scores["sv"] += 2
    scores[default] = scores.get(default, 0) + 0.5
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else default


def topics(text: str, table: dict) -> list:
    t = " " + (text or "").lower() + " "
    return [k for k, words in table.items() if any(w in t for w in words)]


def is_bad(r: dict) -> bool:
    return (r.get("rating") or 5) <= 2 or bool(topics(r.get("content"), {"closed": BAD["closed"], "rude": BAD["rude"]}))


def draft_reply(r: dict, business: str, default_lang: str) -> dict:
    lang = lang_of(r.get("content"), default_lang)
    t = REPLY[lang]
    tops = topics(r.get("content"), BAD) or ["generic"]
    body = " ".join([t["hi"]] + [t[k] for k in tops[:2]] + [t["end"].format(name=business)])
    return {"lang": lang, "topics": tops, "reply": body}


def owner_message(r: dict, draft: dict, owner_lang: str) -> str:
    o = OWNER.get(owner_lang, OWNER["en"])
    text = (r.get("content") or "").strip() or "–"
    return "\n".join([o[0].format(stars=int(r.get("rating") or 0), who=r.get("publisherId", ""), text=text[:300]),
                      "", o[1], draft["reply"], "", o[2]])


def weekly_summary(reviews: list, owner_lang: str, end: datetime) -> str:
    o = OWNER.get(owner_lang, OWNER["en"])
    start = end - timedelta(days=7)
    wk = [r for r in reviews if start.timestamp() * 1000 <= r["publisherDate"] <= end.timestamp() * 1000]
    if not wk:
        return o[4]
    avg = sum(r.get("rating") or 0 for r in wk) / len(wk)
    good = [r for r in wk if (r.get("rating") or 0) >= 4]
    poor = [r for r in wk if (r.get("rating") or 0) <= 2]
    names = TOPIC_NAMES.get(owner_lang, TOPIC_NAMES["en"])
    liked = Counter(t for r in good for t in topics(r.get("content"), GOOD))
    moaned = Counter(t for r in poor for t in topics(r.get("content"), BAD))
    fmt = lambda c: ", ".join(f"{names[k]} ({n})" for k, n in c.most_common(3)) or "–"
    return o[3].format(start=start.strftime("%d.%m."), end=end.strftime("%d.%m."), n=len(wk), avg=f"{avg:.1f}",
                       good=len(good), poor=len(poor), top=fmt(liked), bad=fmt(moaned))

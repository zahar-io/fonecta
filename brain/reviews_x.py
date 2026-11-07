"""Holiday-specific review signals (T403): which special day a review names, and whether it says closed,
open, or closed early at a given time. Only reviews published before the snapshot."""
import re, json
from collections import defaultdict
from datetime import datetime, timedelta
import features  # noqa: F401 (puts the kit on sys.path)
from baseline import cycle
LEX = [("uudenvuodenaatto", "NYE"), ("nyårsafton", "NYE"), ("nyttårsaften", "NYE"), ("new year's eve", "NYE"),
       ("uudenvuodenpäivä", "NEW_YEARS_DAY"), ("nyårsdag", "NEW_YEARS_DAY"), ("nyttårsdag", "NEW_YEARS_DAY"), ("new year's day", "NEW_YEARS_DAY"),
       ("aatonaatto", "DEC23"), ("lille julaften", "DEC23"), ("lillejulaften", "DEC23"), ("dan före dopparedan", "DEC23"), ("lilla julafton", "DEC23"),
       ("jouluaatto", "XMAS_EVE"), ("julafton", "XMAS_EVE"), ("julaften", "XMAS_EVE"), ("christmas eve", "XMAS_EVE"),
       ("andre juledag", "BOXING_DAY"), ("annandag jul", "BOXING_DAY"), ("tapaninpäivä", "BOXING_DAY"), ("boxing day", "BOXING_DAY"),
       ("joulupäivä", "XMAS_DAY"), ("juldag", "XMAS_DAY"), ("juledag", "XMAS_DAY"), ("christmas day", "XMAS_DAY"),
       ("välipäiv", "INTERDAY"), ("mellandag", "INTERDAY"), ("romjul", "INTERDAY"), ("between christmas", "INTERDAY"),
       ("loppiaisaatto", "EPIPHANY_EVE"), ("trettondagsafton", "EPIPHANY_EVE"), ("epiphany eve", "EPIPHANY_EVE"),
       ("loppiai", "EPIPHANY"), ("trettondedag", "EPIPHANY"), ("trettondag jul", "EPIPHANY"), ("epiphany", "EPIPHANY"),
       ("isänpäiv", "FATHERS_DAY"), ("fars dag", "FATHERS_DAY"), ("farsdag", "FATHERS_DAY"), ("father's day", "FATHERS_DAY"),
       ("black friday", "BLACK_FRIDAY"), ("itsenäisyyspäiv", "INDEPENDENCE_DAY"), ("independence day", "INDEPENDENCE_DAY"),
       ("lucia", "LUCIA"), ("tapahtumailta", "EVENT"), ("evenemang", "EVENT"), ("arrangement", "EVENT"), ("event", "EVENT"),
       ("lomaviiko", "SCHOOL_BREAK"), ("sportlov", "SCHOOL_BREAK"), ("vinterferie", "SCHOOL_BREAK"), ("school holiday", "SCHOOL_BREAK")]
EARLY = re.compile(r"(?:allerede|redan|jo klo|klo|already at)\s*(\d{1,2})(?:[.:](\d{2}))?")
OPEN = ("olitte auki", "olittekin auki", "hade öppet", "holdt åpent", "hadde åpent", "were open", "being open", "pelastitte", "att ni hade öppet")
CLOSED = ("kiinni", "stängt", "stengt", "closed", "ei ollut", "wasn't", "pimeänä", "suljetun", "stängd", "foran", "framför")

def parse(text):
    t = (text or "").lower()
    key = None
    for w, k in LEX:
        if w in t:
            key = k; break
    if not key:
        return None
    m = EARLY.search(t)
    if m and any(x in t for x in ("allerede", "redan", "jo kiinni", "suljettiin jo", "already", "jo klo")):
        h = int(m.group(1))
        if 5 <= h <= 23:
            return key, "early", h * 60
    if any(x in t for x in OPEN):
        return key, "open", None
    if any(x in t for x in CLOSED):
        return key, "closed", None
    return None

def build(reviews_path, snap):
    cutoff = datetime(snap.year, snap.month, snap.day).timestamp() * 1000
    out = defaultdict(list)  # (eid, key) -> [(cycle, kind, minutes)]
    for r in json.load(open(reviews_path, encoding="utf-8"))["response"]["reviews"]:
        if r["publisherDate"] >= cutoff:
            continue
        p = parse(r["content"])
        if not p:
            continue
        d = datetime.fromtimestamp(r["publisherDate"] / 1000).date() - timedelta(days=20)
        out[(r["locationId"], p[0])].append((cycle(d), p[1], p[2]))
    return out

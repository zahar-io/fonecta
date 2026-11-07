"""Customer messages in fi / sv / nb / en: the suggestion, the follow-ups and the decision-page strings.

One message per business bundles its upcoming dates. Every date says what Google shows now and why that is
wrong. Low confidence -> phrased as a question. A value line uses the business's own analytics."""
from __future__ import annotations

from datetime import date

from .hours import nice

LANGS = ("fi", "sv", "nb", "en")

WD_SHORT = {"fi": ["ma", "ti", "ke", "to", "pe", "la", "su"],
            "sv": ["mån", "tis", "ons", "tors", "fre", "lör", "sön"],
            "nb": ["man", "tir", "ons", "tor", "fre", "lør", "søn"],
            "en": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]}
WD_LONG = {"fi": ["maanantaina", "tiistaina", "keskiviikkona", "torstaina", "perjantaina", "lauantaina",
                  "sunnuntaina"],
           "sv": ["måndag", "tisdag", "onsdag", "torsdag", "fredag", "lördag", "söndag"],
           "nb": ["mandag", "tirsdag", "onsdag", "torsdag", "fredag", "lørdag", "søndag"],
           "en": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]}
MONTHS_EN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

DAY_NAMES = {
    "XMAS_EVE": ("Jouluaatto", "Julafton", "Julaften", "Christmas Eve"),
    "XMAS_DAY": ("Joulupäivä", "Juldagen", "Første juledag", "Christmas Day"),
    "BOXING_DAY": ("Tapaninpäivä", "Annandag jul", "Andre juledag", "Boxing Day"),
    "DEC23": ("Aatonaatto", "Dagen före julafton", "Lille julaften", "23 December"),
    "INTERDAY": ("Välipäivä", "Mellandag", "Romjulsdag", "Between the holidays"),
    "NYE": ("Uudenvuodenaatto", "Nyårsafton", "Nyttårsaften", "New Year's Eve"),
    "NEW_YEARS_DAY": ("Uudenvuodenpäivä", "Nyårsdagen", "Første nyttårsdag", "New Year's Day"),
    "EPIPHANY_EVE": ("Loppiaisaatto", "Trettondagsafton", "Helligtrekongersaften", "Epiphany Eve"),
    "EPIPHANY": ("Loppiainen", "Trettondedag jul", "Helligtrekongersdag", "Epiphany"),
    "INDEPENDENCE_DAY": ("Itsenäisyyspäivä", "Självständighetsdagen", "Uavhengighetsdagen", "Independence Day"),
    "FATHERS_DAY": ("Isänpäivä", "Fars dag", "Farsdag", "Father's Day"),
    "MOTHERS_DAY": ("Äitienpäivä", "Mors dag", "Morsdag", "Mother's Day"),
    "LUCIA": ("Lucian päivä", "Lucia", "Luciadagen", "St Lucy's Day"),
    "BLACK_FRIDAY": ("Black Friday", "Black Friday", "Black Friday", "Black Friday"),
    "ALL_SAINTS": ("Pyhäinpäivä", "Alla helgons dag", "Allehelgensdag", "All Saints' Day"),
    "SCHOOL_BREAK": ("Koulujen loma", "Skollov", "Skoleferie", "School holiday"),
    "EVENT": ("Tapahtumailta", "Evenemangskväll", "Arrangementskveld", "Event night"),
    "NATIONAL_DAY": ("Kansallispäivä", "Nationaldagen", "Nasjonaldagen", "National Day"),
}

T = {
    "fi": {
        "hi": "Hei {first}!", "closed": "kiinni", "open": "auki klo {h}",
        "single_day": "{day} on {wd} {dm}.",
        "regular": "tavalliset aukioloaikanne ({h})", "exception": "{h}",
        "why_LAST_YEAR": "Viime vuonna olitte {last}, mutta tälle vuodelle poikkeusaikoja ei ole lisätty, joten "
                         "Google näyttää nyt {shown}.",
        "why_SHOPPING_CENTRE": "{mall} on ilmoittanut tämän päivän aukioloajat ({mall_h}), mutta teille ei ole "
                               "lisätty poikkeusaikoja, joten Google näyttää nyt {shown}.",
        "why_PEERS": "{pct} % vastaavista yrityksistä alueellanne on tänä päivänä kiinni, eikä teille ole lisätty "
                     "poikkeusaikoja, joten Google näyttää nyt {shown}.",
        "why_PEER_HOURS": "Vastaavat yritykset alueellanne ovat tänä päivänä yleensä auki klo {peer}, ja Google "
                          "näyttää nyt {shown}.",
        "why_OWNER_EDIT": "Viimeksi kerroitte olevanne tänä päivänä {last}, mutta tälle vuodelle sitä ei ole vielä "
                          "lisätty, joten Google näyttää nyt {shown}.",
        "why_EARLIER": "Aiempina vuosina olitte {last}, mutta tälle vuodelle poikkeusaikoja ei ole lisätty, joten "
                       "Google näyttää nyt {shown}.",
        "why_PUBLISHER": "Googlen käyttäjät ilmoittivat viime kaudella aukioloajoiksenne {last}, mutta tälle "
                         "vuodelle poikkeusaikoja ei ole lisätty, joten Google näyttää nyt {shown}.",
        "why_MODEL": "Kaltaisenne yritykset ovat tänä päivänä yleensä kiinni, mutta Google näyttää nyt {shown}.",
        "b_EARLIER": "kuten aiempina vuosina", "b_PUBLISHER": "Googlen käyttäjien ilmoitus", "b_MODEL": "kaltaisenne yritykset ovat yleensä kiinni",
        "why_OTHER": "Google näyttää nyt {shown}.",
        "suggest": "Ehdotamme: {wd} {dm} {sug}", "adjusted": " (muokattu kuten viimeksi)",
        "ask": "Oletteko auki {wdl} {dm}? Paras arviomme: {sug}.",
        "multi": "{name} näkyy Googlessa väärillä aukioloajoilla {n} pyhäpäivänä. Ehdotamme:",
        "b_LAST_YEAR": "kuten viime vuonna", "b_SHOPPING_CENTRE": "kuten {mall}",
        "b_PEERS": "{pct} % vastaavista on kiinni", "b_PEER_HOURS": "vastaavat yritykset: {peer}",
        "b_OWNER_EDIT": "kuten kerroitte viimeksi", "b_OTHER": "",
        "b_now": "Google nyt: {s}", "b_ask": "oletteko auki? Arviomme: {sug}",
        "value": "Yrityksenne tiedot nähtiin Googlen haussa ja kartoilla {views} kertaa viimeisen 30 päivän "
                 "aikana. Oikeat aukioloajat pitävät teidät mukana ”auki nyt” -hauissa.",
        "buttons": ("Hyväksy", "Muokkaa", "Ei kiitos"),
        "link": "Hyväksy, muokkaa tai hylkää (ei kirjautumista): {url}",
        "sign": "– Fonecta Connect",
        "subject": "{name}: tarkistetaanko pyhien aukioloajat?",
        "done": "Valmista! Uudet aukioloajat on tallennettu:", "done_edit": "Valmista! Tallensimme antamanne ajat:",
        "live_on": "Näkyvissä: {list}.", "kept": "{n} päivä(ä) jätettiin ennalleen.",
        "perm_on": "Jatkossa hoidamme pyhäpäivät puolestanne ja ilmoitamme vain jälkikäteen.",
        "declined": "Selvä, emme muuta mitään. Google näyttää edelleen nykyiset aukioloaikanne. Kiitos tiedosta, "
                    "muistamme tämän ensi kerralla!",
        "edit_prompt": "Selvä! Aseta omat aikanne tästä (ei kirjautumista, vie 20 sekuntia): {url}",
        "auto": "Hei {first}! Kuten pyysitte, lisäsimme pyhäpäivien aukioloajat ({name}):",
        "undo": "Eikö mennyt oikein? Peru yhdellä napautuksella: {url}",
        "undone": "Peruttu. Aiemmat aukioloaikanne ovat taas voimassa.",
        "eta": ("min", "h", "pv", "pv"),
    },
    "sv": {
        "hi": "Hej {first}!", "closed": "stängt", "open": "öppet {h}",
        "single_day": "{day} infaller {wd} {dm}.",
        "regular": "era vanliga öppettider ({h})", "exception": "{h}",
        "why_LAST_YEAR": "Förra året hade ni {last}, men inga avvikande tider är inlagda i år, så Google visar nu "
                         "{shown}.",
        "why_SHOPPING_CENTRE": "{mall} har publicerat sina tider för dagen ({mall_h}), men inga avvikande tider är "
                               "inlagda för er, så Google visar nu {shown}.",
        "why_PEERS": "{pct} % av liknande företag i området har stängt den dagen, och inga avvikande tider är "
                     "inlagda för er, så Google visar nu {shown}.",
        "why_PEER_HOURS": "Liknande företag i området har oftast öppet {peer} den dagen, och Google visar nu "
                          "{shown}.",
        "why_OWNER_EDIT": "Förra gången sa ni att ni har {last} den dagen, men det är inte inlagt i år, så Google "
                          "visar nu {shown}.",
        "why_EARLIER": "Tidigare år hade ni {last}, men inga avvikande tider är inlagda i år, så Google visar nu "
                       "{shown}.",
        "why_PUBLISHER": "Googleanvändare rapporterade förra säsongen att ni hade {last}, men inga avvikande tider "
                         "är inlagda i år, så Google visar nu {shown}.",
        "why_MODEL": "Företag som ert brukar ha stängt den dagen, men Google visar nu {shown}.",
        "b_EARLIER": "som tidigare år", "b_PUBLISHER": "enligt Googleanvändare", "b_MODEL": "liknande företag brukar ha stängt",
        "why_OTHER": "Google visar nu {shown}.",
        "suggest": "Vi föreslår: {wd} {dm} {sug}", "adjusted": " (justerat som er senaste ändring)",
        "ask": "Har ni öppet {wdl} {dm}? Vårt bästa förslag: {sug}.",
        "multi": "Google kommer att visa fel öppettider för {name} {n} helgdagar. Vi föreslår:",
        "b_LAST_YEAR": "som förra året", "b_SHOPPING_CENTRE": "som {mall}",
        "b_PEERS": "{pct} % av liknande har stängt", "b_PEER_HOURS": "liknande företag: {peer}",
        "b_OWNER_EDIT": "som ni sa förra gången", "b_OTHER": "",
        "b_now": "Google nu: {s}", "b_ask": "har ni öppet? Vårt förslag: {sug}",
        "value": "Er profil visades {views} gånger i Googles sök och kartor de senaste 30 dagarna. Rätt "
                 "öppettider håller er kvar i sökningar på ”öppet nu”.",
        "buttons": ("Godkänn", "Ändra", "Nej tack"),
        "link": "Godkänn, ändra eller avböj (ingen inloggning): {url}",
        "sign": "– Fonecta Connect",
        "subject": "{name}: ska vi uppdatera helgtiderna?",
        "done": "Klart! De nya tiderna är sparade:", "done_edit": "Klart! Vi har sparat tiderna ni angav:",
        "live_on": "Syns på: {list}.", "kept": "{n} dag(ar) lämnades som vanligt.",
        "perm_on": "Från och med nu sköter vi helgdagarna åt er och meddelar bara i efterhand.",
        "declined": "Okej, vi ändrar ingenting. Google fortsätter att visa era nuvarande tider. Tack för beskedet, "
                    "vi kommer ihåg det till nästa gång!",
        "edit_prompt": "Absolut! Ställ in era egna tider här (ingen inloggning, tar 20 sekunder): {url}",
        "auto": "Hej {first}! Som ni bad om har vi lagt in helgtiderna för {name}:",
        "undo": "Blev det fel? Ångra med ett tryck: {url}",
        "undone": "Ångrat. Era tidigare tider gäller igen.",
        "eta": ("min", "tim", "dag", "dagar"),
    },
    "nb": {
        "hi": "Hei {first}!", "closed": "stengt", "open": "åpent {h}",
        "single_day": "{day} er {wd} {dm}.",
        "regular": "de vanlige åpningstidene deres ({h})", "exception": "{h}",
        "why_LAST_YEAR": "I fjor hadde dere {last}, men ingen avvikende åpningstider er lagt inn i år, så Google "
                         "viser nå {shown}.",
        "why_SHOPPING_CENTRE": "{mall} har publisert åpningstidene for dagen ({mall_h}), men ingen avvikende tider er "
                               "lagt inn for dere, så Google viser nå {shown}.",
        "why_PEERS": "{pct} % av lignende bedrifter i området har stengt den dagen, og ingen avvikende tider er "
                     "lagt inn for dere, så Google viser nå {shown}.",
        "why_PEER_HOURS": "Lignende bedrifter i området har som regel åpent {peer} den dagen, og Google viser nå "
                          "{shown}.",
        "why_OWNER_EDIT": "Sist sa dere at dere har {last} den dagen, men det er ikke lagt inn i år, så Google "
                          "viser nå {shown}.",
        "why_EARLIER": "Tidligere år hadde dere {last}, men ingen avvikende åpningstider er lagt inn i år, så "
                       "Google viser nå {shown}.",
        "why_PUBLISHER": "Google-brukere meldte forrige sesong at dere hadde {last}, men ingen avvikende tider er "
                         "lagt inn i år, så Google viser nå {shown}.",
        "why_MODEL": "Bedrifter som deres har som regel stengt den dagen, men Google viser nå {shown}.",
        "b_EARLIER": "som tidligere år", "b_PUBLISHER": "ifølge Google-brukere", "b_MODEL": "lignende bedrifter har som regel stengt",
        "why_OTHER": "Google viser nå {shown}.",
        "suggest": "Vi foreslår: {wd} {dm} {sug}", "adjusted": " (justert slik dere endret sist)",
        "ask": "Har dere åpent {wdl} {dm}? Vårt beste forslag: {sug}.",
        "multi": "Google vil vise feil åpningstider for {name} på {n} helligdager. Vi foreslår:",
        "b_LAST_YEAR": "som i fjor", "b_SHOPPING_CENTRE": "som {mall}",
        "b_PEERS": "{pct} % av lignende har stengt", "b_PEER_HOURS": "lignende bedrifter: {peer}",
        "b_OWNER_EDIT": "slik dere sa sist", "b_OTHER": "",
        "b_now": "Google nå: {s}", "b_ask": "har dere åpent? Vårt forslag: {sug}",
        "value": "Profilen deres ble vist {views} ganger i Googles søk og kart de siste 30 dagene. Riktige "
                 "åpningstider holder dere med i søk på «åpent nå».",
        "buttons": ("Godkjenn", "Endre", "Nei takk"),
        "link": "Godkjenn, endre eller avslå (uten innlogging): {url}",
        "sign": "– Fonecta Connect",
        "subject": "{name}: skal vi oppdatere åpningstidene i høytiden?",
        "done": "Ferdig! De nye åpningstidene er lagret:", "done_edit": "Ferdig! Vi har lagret tidene dere la inn:",
        "live_on": "Synlig på: {list}.", "kept": "{n} dag(er) ble latt være som vanlig.",
        "perm_on": "Fra nå av ordner vi helligdagene for dere og gir bare beskjed etterpå.",
        "declined": "Greit, vi endrer ingenting. Google viser fortsatt de nåværende tidene deres. Takk for "
                    "beskjed, vi husker det til neste gang!",
        "edit_prompt": "Selvsagt! Sett deres egne tider her (uten innlogging, tar 20 sekunder): {url}",
        "auto": "Hei {first}! Som dere ba om, har vi lagt inn helligdagstidene for {name}:",
        "undo": "Ble det feil? Angre med ett trykk: {url}",
        "undone": "Angret. De tidligere tidene deres gjelder igjen.",
        "eta": ("min", "t", "dag", "dager"),
    },
    "en": {
        "hi": "Hi {first}!", "closed": "closed", "open": "open {h}",
        "single_day": "{day} is on {wd} {dm}.",
        "regular": "your regular hours ({h})", "exception": "{h}",
        "why_LAST_YEAR": "Last year you were {last} that day, but no special hours have been added this year, so "
                         "Google now shows {shown}.",
        "why_SHOPPING_CENTRE": "{mall} has published its hours for that day ({mall_h}), but no special hours have "
                               "been added for you, so Google now shows {shown}.",
        "why_PEERS": "{pct}% of similar businesses nearby are closed that day, and no special hours have been "
                     "added for you, so Google now shows {shown}.",
        "why_PEER_HOURS": "Similar businesses nearby are usually open {peer} that day, and Google now shows "
                          "{shown}.",
        "why_OWNER_EDIT": "Last time you told us you're {last} that day, but it hasn't been added this year, so "
                          "Google now shows {shown}.",
        "why_EARLIER": "In earlier years you were {last} that day, but no special hours have been added this year, "
                       "so Google now shows {shown}.",
        "why_PUBLISHER": "Google users reported you were {last} that day last season, but no special hours have been "
                         "added this year, so Google now shows {shown}.",
        "why_MODEL": "Businesses like yours are usually closed that day, but Google now shows {shown}.",
        "b_EARLIER": "as in earlier years", "b_PUBLISHER": "as Google users reported", "b_MODEL": "businesses like yours are usually closed",
        "why_OTHER": "Google now shows {shown}.",
        "suggest": "We suggest: {wd} {dm} {sug}", "adjusted": " (adjusted like your last edit)",
        "ask": "Are you open on {wdl} {dm}? Our best guess: {sug}.",
        "multi": "Google will show the wrong hours for {name} on {n} holidays. We suggest:",
        "b_LAST_YEAR": "as last year", "b_SHOPPING_CENTRE": "same as {mall}",
        "b_PEERS": "{pct}% of similar businesses are closed", "b_PEER_HOURS": "similar businesses: {peer}",
        "b_OWNER_EDIT": "as you told us last time", "b_OTHER": "",
        "b_now": "Google now: {s}", "b_ask": "are you open? Our guess: {sug}",
        "value": "Your listing was seen {views} times on Google Search and Maps in the last 30 days. Correct "
                 "holiday hours keep you in “open now” results.",
        "buttons": ("Approve", "Edit", "No thanks"),
        "link": "Approve, edit or decline (no login): {url}",
        "sign": "– Fonecta Connect",
        "subject": "{name}: shall we update your holiday hours?",
        "done": "Done! Your new hours are saved:", "done_edit": "Done! We saved the hours you set:",
        "live_on": "Live on: {list}.", "kept": "{n} day(s) left as usual.",
        "perm_on": "From now on we'll handle public holidays for you and just let you know.",
        "declined": "OK, we won't change anything. Google keeps showing your current hours. Thanks for letting "
                    "us know, we'll remember it next time!",
        "edit_prompt": "Sure! Set your own hours here (no login, takes 20 seconds): {url}",
        "auto": "Hi {first}! As you asked, we've added the holiday hours for {name}:",
        "undo": "Not right? Undo with one tap: {url}",
        "undone": "Undone. Your previous hours are back.",
        "eta": ("min", "h", "day", "days"),
    },
}

# Decision-page strings
P = {
    "fi": {"title": "Pyhien aukioloajat", "now": "Google näyttää nyt", "sug": "Ehdotus", "why": "Miksi",
           "approve": "Hyväksy", "edit": "Muokkaa", "decline": "Ei kiitos", "closed": "Kiinni",
           "as_usual": "Kuten tavallisesti", "save": "Tallenna", "cancel": "Takaisin",
           "perm": "Hoida pyhäpäivät puolestani jatkossa (ilmoitatte jälkikäteen)",
           "why_no": "Kertoisitko miksi? (vapaaehtoinen)", "send_no": "Lähetä",
           "r_open_as_usual": "Olemme auki normaalisti", "r_different_hours": "Eri aukioloajat",
           "r_not_this_year": "Ei tänä vuonna", "q": "Tarkista", "expired": "Linkki on vanhentunut.",
           "views": "näyttökertaa 30 päivässä", "no_login": "Ei kirjautumista. Sinulla on aina viimeinen sana.",
           "undo": "Peru muutos", "decided": "Tämä on jo käsitelty."},
    "sv": {"title": "Öppettider under helgerna", "now": "Google visar nu", "sug": "Förslag", "why": "Varför",
           "approve": "Godkänn", "edit": "Ändra", "decline": "Nej tack", "closed": "Stängt",
           "as_usual": "Som vanligt", "save": "Spara", "cancel": "Tillbaka",
           "perm": "Sköt helgdagarna åt mig från och med nu (meddela i efterhand)",
           "why_no": "Vill du berätta varför? (frivilligt)", "send_no": "Skicka",
           "r_open_as_usual": "Vi har öppet som vanligt", "r_different_hours": "Andra tider",
           "r_not_this_year": "Inte i år", "q": "Kontrollera", "expired": "Länken har gått ut.",
           "views": "visningar på 30 dagar", "no_login": "Ingen inloggning. Du har alltid sista ordet.",
           "undo": "Ångra ändringen", "decided": "Det här är redan klart."},
    "nb": {"title": "Åpningstider i høytiden", "now": "Google viser nå", "sug": "Forslag", "why": "Hvorfor",
           "approve": "Godkjenn", "edit": "Endre", "decline": "Nei takk", "closed": "Stengt",
           "as_usual": "Som vanlig", "save": "Lagre", "cancel": "Tilbake",
           "perm": "Ordne helligdagene for meg fra nå av (gi beskjed etterpå)",
           "why_no": "Vil du si hvorfor? (valgfritt)", "send_no": "Send",
           "r_open_as_usual": "Vi har åpent som vanlig", "r_different_hours": "Andre tider",
           "r_not_this_year": "Ikke i år", "q": "Sjekk", "expired": "Lenken har utløpt.",
           "views": "visninger på 30 dager", "no_login": "Ingen innlogging. Du har alltid siste ord.",
           "undo": "Angre endringen", "decided": "Dette er allerede ordnet."},
    "en": {"title": "Your holiday hours", "now": "Google shows now", "sug": "Suggestion", "why": "Why",
           "approve": "Approve", "edit": "Edit", "decline": "No thanks", "closed": "Closed",
           "as_usual": "As usual", "save": "Save", "cancel": "Back",
           "perm": "Handle public holidays for me from now on (just let me know)",
           "why_no": "Tell us why? (optional)", "send_no": "Send",
           "r_open_as_usual": "We're open as usual", "r_different_hours": "Different hours",
           "r_not_this_year": "Not this year", "q": "Please check", "expired": "This link has expired.",
           "views": "views in 30 days", "no_login": "No login. You always have the last word.",
           "undo": "Undo the change", "decided": "This one is already done."},
}


def lang_of(lang: str) -> str:
    return lang if lang in LANGS else "en"


def day_name(item: dict, lang: str, event_name: str | None = None) -> str:
    if item["day_key"] == "EVENT" and event_name:
        return event_name
    names = DAY_NAMES.get(item["day_key"])
    return names[LANGS.index(lang)] if names else item.get("name_en", item["day_key"])


def dm(d: date, lang: str) -> str:
    if lang == "en":
        return f"{d.day} {MONTHS_EN[d.month - 1]}"
    if lang == "sv":
        return f"{d.day}/{d.month}"
    return f"{d.day}.{d.month}."


def hrs(h: str, lang: str) -> str:
    return nice(h, lang, T[lang]["closed"])


def state(h: str, lang: str) -> str:
    return T[lang]["closed"] if h == "closed" else T[lang]["open"].format(h=nice(h, lang))


def fmt_int(n: int, lang: str) -> str:
    s = f"{n:,}"
    return s if lang == "en" else s.replace(",", " ")


def shown_phrase(item: dict, lang: str) -> str:
    s = item["shown_hours"]
    if item.get("shown_is_exception"):
        return T[lang]["exception"].format(h=hrs(s, lang))
    return T[lang]["regular"].format(h=hrs(s, lang))


def _basis_key(item):
    b = item.get("basis")
    return b if b in ("LAST_YEAR", "SHOPPING_CENTRE", "PEERS", "PEER_HOURS", "OWNER_EDIT", "EARLIER", "PUBLISHER",
                      "MODEL") else "OTHER"


def _fill(item, lang):
    ev = item.get("evidence") or {}
    return {"last": state(ev.get("last_hours") or item["hours"], lang)
            if _basis_key(item) in ("LAST_YEAR", "EARLIER", "PUBLISHER")
            else state(item["hours"], lang),
            "mall": ev.get("mall", ""), "mall_h": hrs(ev.get("mall_hours") or item["hours"], lang),
            "pct": round(float(ev.get("peer_closed_share") or 0) * 100),
            "peer": nice(ev.get("peer_hours") or item["hours"], lang),
            "shown": shown_phrase(item, lang)}


def why_sentence(item: dict, lang: str) -> str:
    k = _basis_key(item)
    t = T[lang]
    if k == "OTHER" and item.get("reasons"):
        return f"{item['reasons'][0]} " + t["why_OTHER"].format(shown=shown_phrase(item, lang))
    return t["why_" + k].format(**_fill(item, lang))


def bullet(item: dict, lang: str, event_name=None) -> str:
    t = T[lang]
    d = date.fromisoformat(item["date"])
    head = f"• {day_name(item, lang, event_name)}, {WD_SHORT[lang][d.weekday()]} {dm(d, lang)}:"
    now = t["b_now"].format(s=hrs(item["shown_hours"], lang))
    if item.get("mode") == "ask":
        return f"{head} {t['b_ask'].format(sug=hrs(item['hours'], lang))} ({now})"
    k = _basis_key(item)
    why = t["b_" + k].format(**_fill(item, lang)) if k != "OTHER" else ""
    adj = t["adjusted"].strip() if item.get("adjusted") else ""
    extra = "; ".join(x for x in (why, adj.strip(" ()"), now) if x)
    return f"{head} {hrs(item['hours'], lang)} ({extra})"


def eta_text(sec: int, lang: str) -> str:
    u = T[lang]["eta"]
    if sec < 3600:
        return f"~{max(1, sec // 60)} {u[0]}"
    if sec < 86400:
        return f"~{sec // 3600} {u[1]}"
    n = sec // 86400
    return f"~{n} {u[2] if n == 1 else u[3]}"


def short_publisher(name: str) -> str:
    return {"Google (Search & Maps)": "Google", "Finder.fi / Fonecta.fi": "Finder.fi",
            "AI assistants (via Bing/Apple data)": "AI assistants", "Waze (via Google)": "Waze"}.get(name, name)


def live_list(listings: list, lang: str, limit: int = 5) -> str:
    live = sorted([l for l in listings if l.get("status") == "LIVE"], key=lambda l: l["typicalUpdateSpeedSeconds"])
    return ", ".join(f"{short_publisher(l['publisherName'])} {eta_text(l['typicalUpdateSpeedSeconds'], lang)}"
                     for l in live[:limit])


# ------------------------------------------------------------------ the suggestion message
def compose(ctx: dict, items: list, url: str) -> dict:
    """ctx: {lang, first, name, views (int|None), events {event_id: name}}; items: SUGGEST items with mode.
    Returns {lang, subject, body, buttons, text (full plain text incl. link and [buttons])}."""
    lang = lang_of(ctx.get("lang"))
    t = T[lang]
    ev_names = ctx.get("events") or {}
    lines = [t["hi"].format(first=ctx["first"])]
    items = sorted(items, key=lambda i: i["date"])
    if len(items) == 1:
        it = items[0]
        d = date.fromisoformat(it["date"])
        if it.get("mode") == "ask":
            lines.append(why_sentence(it, lang))
            lines.append(t["ask"].format(wdl=WD_LONG[lang][d.weekday()], dm=dm(d, lang), sug=hrs(it["hours"], lang)))
        else:
            lines.append(t["single_day"].format(day=day_name(it, lang, ev_names.get(it.get("event_id"))),
                                                wd=WD_LONG[lang][d.weekday()], dm=dm(d, lang))
                         + " " + why_sentence(it, lang))
            lines.append(t["suggest"].format(wd=WD_SHORT[lang][d.weekday()], dm=dm(d, lang),
                                             sug=hrs(it["hours"], lang))
                         + (t["adjusted"] if it.get("adjusted") else ""))
    else:
        lines.append(t["multi"].format(name=ctx["name"], n=len(items)))
        lines.extend(bullet(i, lang, ev_names.get(i.get("event_id"))) for i in items)
    body = "\n".join(lines[:1] + [""] + lines[1:])
    buttons = list(t["buttons"])
    text = body + "\n" + " ".join(f"[{b}]" for b in buttons) + "\n" + t["link"].format(url=url) + "\n" + t["sign"]
    return {"lang": lang, "subject": t["subject"].format(name=ctx["name"]), "body": body, "buttons": buttons,
            "link_line": t["link"].format(url=url), "text": text, "wa": wa_format(ctx, items, url)}


# ------------------------------------------------------------------ WhatsApp formatting (*bold* _italic_ ~strike~)
WA_HEAD = {"fi": "Pyhäpäivien aukioloajat", "sv": "Öppettider under helgerna", "nb": "Åpningstider i høytiden",
           "en": "Holiday hours check"}


def wa_format(ctx: dict, items: list, url: str) -> dict:
    """WhatsApp-native version: a header, Google's wrong hours struck out next to ours in bold, the reason, and
    buttons (added by the channel). One date per message is the default: each date is its own decision."""
    lang = lang_of(ctx.get("lang"))
    t = T[lang]
    ev_names = ctx.get("events") or {}
    items = sorted(items, key=lambda i: i["date"])
    lines = [t["hi"].format(first=ctx["first"]), ""]

    def block(it, short_why):
        d = date.fromisoformat(it["date"])
        k = _basis_key(it)
        why = ""
        if short_why:
            why = t["b_ask"].format(sug=hrs(it["hours"], lang)) if it.get("mode") == "ask" else (
                t["b_" + k].format(**_fill(it, lang)) if k != "OTHER" else "")
        return [f"*{day_name(it, lang, ev_names.get(it.get('event_id')))}, {WD_SHORT[lang][d.weekday()]} {dm(d, lang)}*",
                f"~{hrs(it['shown_hours'], lang)}~ → *{hrs(it['hours'], lang)}*" + (f"  _{why}_" if why else "")]

    if len(items) == 1:
        it = items[0]
        tail = ["", why_sentence(it, lang)]
        if it.get("mode") == "ask":
            d = date.fromisoformat(it["date"])
            tail += ["", t["ask"].format(wdl=WD_LONG[lang][d.weekday()], dm=dm(d, lang), sug=hrs(it["hours"], lang))]
        short = "\n".join(lines + tail[1:])  # used when the header image already shows the date and hours
        lines += block(it, False) + tail
        return {"header": WA_HEAD[lang], "body": "\n".join(lines), "body_with_card": short, "footer": "Connect · demo"}
    else:
        lines.append(t["multi"].format(name=f"*{ctx['name']}*", n=len(items)))
        for it in items:
            lines += [""] + block(it, True)
    return {"header": WA_HEAD[lang], "body": "\n".join(lines), "footer": "Connect · demo"}


# ------------------------------------------------------------------ follow-ups
def _applied_lines(applied: list, lang: str, ev_names=None) -> list:
    out = []
    for a in sorted(applied, key=lambda x: x["date"]):
        d = date.fromisoformat(a["date"])
        out.append(f"• {day_name(a, lang, (ev_names or {}).get(a.get('event_id')))}, "
                   f"{WD_SHORT[lang][d.weekday()]} {dm(d, lang)}: {hrs(a['final_hours'], lang)}")
    return out


def confirmation(ctx: dict, applied: list, listings: list, edited: bool, kept: int = 0,
                 permission: bool = False) -> str:
    lang = lang_of(ctx.get("lang"))
    t = T[lang]
    lines = [t["done_edit"] if edited else t["done"]] + _applied_lines(applied, lang, ctx.get("events"))
    if kept:
        lines.append(t["kept"].format(n=kept))
    lines.append(t["live_on"].format(list=live_list(listings, lang)))
    if permission:
        lines.append(t["perm_on"])
    if ctx.get("views"):
        lines += ["", t["value"].format(views=fmt_int(ctx["views"], lang))]
    return "\n".join(lines)


def declined(ctx: dict) -> str:
    return T[lang_of(ctx.get("lang"))]["declined"]


def edit_prompt(ctx: dict, url: str) -> str:
    return T[lang_of(ctx.get("lang"))]["edit_prompt"].format(url=url)


def auto_applied(ctx: dict, applied: list, listings: list, undo_url: str) -> str:
    lang = lang_of(ctx.get("lang"))
    t = T[lang]
    lines = [t["auto"].format(first=ctx["first"], name=ctx["name"])] + _applied_lines(applied, lang,
                                                                                       ctx.get("events"))
    lines.append(t["live_on"].format(list=live_list(listings, lang)))
    lines.append(t["undo"].format(url=undo_url))
    lines.append(t["sign"])
    return "\n".join(lines)


def undone(ctx: dict) -> str:
    return T[lang_of(ctx.get("lang"))]["undone"]

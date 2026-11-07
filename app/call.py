"""Urgent escalation by voice call: the change is due soon and nobody has answered.

Rule (Engine.urgent_call): a sent suggestion whose first date is within URGENT_WITHIN_H (default 48 h) and that has had
no answer for URGENT_AFTER_H (default 4 h) -> one call. The call explains the suggestion and points to the message
already on the phone: the owner still decides with a tap. A call never approves anything by itself.

Channel: WhatsApp only. A real WhatsApp voice call (Cloud API Calling, app/wa_call.py) that speaks the message,
after the owner granted call permission. If the call can't be placed, the same words go as a WhatsApp voice note.
"""
from __future__ import annotations

import os

SCRIPT = {
    "fi": "Hei {first}, täällä Fonecta Connectin avustaja, olen tekoäly. Soitan, koska {name} näkyy Googlessa väärillä "
          "aukioloajoilla jo {when}: {what}. Lähetimme ehdotuksen viestinä. Hyväksytkö sen? Voit napauttaa viestissä "
          "Hyväksy, tai kerro minulle, niin merkitsen sen.",
    "sv": "Hej {first}, det här är Fonecta Connects assistent, jag är en AI. Jag ringer eftersom {name} visar fel "
          "öppettider på Google redan {when}: {what}. Vi har skickat ett förslag som meddelande. Godkänner du det?",
    "nb": "Hei {first}, dette er Fonecta Connects assistent, jeg er en KI. Jeg ringer fordi {name} viser feil "
          "åpningstider på Google allerede {when}: {what}. Vi har sendt et forslag som melding. Godkjenner du det?",
    "en": "Hi {first}, this is Fonecta Connect's assistant, I'm an AI. I'm getting in touch because {name} will show the wrong "
          "hours on Google as soon as {when}: {what}. We've sent you a suggestion by message: tap Approve if it looks right.",
}


def spoken_time(t: str) -> str:
    """'16:00' -> '4 pm', '07:30' -> '7:30 am' (how people say it on the phone)."""
    h, m = int(t[:2]), int(t[3:5])
    ap = "am" if h < 12 else "pm"
    h12 = h % 12 or 12
    return f"{h12}{':%02d' % m if m else ''} {ap}"


def spoken_hours(h: str) -> str:
    if h == "closed":
        return "closed"
    a, b = h.split(",")[0].split("-")[0], h.split(",")[-1].split("-")[-1]
    return f"open from {spoken_time(a)} to {spoken_time(b)}"


SHORT_EN = ("Hi {first}, it's Connect, your AI assistant. On {when}, Google shows {name} as {shown}, "
            "but we think you're {sug}. I've sent you a WhatsApp message. Tap Approve if that's right. Thanks!")


def script(lang: str, **kw) -> str:
    if lang == "en" and "shown" in kw:
        return SHORT_EN.format(**kw)
    return SCRIPT.get(lang, SCRIPT["en"]).format(**kw)


def place(text: str, why: str, to: str | None = None) -> dict:
    """`why` is kept for the audit trail by the caller; the call itself only needs the words and the number."""
    to = os.environ.get("WA_TO") or to or ""
    if not (os.environ.get("WA_TOKEN") and os.environ.get("WA_PHONE_NUMBER_ID") and to):
        return {"ok": False, "transport": "wa-call", "dialled": False, "error": "WhatsApp not configured"}
    from . import wa_call
    r = wa_call.start_call(to, text)
    if r.get("ok"):
        return {"ok": True, "transport": "wa-call", "dialled": True, "call_id": r.get("call_id")}
    from .channels import WhatsAppCloudChannel
    v = WhatsAppCloudChannel().send_voice(to, text)
    return {"ok": v.get("ok"), "transport": "wa-voice (call failed)", "dialled": False, "error": str(r.get("error"))[:300]}

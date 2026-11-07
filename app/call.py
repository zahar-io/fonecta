"""Urgent escalation by voice call: the change is due soon and nobody has answered.

Rule (Engine.urgent_call): a sent suggestion whose first date is within URGENT_WITHIN_H (default 48 h) and that has had
no answer for URGENT_AFTER_H (default 4 h) -> one call. The call explains the suggestion and points to the message
already on the phone: the owner still decides with a tap. A call never approves anything by itself.

Transports
* zahar-caller: Flovr's existing voice agent (a separate, pre-existing service, not part of this repo) over its local
  socket ~/.zahar/caller.sock. It only calls allowlisted numbers, so in the demo the "owner" is a team member's phone.
  Enabled with CALL_TRANSPORT=zahar-caller and CALL_TO_ID=<the callee id the service knows>.
* preview (default): nothing is dialled; the console shows the call script.
"""
from __future__ import annotations

import json
import os
import socket

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
    mode = os.environ.get("CALL_TRANSPORT", "preview")
    if mode == "wa-call":  # a real WhatsApp voice call that speaks the message; falls back to a voice note
        from . import wa_call
        r = wa_call.start_call(os.environ.get("WA_TO") or to or "", text)
        if r.get("ok"):
            return {"ok": True, "transport": "wa-call", "dialled": True, "call_id": r.get("call_id")}
        from .channels import WhatsAppCloudChannel
        v = WhatsAppCloudChannel().send_voice(to, text)
        return {"ok": v.get("ok"), "transport": "wa-voice (call failed)", "dialled": False,
                "error": str(r.get("error"))[:300]}
    if mode == "wa-voice":  # WhatsApp voice message (spoken nudge) on the same chat as the suggestion
        from .channels import WhatsAppCloudChannel
        r = WhatsAppCloudChannel().send_voice(to, text)
        return {"ok": r.get("ok"), "transport": "wa-voice", "dialled": False, "error": r.get("error")}
    if mode != "zahar-caller":
        return {"ok": True, "transport": "preview", "dialled": False, "script": text}
    sock = os.path.expanduser(os.environ.get("CALL_SOCKET", "~/.zahar/caller.sock"))
    to_id = int(os.environ.get("CALL_TO_ID", "0") or 0)
    if not to_id:
        return {"ok": False, "transport": "zahar-caller", "error": "CALL_TO_ID not set"}
    req = {"op": "call", "to_id": to_id, "urgent": True, "manual": True, "trigger": "connect-suggests",
           "requested_by": "connect-suggests demo", "why": why, "speech": text}
    try:
        with socket.socket(socket.AF_UNIX) as s:
            s.settimeout(float(os.environ.get("CALL_TIMEOUT", "600")))
            s.connect(sock)
            s.sendall((json.dumps(req) + "\n").encode())
            buf = b""
            while not buf.endswith(b"\n"):
                chunk = s.recv(65536)
                if not chunk:
                    break
                buf += chunk
        res = json.loads(buf or b"{}")
        return {"ok": bool(res.get("ok", True)), "transport": "zahar-caller", "dialled": True,
                "outcome": res.get("outcome"), "duration_s": res.get("duration_s"), "error": res.get("error")}
    except OSError as ex:
        return {"ok": False, "transport": "zahar-caller", "error": str(ex)}

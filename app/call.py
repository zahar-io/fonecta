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
    "en": "Hi {first}, this is Fonecta Connect's assistant, I'm an AI. I'm calling because {name} will show the wrong "
          "hours on Google as soon as {when}: {what}. We've sent you a suggestion by message. Do you approve it?",
}


def script(lang: str, **kw) -> str:
    return SCRIPT.get(lang, SCRIPT["en"]).format(**kw)


def place(text: str, why: str) -> dict:
    mode = os.environ.get("CALL_TRANSPORT", "preview")
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

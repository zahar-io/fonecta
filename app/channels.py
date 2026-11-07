"""Channels: how a composed message reaches the owner.

* WhatsAppCloudChannel - Meta WhatsApp Cloud API, interactive message with 3 reply buttons
  (Approve / Edit / No thanks). Enabled only when WA_PHONE_NUMBER_ID and WA_TOKEN are set.
  Optional WA_TO overrides the recipient (the CRM phone numbers are fake; use a verified test phone).
* PreviewChannel - nothing leaves the machine: the console renders a WhatsApp-style phone mock
  ("Mock preview"), an SMS and an email preview.
The access token is read from the environment at send time and never logged, printed or stored."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

GRAPH = "https://graph.facebook.com/v21.0"


def wa_configured() -> bool:
    return bool(os.environ.get("WA_PHONE_NUMBER_ID") and os.environ.get("WA_TOKEN"))


class Channel:
    name = "base"
    real = False

    def send_suggestion(self, to: str, msg: dict, button_ids: list) -> dict:
        raise NotImplementedError

    def send_text(self, to: str, text: str) -> dict:
        raise NotImplementedError


class PreviewChannel(Channel):
    """Records what would be sent; the console renders it."""
    name = "preview"

    def __init__(self, kind: str = "WHATSAPP"):
        self.kind = kind

    def send_suggestion(self, to, msg, button_ids):
        return {"ok": True, "channel": f"preview:{self.kind}", "delivered": False,
                "note": "Mock preview: nothing was sent outside this machine."}

    def send_text(self, to, text):
        return {"ok": True, "channel": f"preview:{self.kind}", "delivered": False}


class WhatsAppCloudChannel(Channel):
    name = "whatsapp"
    real = True

    def __init__(self, transport=None):
        self.phone_id = os.environ.get("WA_PHONE_NUMBER_ID", "")
        self._transport = transport or self._post

    @staticmethod
    def _post(url, payload):
        req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST",
                                     headers={"Authorization": "Bearer " + os.environ.get("WA_TOKEN", ""),
                                              "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:  # error bodies from Graph never echo the token
            return {"error": {"code": e.code, "message": e.read().decode()[:300]}}
        except (urllib.error.URLError, OSError) as e:
            return {"error": {"message": str(e)}}

    @staticmethod
    def recipient(to: str) -> str:
        """Demo safety: CRM numbers are fake, so everything goes to WA_TO, except numbers listed in WA_ALLOW
        (e.g. the backup approver's real phone)."""
        allow = {x.strip().replace("+", "") for x in os.environ.get("WA_ALLOW", "").split(",") if x.strip()}
        t = (to or "").replace("+", "").replace(" ", "")
        if t and t in allow:
            return t
        return (os.environ.get("WA_TO") or to or "").replace("+", "").replace(" ", "")

    @staticmethod
    def interactive_payload(to: str, msg: dict, button_ids: list) -> dict:
        wa = msg.get("wa")
        if wa and len(wa["body"]) <= 1024:  # WhatsApp-native formatting with a header and footer
            return {"messaging_product": "whatsapp", "recipient_type": "individual", "to": to, "type": "interactive",
                    "interactive": {"type": "button", "header": {"type": "text", "text": wa["header"][:60]},
                                    "body": {"text": wa["body"]},
                                    "action": {"buttons": [{"type": "reply", "reply": {"id": bid, "title": title[:20]}}
                                                           for bid, title in list(zip(button_ids, msg["buttons"]))[:3]]}}}
        body = msg["body"] + "\n\n" + msg["link_line"]
        if len(body) > 1024:  # WhatsApp interactive body limit
            body = msg["body"][: 1024 - len(msg["link_line"]) - 4].rstrip() + "…\n\n" + msg["link_line"]
        return {"messaging_product": "whatsapp", "recipient_type": "individual", "to": to, "type": "interactive",
                "interactive": {"type": "button", "body": {"text": body},
                                "action": {"buttons": [{"type": "reply", "reply": {"id": bid, "title": title[:20]}}
                                                       for bid, title in list(zip(button_ids, msg["buttons"]))[:3]]}}}

    @staticmethod
    def template_payload(to: str, msg: dict, button_ids: list) -> dict:
        """Business-initiated (outside the 24 h window) needs a Meta-approved template; see docs/WHATSAPP.md.
        Template body: {{1}} = the suggestion text, quick-reply buttons carry our ids as payloads."""
        name, lang = os.environ["WA_TEMPLATE"], os.environ.get("WA_TEMPLATE_LANG", "fi")
        return {"messaging_product": "whatsapp", "to": to, "type": "template",
                "template": {"name": name, "language": {"code": lang},
                             "components": [{"type": "body", "parameters": [{"type": "text", "text": msg["body"][:900]}]}]
                             + [{"type": "button", "sub_type": "quick_reply", "index": str(i),
                                 "parameters": [{"type": "payload", "payload": bid}]} for i, bid in enumerate(button_ids[:3])]}}

    def upload_image(self, path: str, mime: str = "image/png", fname: str = "card.png") -> str | None:
        """POST /{phone_id}/media (multipart) -> media id, or None."""
        import uuid as _u
        bnd = "----flovr" + _u.uuid4().hex
        data = open(path, "rb").read()
        body = (f"--{bnd}\r\nContent-Disposition: form-data; name=\"messaging_product\"\r\n\r\nwhatsapp\r\n"
                f"--{bnd}\r\nContent-Disposition: form-data; name=\"type\"\r\n\r\n{mime}\r\n"
                f"--{bnd}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{fname}\"\r\n"
                f"Content-Type: {mime}\r\n\r\n").encode() + data + f"\r\n--{bnd}--\r\n".encode()
        req = urllib.request.Request(f"{GRAPH}/{self.phone_id}/media", data=body, method="POST",
                                     headers={"Authorization": "Bearer " + os.environ.get("WA_TOKEN", ""),
                                              "Content-Type": f"multipart/form-data; boundary={bnd}"})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.loads(r.read().decode()).get("id")
        except (urllib.error.URLError, OSError, ValueError):
            return None

    def send_suggestion(self, to, msg, button_ids):
        if not wa_configured():
            return {"ok": False, "channel": "whatsapp", "error": "WhatsApp not configured"}
        build = self.template_payload if os.environ.get("WA_TEMPLATE") else self.interactive_payload
        payload = build(self.recipient(to), msg, button_ids)
        img = (msg.get("wa") or {}).get("image")
        if img and payload.get("type") == "interactive" and os.environ.get("WA_CARDS", "1") == "1":
            mid = self.upload_image(img)
            if mid:
                payload["interactive"]["header"] = {"type": "image", "image": {"id": mid}}
                if (msg.get("wa") or {}).get("body_with_card"):
                    payload["interactive"]["body"]["text"] = msg["wa"]["body_with_card"]
        r = self._transport(f"{GRAPH}/{self.phone_id}/messages", payload)
        return {"ok": "error" not in r, "channel": "whatsapp", "delivered": "error" not in r,
                "provider_id": ((r.get("messages") or [{}])[0]).get("id"), "error": r.get("error")}

    def send_voice(self, to, text: str, voice: str = "Samantha") -> dict:
        """Spoken nudge as a WhatsApp voice message: macOS TTS -> ogg/opus -> media upload -> audio message."""
        import subprocess
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            aiff, ogg = os.path.join(d, "v.aiff"), os.path.join(d, "v.ogg")
            try:
                subprocess.run(["say", "-v", voice, "-o", aiff, text], check=True, timeout=60)
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", aiff, "-c:a", "libopus", "-b:a", "32k", ogg],
                               check=True, timeout=60)
            except (OSError, subprocess.SubprocessError) as ex:
                return {"ok": False, "channel": "whatsapp", "error": str(ex)[:120]}
            mid = self.upload_image(ogg, "audio/ogg", "nudge.ogg")
        if not mid:
            return {"ok": False, "channel": "whatsapp", "error": "audio upload failed"}
        r = self._transport(f"{GRAPH}/{self.phone_id}/messages",
                            {"messaging_product": "whatsapp", "to": self.recipient(to), "type": "audio",
                             "audio": {"id": mid}})
        return {"ok": "error" not in r, "channel": "whatsapp", "error": r.get("error")}

    def send_buttons(self, to, text, buttons):
        """buttons: [(id, title)] up to 3."""
        if not wa_configured():
            return {"ok": False, "channel": "whatsapp", "error": "WhatsApp not configured"}
        r = self._transport(f"{GRAPH}/{self.phone_id}/messages",
                            {"messaging_product": "whatsapp", "to": self.recipient(to), "type": "interactive",
                             "interactive": {"type": "button", "body": {"text": text[:1024]},
                                             "action": {"buttons": [{"type": "reply", "reply": {"id": i, "title": t[:20]}}
                                                                    for i, t in buttons[:3]]}}})
        return {"ok": "error" not in r, "channel": "whatsapp", "error": r.get("error")}

    def send_text(self, to, text):
        if not wa_configured():
            return {"ok": False, "channel": "whatsapp", "error": "WhatsApp not configured"}
        r = self._transport(f"{GRAPH}/{self.phone_id}/messages",
                            {"messaging_product": "whatsapp", "to": self.recipient(to), "type": "text",
                             "text": {"preview_url": True, "body": text[:4096]}})
        return {"ok": "error" not in r, "channel": "whatsapp", "error": r.get("error")}


def parse_webhook(payload: dict) -> list:
    """WhatsApp webhook -> [(from, button_id)] for interactive button replies (also legacy 'button' type)."""
    out = []
    for entry in payload.get("entry", []) or []:
        for ch in entry.get("changes", []) or []:
            for m in (ch.get("value") or {}).get("messages", []) or []:
                if m.get("type") == "interactive" and (m.get("interactive") or {}).get("type") == "button_reply":
                    out.append((m.get("from"), m["interactive"]["button_reply"].get("id")))
                elif m.get("type") == "button":
                    out.append((m.get("from"), (m.get("button") or {}).get("payload")))
    return out


def parse_texts(payload: dict) -> list:
    """WhatsApp webhook -> [(from, text)] for typed text messages."""
    out = []
    for entry in payload.get("entry", []) or []:
        for ch in entry.get("changes", []) or []:
            for m in (ch.get("value") or {}).get("messages", []) or []:
                if m.get("type") == "text":
                    out.append((m.get("from"), (m.get("text") or {}).get("body", "")))
    return out


def parse_audio(payload: dict) -> list:
    """WhatsApp webhook -> [(from, media_id)] for voice notes / audio."""
    out = []
    for entry in payload.get("entry", []) or []:
        for ch in entry.get("changes", []) or []:
            for m in (ch.get("value") or {}).get("messages", []) or []:
                if m.get("type") == "audio" and (m.get("audio") or {}).get("id"):
                    out.append((m.get("from"), m["audio"]["id"]))
    return out


def channel_for(preferred: str, force_preview: bool = False) -> Channel:
    """Preferred channel WhatsApp + configured -> real WhatsApp; everything else -> preview of that channel."""
    if not force_preview and preferred == "WHATSAPP" and wa_configured():
        return WhatsAppCloudChannel()
    return PreviewChannel(preferred or "SMS")

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
        return (os.environ.get("WA_TO") or to or "").replace("+", "").replace(" ", "")

    @staticmethod
    def interactive_payload(to: str, msg: dict, button_ids: list) -> dict:
        wa = msg.get("wa")
        if wa and len(wa["body"]) <= 1024:  # WhatsApp-native formatting with a header and footer
            return {"messaging_product": "whatsapp", "recipient_type": "individual", "to": to, "type": "interactive",
                    "interactive": {"type": "button", "header": {"type": "text", "text": wa["header"][:60]},
                                    "body": {"text": wa["body"]}, "footer": {"text": wa["footer"][:60]},
                                    "action": {"buttons": [{"type": "reply", "reply": {"id": bid, "title": title[:20]}}
                                                           for bid, title in list(zip(button_ids, msg["buttons"]))[:3]]}}}
        body = msg["body"] + "\n\n" + msg["link_line"]
        if len(body) > 1024:  # WhatsApp interactive body limit
            body = msg["body"][: 1024 - len(msg["link_line"]) - 4].rstrip() + "…\n\n" + msg["link_line"]
        return {"messaging_product": "whatsapp", "recipient_type": "individual", "to": to, "type": "interactive",
                "interactive": {"type": "button", "body": {"text": body},
                                "footer": {"text": "Fonecta Connect"},
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

    def send_suggestion(self, to, msg, button_ids):
        if not wa_configured():
            return {"ok": False, "channel": "whatsapp", "error": "WhatsApp not configured"}
        build = self.template_payload if os.environ.get("WA_TEMPLATE") else self.interactive_payload
        r = self._transport(f"{GRAPH}/{self.phone_id}/messages", build(self.recipient(to), msg, button_ids))
        return {"ok": "error" not in r, "channel": "whatsapp", "delivered": "error" not in r,
                "provider_id": ((r.get("messages") or [{}])[0]).get("id"), "error": r.get("error")}

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


def channel_for(preferred: str, force_preview: bool = False) -> Channel:
    """Preferred channel WhatsApp + configured -> real WhatsApp; everything else -> preview of that channel."""
    if not force_preview and preferred == "WHATSAPP" and wa_configured():
        return WhatsAppCloudChannel()
    return PreviewChannel(preferred or "SMS")

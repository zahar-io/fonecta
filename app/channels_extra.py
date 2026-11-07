"""More owner channels, built and switched OFF. Same Channel interface as WhatsApp, so turning one on is config,
not new logic: the engine, learning, decision log and Yext write stay the same.

* SmsChannel: any HTTP SMS gateway with a Twilio-style API (SMS_GATEWAY_URL, SMS_ACCOUNT, SMS_TOKEN, SMS_FROM).
  For owners without smartphones: "Reply 1 = yes, 2 = no, or just write the hours." Replies come back through the
  gateway's webhook and go through parse_sms_reply() into the same decide / free-text path as WhatsApp.
* IMessageChannel: Apple Messages for Business through a registered messaging service provider
  (IMSG_MSP_URL, IMSG_BUSINESS_ID, IMSG_TOKEN). Needs Apple's business registration, so it stays off for the demo.

Both are disabled unless SMS_ENABLED=1 / IMESSAGE_ENABLED=1 and their credentials are set."""
from __future__ import annotations

import base64
import json
import os
import re
import urllib.parse
import urllib.request

from .channels import Channel


def _hours_line(msg: dict) -> str:
    return (msg.get("sms") or msg.get("text") or "")[:600]


class SmsChannel(Channel):
    name = "sms"
    real = True

    @staticmethod
    def enabled() -> bool:
        return os.environ.get("SMS_ENABLED") == "1" and all(
            os.environ.get(k) for k in ("SMS_GATEWAY_URL", "SMS_ACCOUNT", "SMS_TOKEN", "SMS_FROM"))

    def _send(self, to: str, body: str) -> dict:
        if not self.enabled():
            return {"ok": False, "channel": "sms", "disabled": True, "note": "SMS channel is built but switched off"}
        url = f"{os.environ['SMS_GATEWAY_URL'].rstrip('/')}/Accounts/{os.environ['SMS_ACCOUNT']}/Messages.json"
        auth = base64.b64encode(f"{os.environ['SMS_ACCOUNT']}:{os.environ['SMS_TOKEN']}".encode()).decode()
        data = urllib.parse.urlencode({"To": to, "From": os.environ["SMS_FROM"], "Body": body[:1500]}).encode()
        req = urllib.request.Request(url, data=data, method="POST", headers={"Authorization": "Basic " + auth})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return {"ok": True, "channel": "sms", "provider_id": json.loads(r.read().decode()).get("sid")}
        except Exception as ex:  # noqa: BLE001
            return {"ok": False, "channel": "sms", "error": str(ex)[:120]}

    def send_suggestion(self, to, msg, button_ids):
        return self._send(to, _hours_line(msg) + "\n\nReply 1 = yes, 2 = no, or write the hours you want.")

    def send_text(self, to, text):
        return self._send(to, text)


def parse_sms_reply(text: str) -> tuple:
    """'1' / 'yes' -> ('approve', None); '2' / 'no' -> ('decline', None); anything else -> ('text', text),
    which goes to the same free-text parser as a WhatsApp message."""
    t = (text or "").strip().lower()
    if re.fullmatch(r"(1|y|yes|kyllä|joo|ja)\W*", t):
        return "approve", None
    if re.fullmatch(r"(2|n|no|ei|nej|nei)\W*", t):
        return "decline", None
    return "text", text.strip()


class IMessageChannel(Channel):
    name = "imessage"
    real = True

    @staticmethod
    def enabled() -> bool:
        return os.environ.get("IMESSAGE_ENABLED") == "1" and all(
            os.environ.get(k) for k in ("IMSG_MSP_URL", "IMSG_BUSINESS_ID", "IMSG_TOKEN"))

    def _send(self, to: str, payload: dict) -> dict:
        if not self.enabled():
            return {"ok": False, "channel": "imessage", "disabled": True,
                    "note": "iMessage channel is built but switched off (needs Apple Messages for Business)"}
        req = urllib.request.Request(os.environ["IMSG_MSP_URL"], data=json.dumps(
            {"businessId": os.environ["IMSG_BUSINESS_ID"], "destination": to, **payload}).encode(), method="POST",
            headers={"Authorization": "Bearer " + os.environ["IMSG_TOKEN"], "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return {"ok": True, "channel": "imessage", "status": r.status}
        except Exception as ex:  # noqa: BLE001
            return {"ok": False, "channel": "imessage", "error": str(ex)[:120]}

    def send_suggestion(self, to, msg, button_ids):
        # Apple's "list picker" carries the same three choices as the WhatsApp buttons.
        return self._send(to, {"type": "listPicker", "body": _hours_line(msg),
                               "items": [{"id": b, "title": t} for b, t in
                                         zip(button_ids, ("Approve", "Edit", "No thanks"))]})

    def send_text(self, to, text):
        return self._send(to, {"type": "text", "body": text})

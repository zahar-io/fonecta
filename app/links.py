"""No-login links: HMAC-SHA256 signed, expiring tokens. Format: base64url(json payload) "." base64url(sig)."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

from . import config

DEFAULT_TTL = 14 * 86400  # two weeks: enough for an owner to answer before the holidays


class TokenError(ValueError):
    pass


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def sign(payload: dict, ttl: int = DEFAULT_TTL, secret: bytes | None = None, now: float | None = None) -> str:
    body = dict(payload)
    body["exp"] = int((now if now is not None else time.time()) + ttl)
    raw = _b64(json.dumps(body, separators=(",", ":"), sort_keys=True).encode())
    sig = hmac.new(secret or config.app_secret(), raw.encode(), hashlib.sha256).digest()[:18]
    return f"{raw}.{_b64(sig)}"


def verify(token: str, secret: bytes | None = None, now: float | None = None) -> dict:
    try:
        raw, sig = token.split(".", 1)
        want = hmac.new(secret or config.app_secret(), raw.encode(), hashlib.sha256).digest()[:18]
        if not hmac.compare_digest(want, _unb64(sig)):
            raise TokenError("bad signature")
        body = json.loads(_unb64(raw))
    except TokenError:
        raise
    except Exception:
        raise TokenError("malformed token") from None
    if body.get("exp", 0) < (now if now is not None else time.time()):
        raise TokenError("expired")
    return body

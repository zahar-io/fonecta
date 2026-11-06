"""Yext Management API client (works against the kit mock and the real sandbox; standard library only).

* Auth via the `api-key` header (never the query string, so keys stay out of logs); v=20261101 on every call.
* YEXT_BASE_URL may be given with or without /v2 (mock: http://localhost:8787, sandbox: https://sbx-api.yextapis.com).
* holidayHours is REPLACED on PUT, so writes are GET fields=hours -> merge -> drop past dates -> sort -> PUT full hours.
* Where-is-it-live: the mock returns expectedLiveBy per publisher; real Yext doesn't, so we fall back to the
  listing status plus the typical update speed per publisher (from the kit's listings data), labelled "typical".

Every write goes through an Applier, and the engine only calls it with an explicit authority (owner decision or
standing permission). Tests swap the transport to record calls."""
from __future__ import annotations

import json
import os
import statistics
import urllib.error
import urllib.parse
import urllib.request
from datetime import date

from . import config
from .hours import merge_holiday_hours


class YextError(RuntimeError):
    pass


def _http(method, url, body=None, headers=None, timeout=15):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:  # url has no key in it (header auth), safe to show the path
        raise YextError(f"{method} {urllib.parse.urlparse(url).path} -> {e.code}: "
                        f"{e.read().decode()[:300]}") from None
    except (urllib.error.URLError, OSError) as e:
        raise YextError(f"{method} {urllib.parse.urlparse(url).path}: {e}") from None


def _typical_speeds() -> dict:
    """Median typicalUpdateSpeedSeconds per publisher from the kit's listings data (fallback for real Yext)."""
    from . import kitdata
    by = {}
    for ls in kitdata.listings_local().values():
        for l in ls:
            by.setdefault(l["publisherId"], []).append(l["typicalUpdateSpeedSeconds"])
    return {k: int(statistics.median(v)) for k, v in by.items()}


def entity_map() -> dict:
    out = {}
    for part in (os.environ.get("YEXT_ENTITY_MAP") or "").split(","):
        if "=" in part:
            a, b = part.split("=", 1)
            out[a.strip()] = b.strip()
    return out


def detect_client() -> "YextClient":
    """Detection reads "what Google shows now" from YEXT_DETECT_BASE_URL (default: YEXT_BASE_URL). When writing
    to the real sandbox, point this at the mock so detection still sees the demo businesses."""
    return YextClient(base_url=os.environ.get("YEXT_DETECT_BASE_URL") or config.yext_base())


class YextClient:
    def __init__(self, base_url=None, api_key=None, v=config.YEXT_V, transport=None):
        base = (base_url or config.yext_base()).rstrip("/")
        self.root = base[:-3] if base.endswith("/v2") else base   # host root (mock /health, /sim, /mock)
        self.key = api_key or config.yext_key()
        self.v = v
        self._transport = transport or _http
        self.is_mock = "yextapis.com" not in self.root and "yext.com" not in self.root
        # YEXT_ENTITY_MAP="FI-D0001=SinceAI15,FI-D0012=SinceAI19": demo business -> real sandbox entity.
        # Only used against real Yext; the mock has the demo ids itself.
        self.map = {} if self.is_mock else entity_map()

    def rid(self, eid: str) -> str:
        return self.map.get(eid, eid)

    def _req(self, method, path, params=None, body=None, extra_headers=None):
        q = {"v": self.v, **(params or {})}
        url = f"{self.root}/v2/accounts/me/{path}?{urllib.parse.urlencode(q)}"
        return self._transport(method, url, body, {"api-key": self.key, **(extra_headers or {})})

    def get_entity(self, eid: str, fields: str | None = None) -> dict:
        return self._req("GET", f"entities/{self.rid(eid)}", {"fields": fields} if fields else None)["response"]

    def put_hours(self, eid: str, hours_obj: dict) -> dict:
        return self._req("PUT", f"entities/{self.rid(eid)}", body={"hours": hours_obj},
                         extra_headers={"Yext-Username": "connect-suggests-bot"})

    def set_holiday_hours(self, eid: str, changes: dict, today: str | None = None) -> tuple:
        """Read-modify-write. Returns (previous entries by date or None, PUT response)."""
        cur = self.get_entity(eid, fields="hours").get("hours", {}) or {}
        prev = {d: next((dict(h) for h in cur.get("holidayHours", []) if h.get("date") == d), None) for d in changes}
        merged = merge_holiday_hours(cur, changes, today or date.today().isoformat())
        return prev, self.put_hours(eid, merged)

    def listings(self, eid: str) -> list:
        return self._req("GET", "listings/listings", {"locationIds": self.rid(eid)})["response"].get("listings", [])

    def where_live(self, eid: str) -> list:
        """Normalised per-publisher confirmation rows:
        {publisherId, publisherName, status, typicalUpdateSpeedSeconds, expectedLiveBy, source}."""
        speeds = None
        out = []
        try:
            got = self.listings(eid)
        except YextError:
            got = []
        if not got:  # real sandbox returns no listings: use the kit's listings, labelled "typical update time"
            from . import kitdata
            got = [{k: v for k, v in l.items() if k != "expectedLiveBy"} for l in kitdata.listings_local().get(eid, [])]
            for l in got:
                l["_typical"] = True
        for l in got:
            row = {"publisherId": l.get("publisherId"), "publisherName": l.get("publisherName") or l.get("publisherId"),
                   "status": l.get("status"), "listingUrl": l.get("listingUrl"),
                   "expectedLiveBy": l.get("expectedLiveBy")}
            if "typicalUpdateSpeedSeconds" in l:
                row["typicalUpdateSpeedSeconds"] = l["typicalUpdateSpeedSeconds"]
                row["source"] = ("typical update time (kit listings data)" if l.get("_typical") else
                                 "mock listings (expectedLiveBy)" if l.get("expectedLiveBy") else "listings")
            else:
                speeds = speeds or _typical_speeds()
                row["typicalUpdateSpeedSeconds"] = speeds.get(row["publisherId"], 86400)
                row["source"] = "listing status + typical update speed"
            out.append(row)
        return out

    def health(self) -> bool:
        try:
            if self.is_mock:
                self._transport("GET", f"{self.root}/health", None, {})
            return True
        except Exception:
            return False

    # ---- mock-only helpers
    def owner_response(self, eid, day, proposed, channel=None) -> dict:
        body = {"entityId": eid, "date": day, "proposedHours": proposed}
        if channel:
            body["channel"] = channel
        return self._transport("POST", f"{self.root}/sim/v1/owner-response", body, {})["response"]

    def reset(self) -> dict:
        return self._transport("POST", f"{self.root}/mock/reset", {}, {})["response"]


# ------------------------------------------------------------------ apply layer (pluggable)
class DirectEntityWrite:
    """Approve -> write holidayHours to the entity (GET -> merge -> PUT)."""
    name = "direct entity write (GET fields=hours -> merge -> PUT full hours)"

    def __init__(self, client: YextClient):
        self.client = client

    def apply(self, eid: str, changes: dict) -> dict:
        prev, resp = self.client.set_holiday_hours(eid, changes)
        warnings = [e.get("message") for e in (resp.get("meta") or {}).get("errors", []) if e]
        return {"previous": prev, "uuid": (resp.get("meta") or {}).get("uuid"), "warnings": warnings}


class YextSuggestionApprove:
    """Planned: file a native Yext Suggestion (POST /suggestions) and approve it
    (PUT /suggestions/action/{uid} {"status":"APPROVED"}) so the approver lives in Fonecta's backend.
    Not built yet: needs Suggestions R/W on the sandbox key, to be verified first."""
    name = "Yext native suggestion + APPROVED (not enabled)"

    def __init__(self, client: YextClient):
        self.client = client

    def apply(self, eid: str, changes: dict) -> dict:
        raise NotImplementedError("APPLY_MODE=yext_suggestion is not built yet; use APPLY_MODE=direct")


def get_applier(client: YextClient):
    mode = os.environ.get("APPLY_MODE", "direct")
    return YextSuggestionApprove(client) if mode == "yext_suggestion" else DirectEntityWrite(client)

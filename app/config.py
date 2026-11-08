"""Paths and settings. Everything comes from env vars; nothing secret is ever printed."""
from __future__ import annotations

import os
import secrets
from datetime import date

APP_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(APP_DIR)

KIT = os.environ.get(
    "FONECTA_KIT",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "FONECTA_CONNECT_SUGGESTS_2026"),
)
KIT_DATA = os.path.join(KIT, "data")
KIT_EXAMPLES = os.path.join(KIT, "examples")
TARGETS_CSV = os.path.join(KIT, "evaluation", "targets_2026.csv")

# Today in the scenario: Connect knows everything up to 5 Nov 2026.
SNAPSHOT = date(2026, 11, 6)

DEMO_IDS = ["FI-D0001", "FI-D0002", "FI-D0003", "FI-D0004", "FI-D0005", "FI-D0006", "FI-D0007", "SE-D0008",
            "NO-D0009", "FI-D0010", "FI-D0011", "FI-D0012", "FI-D0013", "FI-D0014", "NO-D0015", "SE-D0016",
            "FI-D0017"]

TZ = "Europe/Helsinki"
YEXT_V = "20261101"


def demo_first(eid: str | None, default: str = "") -> str:
    """DEMO_FIRST: one name for every business ("Mikko"), or per business ("FI-D0001=Mikko,FI-D0017=Aino");
    a business not in the per-business list keeps its own contact name. Unset = FI-D0001 is "Mikko", the owner in
    our films, deck and live demo (demo.zahar.io); set DEMO_FIRST= (empty) to use the kit's own contact names."""
    v = os.environ.get("DEMO_FIRST")
    v = ("FI-D0001=Mikko" if v is None else v).strip()
    if "=" not in v:
        return v or default
    names = dict(p.split("=", 1) for p in v.split(",") if "=" in p)
    return names.get(eid or "", "").strip() or default


def var_dir() -> str:
    d = os.environ.get("APP_VAR_DIR") or os.path.join(APP_DIR, "var")
    os.makedirs(d, exist_ok=True)
    return d


def yext_base() -> str:
    return os.environ.get("YEXT_BASE_URL", "http://localhost:8787").rstrip("/")


def yext_key() -> str:
    return os.environ.get("YEXT_API_KEY", "demo")


def brain_predictions() -> str | None:
    """The brain's per-row file. Default: predictions_2026_explained.csv in the repo root (v2.3, written by
    brain/train.sh). BRAIN_PREDICTIONS overrides it; BRAIN_PREDICTIONS=none runs the kit baseline instead."""
    p = os.environ.get("BRAIN_PREDICTIONS") or os.path.join(os.path.dirname(APP_DIR), "predictions_2026_explained.csv")
    return p if p != "none" and os.path.exists(p) else None


_SECRET: bytes | None = None


def app_secret() -> bytes:
    """APP_SECRET env, else a random secret generated once and kept in app/.secret (gitignored)."""
    global _SECRET
    if _SECRET is not None:
        return _SECRET
    env = os.environ.get("APP_SECRET")
    if env:
        _SECRET = env.encode()
        return _SECRET
    path = os.environ.get("APP_SECRET_FILE") or os.path.join(APP_DIR, ".secret")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            val = f.read().strip()
        if val:
            _SECRET = val.encode()
            return _SECRET
    val = secrets.token_urlsafe(48)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(val)
    _SECRET = val.encode()
    return _SECRET

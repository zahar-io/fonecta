"""Light AI for free-text owner requests ("open an hour later than usual on Friday").

Claude Haiku (through the Claude Code CLI during the event; the Anthropic API is a drop-in swap of `_ask_claude`),
with Gemini Flash-Lite as fallback, turns the message into {dates, hours} as JSON. Its answer is never trusted blindly: dates must be real and within a year, hours must pass
the same validator as everything else, and the owner still confirms with Save. If the model is off or unsure, the
rule-based parser in chat_edit takes over. Only the message text, today's date and the business's regular hours are sent.
"""
from __future__ import annotations

import json
import os
import urllib.request
from datetime import date, timedelta

from .hours import is_valid

DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
PROMPT = """You turn a small-business owner's chat message into an opening-hours change.
Today is {today} ({wd}). The business's regular weekly hours: {regular}.
Return JSON only: {{"dates": ["YYYY-MM-DD", ...], "hours": "HH:MM-HH:MM" | "HH:MM-HH:MM,HH:MM-HH:MM" | "closed" | null}}.
Rules: dates are future dates the owner means (next occurrence; a range like 24-26 Dec = every day in it; max 7).
Relative wishes ("an hour later than usual", "close early at 3") are resolved against that weekday's regular hours.
Use 24 h times. If the message is not about opening hours, return {{"dates": [], "hours": null}}.
If a date is clear but the hours are not, return the dates and "hours": null.
Message: {msg}"""


def enabled() -> bool:
    return os.environ.get("NLU", "1") == "1"


def _ask_claude(prompt: str) -> str | None:
    """Haiku via the `claude` CLI (CLAUDE_BIN). No tools, runs in /tmp, 25 s timeout."""
    import shutil
    import subprocess
    exe = os.environ.get("CLAUDE_BIN") or shutil.which("claude") or os.path.expanduser("~/.local/bin/claude")
    try:
        r = subprocess.run([exe, "-p", "--model", os.environ.get("CLAUDE_NLU_MODEL", "haiku")], input=prompt,
                           capture_output=True, text=True, timeout=25, cwd="/tmp")
    except (OSError, subprocess.TimeoutExpired):
        return None
    out = (r.stdout or "").strip()
    if out.startswith("```"):
        out = out.strip("`").split("\n", 1)[-1]
    i, j = out.find("{"), out.rfind("}")
    return out[i:j + 1] if i >= 0 and j > i else None


def _ask_gemini(prompt: str) -> str | None:
    if not os.environ.get("GEMINI_KEY"):
        return None
    body = {"contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0, "responseMimeType": "application/json"}}
    model = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "x-goog-api-key": os.environ["GEMINI_KEY"]})
    try:
        with urllib.request.urlopen(req, timeout=12) as r:
            return json.load(r)["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
        return None


def parse(msg: str, today: date, regular: dict) -> tuple:
    """-> (dates or None, hours or None). Never raises."""
    if not enabled():
        return None, None
    reg = ", ".join(f"{d}: {regular.get(d) or '?'}" for d in DAYS)
    prompt = PROMPT.format(today=today.isoformat(), wd=DAYS[today.weekday()], regular=reg, msg=msg[:500])
    text = None
    for backend in (os.environ.get("NLU_BACKEND", "claude,gemini")).split(","):
        text = _ask_claude(prompt) if backend.strip() == "claude" else _ask_gemini(prompt)
        if text:
            break
    try:
        j = json.loads(text or "")
    except ValueError:
        return None, None
    dates = []
    for d in (j.get("dates") or [])[:7]:
        try:
            dd = date.fromisoformat(str(d))
        except ValueError:
            continue
        if today <= dd <= today + timedelta(days=366):
            dates.append(dd.isoformat())
    h = j.get("hours")
    h = h.strip().lower() if isinstance(h, str) else None
    if h and not is_valid(h):
        h = None
    return (dates or None), h

"""Live review monitor: new reviews are scored for urgency; urgent ones go to the owner's WhatsApp with a drafted reply
([Post] [Edit] [Skip], Edit in the chat), the rest go to the weekly summary. Nothing is posted without the owner."""
from __future__ import annotations

import threading
import time

URGENT_WORDS = ("closed", "locked", "kiinni", "stängt", "stengt", "rude", "töykeä", "otrevlig", "uhøflig",
                "food poisoning", "sick", "ill after", "dirty", "hair in", "ruokamyrkytys", "likainen", "matförgiftning",
                "skitten", "smutsig", "refund", "never again", "scam")


def urgency(r: dict, views30: int = 0, now_ms: float | None = None) -> tuple:
    """-> (score, reasons). Urgent when score >= 3."""
    score, why = 0, []
    rating = int(r.get("rating") or 5)
    text = (r.get("content") or "").lower()
    if rating <= 2:
        score += 2
        why.append(f"{rating}★")
    hits = [w for w in URGENT_WORDS if w in text]
    if hits:
        score += 2
        why.append("mentions " + ", ".join(hits[:2]))
    now_ms = now_ms or time.time() * 1000
    if now_ms - (r.get("publisherDate") or 0) < 48 * 3600 * 1000:
        score += 1
        why.append("posted in the last 48 h")
    if views30 >= 500:
        score += 1
        why.append(f"{views30:,} people saw the listing last month")
    return score, why


class Monitor:
    def __init__(self, check, every_s: int = 60):
        self.check, self.every = check, every_s
        self._stop = threading.Event()

    def start(self):
        t = threading.Thread(target=self._run, daemon=True, name="review-monitor")
        t.start()
        return t

    def _run(self):
        while not self._stop.wait(self.every):
            try:
                self.check()
            except Exception:
                pass

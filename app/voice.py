"""WhatsApp voice notes: download the audio from Meta, convert with ffmpeg, transcribe on this machine with a local
Whisper server (WHISPER_URL, default http://127.0.0.1:8179/inference). The audio never goes to a cloud AI."""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import urllib.request
import uuid

GRAPH = "https://graph.facebook.com/v21.0"


def _auth():
    return {"Authorization": "Bearer " + os.environ.get("WA_TOKEN", "")}


def download(media_id: str) -> bytes | None:
    try:
        with urllib.request.urlopen(urllib.request.Request(f"{GRAPH}/{media_id}", headers=_auth()), timeout=15) as r:
            url = json.load(r).get("url")
        with urllib.request.urlopen(urllib.request.Request(url, headers=_auth()), timeout=30) as r:
            return r.read()
    except Exception:
        return None


def transcribe(audio: bytes, language: str = "auto") -> str | None:
    with tempfile.TemporaryDirectory() as d:
        src, wav = os.path.join(d, "in.ogg"), os.path.join(d, "out.wav")
        open(src, "wb").write(audio)
        try:
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-ar", "16000", "-ac", "1", wav],
                           check=True, timeout=30)
        except (OSError, subprocess.SubprocessError):
            return None
        data = open(wav, "rb").read()
    b = uuid.uuid4().hex
    field = lambda k, v: f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'  # noqa: E731
    body = (field("response_format", "json") + field("language", language) +
            f'--{b}\r\nContent-Disposition: form-data; name="file"; filename="v.wav"\r\nContent-Type: audio/wav\r\n\r\n'
            ).encode() + data + f"\r\n--{b}--\r\n".encode()
    url = os.environ.get("WHISPER_URL", "http://127.0.0.1:8179/inference")
    try:
        req = urllib.request.Request(url, body, {"Content-Type": f"multipart/form-data; boundary={b}"})
        return (json.loads(urllib.request.urlopen(req, timeout=60).read()).get("text") or "").strip() or None
    except Exception:
        return None

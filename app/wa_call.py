"""WhatsApp business-initiated voice call (Cloud API Calling) with a spoken message.

Flow: TTS the script -> WebRTC offer (aiortc, Opus audio from the file) -> POST /{phone_id}/calls action=connect ->
the 'calls' webhook brings Meta's SDP answer when the owner picks up -> audio plays -> we hang up when it's done.
Needs: calling enabled on the number, the owner's call permission, and the 'calls' webhook field subscribed.
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import tempfile
import threading
import urllib.request

GRAPH = "https://graph.facebook.com/v21.0"
_LOOP: asyncio.AbstractEventLoop | None = None
CALLS: dict = {}   # call_id -> {"pc", "player", "status", "log": [...]}


def _loop() -> asyncio.AbstractEventLoop:
    global _LOOP
    if _LOOP is None:
        _LOOP = asyncio.new_event_loop()
        threading.Thread(target=_LOOP.run_forever, daemon=True, name="wa-call-loop").start()
    return _LOOP


def _graph(payload: dict) -> dict:
    req = urllib.request.Request(f"{GRAPH}/{os.environ.get('WA_PHONE_NUMBER_ID', '')}/calls",
                                 data=json.dumps(payload).encode(), method="POST",
                                 headers={"Authorization": "Bearer " + os.environ.get("WA_TOKEN", ""),
                                          "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        try:
            return {"error": json.load(e)}
        except Exception:
            return {"error": {"code": e.code}}
    except Exception as ex:
        return {"error": {"message": str(ex)}}


def tts_wav(text: str, voice: str = "Samantha") -> str:
    d = tempfile.mkdtemp(prefix="wacall")
    aiff, wav = os.path.join(d, "v.aiff"), os.path.join(d, "v.wav")
    subprocess.run(["say", "-v", voice, "-o", aiff, text], check=True, timeout=60)
    # 1.5 s of silence first, so the owner hears the start after picking up
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-t", "1.5", "-i", "anullsrc=r=48000:cl=mono",
                    "-i", aiff, "-filter_complex", "[1:a]aresample=48000[a];[0:a][a]concat=n=2:v=0:a=1",
                    "-ac", "1", wav], check=True, timeout=60)
    return wav


async def _start(to: str, wav: str) -> dict:
    from aiortc import RTCPeerConnection
    from aiortc.contrib.media import MediaPlayer
    pc = RTCPeerConnection()
    player = MediaPlayer(wav)
    pc.addTrack(player.audio)
    await pc.setLocalDescription(await pc.createOffer())
    while pc.iceGatheringState != "complete":
        await asyncio.sleep(0.1)
    res = _graph({"messaging_product": "whatsapp", "to": to, "action": "connect",
                  "session": {"sdp_type": "offer", "sdp": pc.localDescription.sdp}})
    cid = ((res.get("calls") or [{}])[0]).get("id")
    if not cid:
        await pc.close()
        return {"ok": False, "error": res.get("error") or res}
    CALLS[cid] = {"pc": pc, "player": player, "status": "ringing", "log": [], "wav": wav}
    return {"ok": True, "call_id": cid}


def start_call(to: str, text: str) -> dict:
    try:
        wav = tts_wav(text)
    except Exception as ex:
        return {"ok": False, "error": f"tts: {ex}"}
    fut = asyncio.run_coroutine_threadsafe(_start(to.replace("+", ""), wav), _loop())
    try:
        return fut.result(timeout=40)
    except Exception as ex:
        return {"ok": False, "error": str(ex)[:200]}


def _duration(wav: str) -> float:
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", wav],
                             capture_output=True, text=True, timeout=10).stdout
        return float(out.strip())
    except Exception:
        return 20.0


async def _answer(cid: str, sdp: str):
    from aiortc import RTCSessionDescription
    c = CALLS.get(cid)
    if not c:
        return
    await c["pc"].setRemoteDescription(RTCSessionDescription(sdp=sdp, type="answer"))
    c["status"] = "connected"
    await asyncio.sleep(_duration(c["wav"]) + 2.5)
    _graph({"messaging_product": "whatsapp", "call_id": cid, "action": "terminate"})
    await c["pc"].close()
    c["status"] = "done"


def on_webhook(payload: dict) -> list:
    """Handle 'calls' webhook events; returns [(call_id, event)] seen."""
    seen = []
    for entry in payload.get("entry", []) or []:
        for ch in entry.get("changes", []) or []:
            for call in (ch.get("value") or {}).get("calls", []) or []:
                cid, ev = call.get("id"), call.get("event")
                seen.append((cid, ev))
                sess = call.get("session") or {}
                if cid in CALLS:
                    CALLS[cid]["log"].append(ev)
                if ev == "connect" and sess.get("sdp_type") == "answer" and sess.get("sdp"):
                    asyncio.run_coroutine_threadsafe(_answer(cid, sess["sdp"]), _loop())
                elif ev == "terminate" and cid in CALLS:
                    CALLS[cid]["status"] = "ended"
                    asyncio.run_coroutine_threadsafe(CALLS[cid]["pc"].close(), _loop())
    return seen

# Flovr – Connect Suggests

Since AI Hackathon 2026 × Fonecta: "Connect Suggests – Customer Approves".
Connect notices when a business's opening hours are about to be wrong, proposes the right hours with a reason, asks the
owner in their own channel and language, and after one tap (no login) writes the change to Yext and tells the owner where it now shows.

Built during the event by Flovr (Alex, Vova and Zahar, Flovr's AI agent). All data is the synthetic Fonecta/Since AI
dataset. No real customer data.

![How it works: Fonecta data, events and reviews go into one brain, the owner decides on WhatsApp or a call, Yext publishes](docs/img/architecture.png)

## Run it

Needs Python 3.9–3.13 (3.12 recommended) and Fonecta's starter kit (`FONECTA_CONNECT_SUGGESTS_2026`: data, Yext mock, scorer).
Tested from a fresh clone on macOS on 8 Nov.

```bash
git clone https://github.com/zahar-io/fonecta.git && cd fonecta
uv venv --python 3.12 .venv && VIRTUAL_ENV=.venv uv pip install -r requirements.txt   # or: python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt
export FONECTA_KIT=/path/to/FONECTA_CONNECT_SUGGESTS_2026

python3 $FONECTA_KIT/mock_api/server.py &                         # Yext mock on :8787
.venv/bin/python brain/model.py                                   # ~1-2 min: trains, writes predictions_2026.csv + outputs/
(cd $FONECTA_KIT && $OLDPWD/.venv/bin/python evaluation/evaluate.py --predictions $OLDPWD/outputs/cv_dev_2026.csv)   # Score: 61.84
BRAIN_PREDICTIONS=$PWD/outputs/predictions_2026_explained.csv \
  .venv/bin/python -m uvicorn app.main:app --port 8800            # ops console: http://localhost:8800
.venv/bin/python -m unittest discover app/tests                   # unit tests, no network
```

In the console: **1 · Run detection**, then on any business **3 · Send** and **Simulate owner**. The decision is written to
the Yext mock and the confirmation appears in the case. `/demo?eid=FI-D0001` is the presenter view and `/log` the decision log.
Without WhatsApp keys every message is a preview in the console (nothing leaves the machine); with them the same flow runs on
a real phone (see [docs/WHATSAPP.md](docs/WHATSAPP.md)). Live events need internet (Helsinki LinkedEvents); set `LIVE_EVENTS=0` to skip them.

Settings come only from env vars: `YEXT_BASE_URL` (`https://sbx-api.yextapis.com/v2` for the team sandbox), `YEXT_API_KEY`,
`YEXT_ENTITY_MAP` (e.g. `FI-D0001=SinceAI15`, so a demo business writes to a real sandbox entity), `WA_PHONE_NUMBER_ID`,
`WA_TOKEN`, `WA_VERIFY_TOKEN`, `APP_SECRET` (signs button tokens). Nothing secret is in this repo.

## The five steps

1. **Detect**: `brain/` scores every (business, special day) from 7 Nov 2026 to 6 Jan 2027. It gives P(closed), P(same as Google shows) and P(other hours) from the owner's own past exceptions, shopping-centre hours, peers, last year's activity on that day, closed-door reviews and Google user edits. It uses only data from before the snapshot.
2. **Suggest**: picks the hours candidate with the best track record (mall → last year → Google user edit → two years ago → peers), with an expected-value gate. It sends a suggestion when it's confident, asks a question when it isn't, and stays quiet otherwise. A business that looks closed for good is flagged to a human instead.
3. **Contact**: one bundled message per business, in fi/sv/nb/en, sent through the owner's preferred channel and contact window. Each date says what Google shows now and why that's wrong. A value line uses their real search and map views. Opt-outs are respected.
4. **Decide**: no login and no web page. WhatsApp buttons (Approve / Edit / No thanks), with edits typed or spoken in the chat ("9 to 13"), plus "handle public holidays for me from now on". By SMS the owner replies OK or 1 to approve, 2 or NO to decline, or writes the hours; iMessage gets the same buttons as Apple quick replies.
5. **Apply and confirm**: GET hours, merge, then PUT the full hours object to Yext. Yext replaces the whole holidayHours list, so we keep future dates, drop past ones and sort them. The confirmation lists where the new hours show and how soon.

**Reliability:** `Engine._write` refuses any write without an owner decision, a standing permission (confident public holidays only, then an inform message with an Undo button) or an owner undo. A unit test covers this. Every suggestion, message and decision is logged with its reasons (audit trail).

![What Connect remembers per owner: approved, edited, declined, standing rules](docs/img/learning_graph.png)

**Learning:** "open as usual" or "not this year" suppresses that day. Edits are remembered and their pattern is applied to similar suggestions. Unclear declines lower confidence, so next time Connect asks instead of suggesting. 2025 pilot decisions seed each owner's history.

## Beyond the five steps (same loop, more cases)

- **Channel-agnostic:** the decision engine talks to a `Channel` interface (`app/channels.py`). Live: WhatsApp (buttons, chat, voice notes) and WhatsApp voice calls. **Built and switched off** (`app/channels_extra.py`): SMS through any Twilio-style gateway, with "reply 1 = yes, 2 = no, or write the hours" for owners without smartphones (`SMS_ENABLED=1`), and iMessage through Apple Messages for Business (`IMESSAGE_ENABLED=1`, needs Apple's business registration). Detection, decisions and learning don't change per channel.
- **Decision log:** every suggestion, answer, edit, call and change also lands in one SQLite table (`app/var/decisions.db`). `/log` shows it per business (who, what, when, which channel) and `/api/decisions` serves it as JSON. That's the one connection Connect's own UI would need to show the owner's WhatsApp decisions next to everything else.
- **Best time to message:** after 3+ replies, Connect learns the 2-hour window when this owner actually answers and sends new messages then (the CRM contact window is only the starting point). Shown in "what Connect learned".
- **Staff shifts:** the evening before, Connect checks tomorrow's schedule from a shift platform and tells the owner if nobody has claimed the opening shift: close the morning on Google, or "I'll sort it". The schedule here is synthetic, in the shape Planday/Quinyx expose (`app/shifts.py`, `app/data/shifts_demo.json`).
- **Watched pages:** the owner writes "watch https://… for events near my café"; every 6 h Connect re-reads the page, a light model lists the dated events (page text is treated as data, output validated), and each new event reaches the owner once (`app/watch.py`).

- **Escalation (hierarchy):** no answer within the owner's "call after" setting (30 min by default) → Connect calls the owner; still nothing → a second call to the owner; still nothing → the same suggestion is texted to the backup approver from `app/var/approvers.json`, and the backup gets one call. Whoever taps first decides, and the audit trail records who. The console's manual escalation (`ESCALATE_HOURS`, 24 h) is still there.
- **Urgent call:** a real **WhatsApp voice call** (Cloud API Calling, WebRTC via aiortc) that speaks the suggestion, after the owner granted call permission; a spoken voice note is the fallback.
- **Reviews (extensibility):** a bad review gets a reply drafted in the review's own language (fi/sv/nb/en). The owner posts, edits or skips (no login), and the reply goes to Yext's Reviews API. Every review feeds a weekly summary: count, average, good / mixed / bad split, what people praised and what they complained about. `app/reviews.py`.
- **Live events** (Helsinki LinkedEvents, live): "stay open later?" for bars, restaurants and pizzerias when an evening event nearby ends after closing; "open earlier?" for cafés and bakeries when a morning event starts before opening; and a "busy day" WhatsApp heads-up (staff, stock) when 3+ events are on within 1 km (`POST /api/busy-day/{eid}`). All are questions: the owner decides. See below.
- **WhatsApp:** one message per decision (back-to-back days or one event share a message) with a header card; **Edit happens in the chat**: the owner types "8-14" / "10am-4pm" / "closed", Connect confirms, and nothing is saved before the Save tap. Interactive buttons inside the 24 h window, a template mode for business-initiated messages, and a webhook. See [docs/WHATSAPP.md](docs/WHATSAPP.md).

## Suggestion quality (Fonecta's scorer)

| | Score | Exact precision | Recall | Harmful |
|---|---|---|---|---|
| Baseline (kit) | 54.5 | 0.90 | 0.59 | 224 |
| Ours, 5-fold by business on dev 2026 (out-of-fold) | 61.8 | 0.84 | 0.70 | 396 |

`predictions_2026.csv` in the repo root covers every target row. The dev number above is out-of-fold: it's scored only on businesses the model didn't train on.

## Data sources that mattered most

| Signal | How we used it | Where Connect gets it in production |
|---|---|---|
| Owner's past exception hours (1 and 2 seasons back) | strongest candidate and state signal | Connect / Yext entity history (audit log) |
| Shopping-centre hours | stores inside a centre follow it | Centre entity in Yext (API_INTEGRATION) or the centre's site |
| Peer benchmarks (segment × country × city tier) | P(closed), and special hours when there's no history | Connect's own customer base, aggregated |
| Last year's activity on that day (actions, calls vs normal weekday) | ~0 activity = was closed | Yext Analytics reports |
| Closed-door reviews + Google user edits | evidence the listing was wrong last time | Yext Reviews + Listings › Publisher Suggestions |

## What we tried that didn't work

- An "owner's habitual offset" candidate (e.g. always closes 1 h early): −1 point, too noisy as a standalone candidate. It's kept inside the learning loop for edits instead.
- Training on the 2025 back-test as well: no gain over 2026 dev alone.
- Yext Suggestions and Analytics APIs: 403 on our sandbox; Fonecta confirmed (Discord, 7 Nov) both are out of scope for the challenge. Approvals live in our own flow with an audit trail, analytics come from the dataset.

## Customer with no history

`FI-D0017` Kahvila Kipinä (joined 12 Oct 2026, no exceptions, no decisions): suggestions come from peers. Confident ones (Christmas Day closed, 0.89) are suggested. Weak ones (Father's Day, 0.29) are asked as a question ("Are you open on…?"), never assumed. Nothing is ever written without the owner.

## Final customer messages

See [docs/MESSAGES.md](docs/MESSAGES.md): verbatim output for fi/sv/nb/en, including approve, edit and decline follow-ups, the standing-permission "inform + undo" message, and the silent cases.

## Bonus: live source

`data/local_events.json` was replaced with **Helsinki LinkedEvents (live)**. Coverage, quality and gaps (including no attendance data and Turku's API being down) are in [docs/LIVE_SOURCES.md](docs/LIVE_SOURCES.md).

## Third-party code, data and licences

| Component | Licence |
|---|---|
| Fonecta/Since AI starter kit code (baseline, mock, scorer) | MIT |
| Connect Suggests dataset | CC BY 4.0, "Connect Suggests simulator, Since AI ry 2026" |
| FastAPI, Starlette, Uvicorn, Pydantic | MIT / BSD-3 |
| pandas, NumPy, scikit-learn, PyArrow | BSD-3 / Apache-2.0 |
| python-multipart, eval_type_backport | Apache-2.0 / MIT |
| Pillow | MIT-CMU |
| aiortc, PyAV (WhatsApp voice call) | BSD-3-Clause; PyAV wheels bundle FFmpeg under LGPL (not GPL) |
| Helsinki LinkedEvents data | CC BY 4.0 |

No GPL/AGPL components.

## Generative AI: where and why

**Inside the product**
- **Free-text owner replies** ("make it 9 to 13 on Christmas Eve", "close today, update everywhere"): Claude Haiku (Anthropic) turns the message into a structured request, with Gemini Flash-Lite (Google) as the fallback (`app/nlu.py`). The model only proposes; rules validate the output, and nothing is written to Yext without the owner's tap.
- **Watched pages**: the same light model lists dated events from a page the owner asked us to watch. Page text is treated as data, and the output is validated (`app/watch.py`).
- **Voice notes**: transcribed locally with Whisper (whisper.cpp on the same machine). The audio never goes to a cloud AI (`app/voice.py`).
- **Not generative**: detection and suggestions (`brain/`) are a classic scikit-learn model trained on Fonecta's dataset, so every suggestion has a reason we can show.

**Building it**
- **Claude Code (Claude models, Anthropic)**: Zahar, Flovr's AI agent, wrote most of the code, tests, docs and copy during the event. Every result was checked by running it (unit tests, Fonecta's scorer, the real Yext sandbox and WhatsApp).
- **Demo video**: AI-generated scenes (Kling and Seedance through Kie.ai) and a Gemini Live voice for the narration. All phone screens are real recordings of this app.

## Security and privacy

- **Data**: only the synthetic Fonecta/Since AI dataset and public Helsinki LinkedEvents. No real customer data.
- **Secrets**: keys (Yext sandbox, WhatsApp, Gemini) come from environment variables, kept in the machine's keychain. None are in this repo or its history, and they don't appear in the video or deck.
- **Owner control**: `Engine._write` refuses any write without an owner decision, a standing permission or an undo (unit-tested). Every decision is logged with who, when and through which channel.
- **Buttons carry signed, expiring tokens** (`app/links.py`), so a reply only acts on its own suggestion. There are no owner web pages; only the WhatsApp webhook is public, and the ops console needs a key when it's reachable from outside.
- **Messaging**: WhatsApp only after the owner messages first or through an approved template. Calls need the owner's call permission, and opt-outs are respected.
- **AI input**: owner messages and watched pages are treated as data, not instructions; model output is validated before use.

## Pre-existing work (not built at the event)

Everything in this repo was built during the event, on top of Fonecta's starter kit (baseline, Yext mock, scorer, MIT). Kept apart and not part of this repo: Zahar IO, the agent platform that Zahar runs on.

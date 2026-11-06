# Flovr – Connect Suggests

Since AI Hackathon 2026 × Fonecta: "Connect Suggests – Customer Approves".
Connect notices when a business's opening hours are about to be wrong, proposes the right hours with a reason, asks the
owner in their own channel and language, and after one tap (no login) writes the change to Yext and tells the owner where it now shows.

Built during the event by Flovr (Alex, Vova and Zahar, Flovr's AI agent). All data is the synthetic Fonecta/Since AI
dataset. No real customer data.

## Run it

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
export FONECTA_KIT=/path/to/FONECTA_CONNECT_SUGGESTS_2026        # the starter kit (data + Yext mock)
python $FONECTA_KIT/mock_api/server.py &                          # Yext mock on :8787
.venv/bin/python brain/model.py                                   # trains, writes predictions_2026.csv (+ explained CSV)
BRAIN_PREDICTIONS=$PWD/outputs/predictions_2026_explained.csv \
  .venv/bin/python -m uvicorn app.main:app --port 8800            # ops console: http://localhost:8800
.venv/bin/python -m unittest discover app/tests                   # 10 tests, no network
```

Settings come only from env vars: `YEXT_BASE_URL` (`https://sbx-api.yextapis.com/v2` for the team sandbox), `YEXT_API_KEY`,
`YEXT_ENTITY_MAP` (e.g. `FI-D0001=SinceAI15`, so a demo business writes to a real sandbox entity), `WA_PHONE_NUMBER_ID`,
`WA_TOKEN`, `WA_VERIFY_TOKEN`, `APP_BASE_URL` (public tunnel URL for links), `APP_SECRET`. Nothing secret is in this repo.

## The five steps

1. **Detect**: `brain/` scores every (business, special day) from 7 Nov 2026 to 6 Jan 2027. It gives P(closed), P(same as Google shows) and P(other hours) from the owner's own past exceptions, shopping-centre hours, peers, last year's activity on that day, closed-door reviews and Google user edits. It uses only data from before the snapshot.
2. **Suggest**: picks the hours candidate with the best track record (mall → last year → Google user edit → two years ago → peers), with an expected-value gate. It sends a suggestion when it's confident, asks a question when it isn't, and stays quiet otherwise. A business that looks closed for good is flagged to a human instead.
3. **Contact**: one bundled message per business, in fi/sv/nb/en, sent through the owner's preferred channel and contact window. Each date says what Google shows now and why that's wrong. A value line uses their real search and map views. Opt-outs are respected.
4. **Decide**: a signed, expiring link (no login) offers Approve / Edit (time picker, or closed) / No thanks with a one-tap reason, plus "handle public holidays for me from now on". The same decisions work from WhatsApp reply buttons.
5. **Apply and confirm**: GET hours, merge, then PUT the full hours object to Yext. Yext replaces the whole holidayHours list, so we keep future dates, drop past ones and sort them. The confirmation lists where the new hours show and how soon.

**Reliability:** `Engine._write` refuses any write without an owner decision, a standing permission (confident public holidays only, then inform with a one-tap Undo) or an owner undo. A unit test covers this. Every suggestion, message and decision is logged with its reasons (audit trail).

**Learning:** "open as usual" or "not this year" suppresses that day. Edits are remembered and their pattern is applied to similar suggestions. Unclear declines lower confidence, so next time Connect asks instead of suggesting. 2025 pilot decisions seed each owner's history.

## Suggestion quality (Fonecta's scorer)

| | Score | Exact precision | Recall | Harmful |
|---|---|---|---|---|
| Baseline (kit) | 54.5 | 0.90 | 0.59 | 224 |
| Ours, 5-fold by business on dev 2026 (out-of-fold) | 61.9 | 0.83 | 0.70 | 381 |

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
- Training on the 2025 back-test as well: no gain over 2026 dev alone (61.9 vs 61.9).
- Yext Suggestions and Analytics APIs on the sandbox: 403 for our app, so we kept the analytics from the dataset. The apply layer can switch to native Yext suggestions (`APPLY_MODE`).

## Customer with no history

`FI-D0017` Kahvila Kipinä (joined 12 Oct 2026, no exceptions, no decisions): suggestions come from peers. Confident ones (Christmas Day closed, 0.89) are suggested. Weak ones (Father's Day, 0.29) are asked as a question ("Are you open on…?"), never assumed. Nothing is ever written without the owner.

## Final customer messages

See [docs/MESSAGES.md](docs/MESSAGES.md): verbatim output for fi/sv/nb/en, including approve, edit and decline follow-ups, the standing-permission "inform + undo" message, and the silent cases.

## Bonus: live source

TODO (in progress): live events next to the business (stay open later?) and/or public holidays from Nager.Date.

## Third-party code, data and licences

| Component | Licence |
|---|---|
| Fonecta/Since AI starter kit code (baseline, mock, scorer) | MIT |
| Connect Suggests dataset | CC BY 4.0, "Connect Suggests simulator, Since AI ry 2026" |
| FastAPI, Starlette, Uvicorn, Pydantic | MIT / BSD-3 |
| pandas, NumPy, scikit-learn, PyArrow | BSD-3 / Apache-2.0 |
| python-multipart, eval_type_backport | Apache-2.0 / MIT |

No GPL/AGPL components. GenAI used: Claude (Anthropic) via Claude Code, for code and copy, with every result checked by running it.

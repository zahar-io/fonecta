# Configuration

Everything is set with environment variables, plus two optional files under `app/`: `app/.secret` (the token-signing
key, created on first run, mode 0600) and `app/var/approvers.json` (backup approvers per business). With nothing set,
the app runs fully offline against the kit's Yext mock and every message is a preview in the console.

## Kit and data
| Variable | Default | What it does |
|---|---|---|
| `FONECTA_KIT` | `../FONECTA_CONNECT_SUGGESTS_2026` | Fonecta's starter kit folder (data, Yext mock, scorer) |
| `BRAIN_PREDICTIONS` | `predictions_2026_explained.csv` in the repo root | The brain's per-row file. `none` runs the kit baseline instead |
| `APP_VAR_DIR` | `app/var` | Where cases, the decision log and webhook events are stored |
| `APP_SECRET_FILE` | `app/.secret` | File holding the token-signing key when `APP_SECRET` is not set |

## Yext
| Variable | Default | What it does |
|---|---|---|
| `YEXT_BASE_URL` | `http://localhost:8787` (kit mock) | Where approved changes are written. `https://sbx-api.yextapis.com/v2` for the sandbox |
| `YEXT_API_KEY` | `demo` | Yext API key |
| `YEXT_ENTITY_MAP` | – | Maps demo businesses to real sandbox entities, e.g. `FI-D0001=SinceAI15` |
| `YEXT_DETECT_BASE_URL` | `YEXT_BASE_URL` | Where detection reads "what Google shows now". Point at the mock when writing to the sandbox |
| `APPLY_MODE` | `direct` | How a decision reaches Yext. Only `direct` is built |

## WhatsApp (see [WHATSAPP.md](WHATSAPP.md))
| Variable | Default | What it does |
|---|---|---|
| `WA_PHONE_NUMBER_ID`, `WA_TOKEN` | – | Meta WhatsApp Cloud API. Without them every message is a console preview |
| `WA_VERIFY_TOKEN` | – | Answers Meta's webhook verification |
| `WA_APP_SECRET` | – | Meta app secret. When set, webhook POSTs without a valid `X-Hub-Signature-256` are rejected (403) |
| `WA_TO` | – | Demo safety: the kit's phone numbers are fake, so every message goes to this one test phone |
| `WA_ALLOW` | – | Comma-separated numbers that may still receive messages directly (e.g. a backup approver's real phone) |
| `WA_TEMPLATE`, `WA_TEMPLATE_LANG` | –, `fi` | Approved template for the first message outside the 24-hour window |
| `WA_PER_DATE` | `1` | One message per decision; only back-to-back days share one |
| `WA_CARDS` | `1` | Attach the image card to suggestion messages |
| `APP_SECRET` | from `app/.secret` | Signs the button tokens (HMAC-SHA256) |

## AI
| Variable | Default | What it does |
|---|---|---|
| `NLU` | `1` | `0` turns the AI off; the rule-based parser handles free text alone |
| `NLU_BACKEND` | `claude,gemini` | Order in which models are tried |
| `CLAUDE_BIN`, `CLAUDE_NLU_MODEL` | `claude` on PATH, `haiku` | Claude CLI used during the event (the Anthropic API is a drop-in swap) |
| `GEMINI_KEY`, `GEMINI_MODEL` | –, `gemini-3.5-flash-lite` | Gemini fallback |
| `WHISPER_URL` | `http://127.0.0.1:8179/inference` | Local whisper.cpp server for voice notes. Without it the owner is asked to type |

## Demo and timing
| Variable | Default | What it does |
|---|---|---|
| `DEMO_FIRST` | `FI-D0001=Mikko` (empty = the kit's own contact names) | One first name for every business (`Mikko`) or per business (`FI-D0001=Mikko`) |
| `DEMO_LANG` | the business's language | Force the message language (`fi`, `sv`, `nb`, `en`) |
| `DEMO_EXTRA` | `FI-00125` | Extra businesses added to the demo detection run |
| `LIVE_EVENTS` | `1` | Helsinki LinkedEvents lookup (needs internet). `0` skips it |
| `EVENT_DAYS` | `3` | How many days ahead live events are considered |
| `URGENT_WITHIN_H` | `48` | A sent suggestion due within this many hours can trigger a call |
| `ESCALATE_HOURS` | `24` | No answer by then: the suggestion goes to the next approver |
| `APP_CONSOLE_KEY` | – | When set, the console needs `?k=<key>` once (then a cookie); only the webhook stays public |

## Background jobs
| Variable | Default | What it does |
|---|---|---|
| `REVIEW_MONITOR` | `1` | Starts the background loop (reviews, auto calls, watched pages, shift check) |
| `REVIEW_POLL_S` | `60` | Loop interval in seconds |
| `AUTO_CALLS` | `0` | `1` lets the loop call owners who haven't answered (calls never decide) |
| `SHIFT_CHECK` | `1` | Evening check of tomorrow's opening shift (19:00–21:00 Helsinki) |

## SMS and iMessage (optional channels)
| Variable | What it does |
|---|---|
| `SMS_ENABLED=1`, `SMS_GATEWAY_URL`, `SMS_ACCOUNT`, `SMS_TOKEN`, `SMS_FROM` | Any Twilio-style SMS gateway |
| `IMESSAGE_ENABLED=1`, `IMSG_MSP_URL`, `IMSG_BUSINESS_ID`, `IMSG_TOKEN` | Apple Messages for Business through a messaging provider |

## brain/
`brain/train.sh` sets every brain variable (`THR_CLOSED`, `THR_OPEN`, `DPKL`, `XC`, `XD`, `CAL`, `TAG`, `SM`, …).
Nothing needs setting by hand.

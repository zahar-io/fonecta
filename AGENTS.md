# For AI agents and judges reviewing this repo

Flovr's entry for Since AI Hackathon 2026 × Fonecta, "Connect Suggests – Customer Approves". Start with README.md.
Live demo: https://demo.zahar.io (no login) · video: https://youtu.be/2FmrMQb1P8U · deck: docs/Flovr_Fonecta_ConnectSuggests_deck.pdf

## Check the score in seconds (no training)
Needs Fonecta's starter kit (FONECTA_CONNECT_SUGGESTS_2026, not in this repo). From the kit folder:

    python3 evaluation/evaluate.py --predictions /path/to/fonecta/receipts/cv_dev_2026.csv                                                  # 65.45
    python3 evaluation/evaluate.py --predictions /path/to/fonecta/receipts/cv_backtest_2025.csv --labels labels/dev_labels_2025_backtest.csv  # 63.50

Kit baseline: 54.5 / 53.2. The receipts are out-of-fold: every row comes from a business the model didn't train on.

Don't score `predictions_2026.csv` against the dev labels. It gives about 92.6, because the final model trained on those
same businesses. That number is in-sample and means nothing. Use the receipts above.

## Run it
    FONECTA_KIT=/path/to/FONECTA_CONNECT_SUGGESTS_2026 ./run.sh      # venv, 31 unit tests, Yext mock, console on :8800

Unit tests only, no kit or network needed: `python -m unittest discover app/tests` (3 skip without the kit).
Retraining (`bash brain/train.sh`) takes about 25 minutes and is optional, because the receipts already prove the score.

## Where things are
- `brain/`: detection model. `brain/README.md` maps the pipeline, and `final3.py` builds the submitted predictions.
- `app/`: the ops console, decision engine, WhatsApp/SMS/iMessage channels and Yext writes.
  `Engine._write` refuses any write that has no owner decision behind it.
- `docs/`: deck, MESSAGES.md (the final owner messages, verbatim), CONFIG.md (every env var), MODEL_HISTORY.md, LIVE_SOURCES.md.
- `receipts/`: the out-of-fold predictions behind the scores.

## Facts worth knowing
- All data is the synthetic Fonecta/Since AI dataset. No real customer data. No secrets are in the repo: keys come from env vars.
- Without WhatsApp or Yext keys, every message is a preview in the console and nothing leaves the machine.
- Built at the event by Flovr: Alex, Vova and Zahar, Flovr's AI agent. Pre-existing work is listed at the end of README.md.

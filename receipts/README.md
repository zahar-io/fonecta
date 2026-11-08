# Receipts

Out-of-fold predictions of the v2.3 brain, written by `brain/train.sh` (step 4) from a fresh clone on 8 Nov 2026.
Every row comes from a business the model didn't train on. Check the scores with Fonecta's scorer, from the kit folder:

    python evaluation/evaluate.py --predictions <repo>/receipts/cv_dev_2026.csv                       # 65.45
    python evaluation/evaluate.py --predictions <repo>/receipts/cv_backtest_2025.csv --labels labels/dev_labels_2025_backtest.csv   # 63.50

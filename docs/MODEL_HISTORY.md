# Model history

How the brain went from the kit baseline (54.5) to v2.3 (65.45 dev, 63.50 back-test). Scores are in the README table.
Only v2.3's code is kept in this repository.

**v1**: one gradient-boosted open/closed model plus last-year / peer hours candidates (61.8 dev, 59.3 back-test).

**v2** adds:
- a candidate model that scores about 30 hours candidates per date (last year, mall, Google edits, peers, shifts of
  the shown hours, mixes of these) by the scorer points it expects;
- the decision takes the action with the highest expected points (+1 exact, -0.5 needless, -1 wrong state);
- owner-level habit across all their special days, plus entries already made for this season;
- last season's activity over the Christmas cluster against a stable autumn baseline, and an activity-collapse signal;
- 2025 pilot decisions;
- reviews that name the holiday ("closed on Epiphany", "closed already at 18 on NYE"), used both as a state signal
  and as an hours candidate;
- an average of 4 model configs, one of them also trained on the 2025 season.

**v2.1** adds:
- **Calibration.** The open/closed model was overconfident: at a stated 0.85 it was right about 0.63 of the time. An
  inner 3-fold by business, run inside each training fold, fits a logistic calibration layer. After it, the best
  thresholds sit near the theoretical 0 (closed 0.1, open 0), so the expected-points decision means what it says.
- **Poisson evidence from analytics** (`brain/an_llr.py`). On a day the shop was closed while Google said open,
  customer actions fall to about 0.6x the usual weekday and phone calls don't fall. The old feature mixed the two. A
  log-likelihood ratio over every past occurrence of the same day: AUC 0.755 vs 0.63 for closed against open, on
  rows with no owner entry last year.
- **Fold-safe label statistics** (`brain/te.py`, `brain/v3.py`). Built from training-fold businesses only (their labels
  and their 2024-25 truth history): how this segment, in this country, on this day really changes its hours, used
  as state features, as hours candidates and as candidate features. Training rows get the statistics from inner
  folds, because leave-one-out leaked the label (first try: 60.9).
- The ensemble is 3 calibrated models (g1cal, g1calc, v3cal).

**v2.2** (`brain/extra2.py`) adds the owner's own Sunday and Saturday regular hours and their most
common open entry last season as hours candidates: on many holidays a business simply runs its weekend hours. It
also adds the owner's state on each holiday last season as separate features, because habits correlate across
holidays (closed on Father's Day goes with closed on Boxing Day at 0.63). Same 3-model calibrated ensemble (h1cal,
h1calc, v3hcal), thresholds closed 0.1, open -0.1 picked on the 2025 sweep.

**v2.3** (`brain/extra5.py`, `brain/final3.py`) adds **owner diligence**: how many of last season's (and
the season before's) special days the owner entered at all, the same for the Christmas cluster, how many days ahead
they entered, and how often they entered "regular hours". An owner who never enters exceptions leaves Google wrong,
which is exactly the case we have to catch. The ensemble is now 5 calibrated models of different kinds: v2 with
diligence (two candidate models), v2 with a LightGBM state model, v3 with the extra kit data (`brain/extra4.py`),
and v3 on the v2.2 features. Thresholds closed 0, open -0.1 from the 2025 sweep. The combination was picked with a
greedy search over saved out-of-fold predictions that looked at both seasons, so part of the +0.3 / +0.5 is search
luck; seeds alone move a single model by about 0.2.

Tried in the v2.3 round and not kept: weather (the kit stops at the 15 Nov forecast), listing status, events within 1 km,
school breaks, category ids, a cleaner activity baseline that skips other holidays (all about ±0.1); class weights
(64.8 / 62.9 single); random forest (63.5 / 59.3); separate thresholds for the Christmas cluster (no change).

Tried and not kept: a low-confidence FLAG (+0.06, not worth confusing "flag" in the app); adding the 2025 season as
training rows (worse in both seasons); bigger or slower trees without calibration.

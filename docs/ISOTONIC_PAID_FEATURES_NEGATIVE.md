# Fixed monotone paid-feature projection: negative result

The prefrozen isotonic paid-feature challenger is **rejected**. The current
bandwidth-0.7 model remains the development incumbent.

| Complete 119-sample / 59-patient task | MSE | p90 patient RMSE |
|---|---:|---:|
| **Bandwidth-0.7 incumbent** | **0.001058275042** | **0.037894285** |
| Fixed isotonic paid features | 0.001073173378 | 0.038166466 |

The candidate is 1.4078% worse in patient-balanced full-24 MSE. It improves
24/59 patient means, loses 35/59, improves only 2/5 outer-fold means, has a
worse p90, and regresses on 13/24 target-average errors. Its descriptive
10,000-resample patient bootstrap interval for candidate-minus-incumbent MSE
is `[-3.0801e-6, +3.9183e-5]`; it crosses zero and is not selection-corrected.

## What was tested

The candidate retained every fitting-slice acquisition plan, all 64 distinct
treatment wells, the 32/32 plate split, all 24 targets, the five outer and
three inner whole-patient folds, and the bandwidth-0.7 residual family. It
changed only the values presented to the candidate predictor: within each
sample, orientation and drug, the two or three purchased normalized-viability
values were ordered by increasing native dose and projected onto a
non-increasing sequence with deterministic equal-weight PAVA.

No clipping or tunable projection strength was allowed. Incumbent controls
received the original paid values. Candidate and incumbent used identical
physical plans, and A/B losses—not predictions—were averaged. The projection
changed 22.5% to 24.0% of fitting values across outer fits; the maximum
absolute adjustment was 0.6021.

The protocol and family identity were frozen before the first Lib1 fit. Seven
invented-data tests passed before fitting. A separate no-refit audit then
recomputed the complete-task candidate and incumbent metrics, patient wins,
fold wins, and physical budgets from the committed private prediction arrays.

## Decision

The candidate failed every immediate successor clause: lower MSE, at least
30 patient wins, all five favorable folds, and nonworse p90. The family is
closed. There is no retry, projection-strength menu, selective target use, or
outer-fold splice.

This is repeated adaptive development on the original Lib1 TRAIN population,
not independent validation, a clinical result, prospective organ-on-chip
evidence, an official competition score, or evidence of finalist rank.

Machine-readable aggregate evidence: [isotonic_paid_features_20261004.json](../evidence/isotonic_paid_features_20261004.json)

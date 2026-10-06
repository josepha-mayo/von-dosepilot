# 72-well transferred control-quality rank-1 protocol

This is a no-retuning transfer experiment on repeated Lib1 development data.

## Fixed base

The base is the already-frozen 72-well point from the seven-budget curve:

- 24 targets, all using their fitting-only best size-3 native subset;
- 36 p1 + 36 p2 treatment wells per A/B deployment;
- patient-balanced OOF MSE 0.0010055928901387746;
- predictions SHA-256 3c3ba9d3dc1e1aaf7b7e3849ee13157ddbe298f81b60aa02d0d8e41096a7dcc0.

## Transferred recipe

No new basis, rank, ridge prior, or strength is tuned.

For each held-out outer patient fold:

1. Use only the other four folds' **OOF** 72-well residuals as calibration targets.
2. Orientation A uses the exact existing 7-feature level basis from `orientation_specific_control_quality_rank1`: range mean, range half-difference, range-mean squared, negative-control log-median mean/half-difference, and positive-control log-median mean/half-difference.
3. Orientation B uses the exact existing 11-feature full-quality basis, adding negative- and positive-control CV mean/half-difference.
4. Fit the existing patient-weighted ridge map with prior 0.125 and truncate its coefficient matrix to rank 1.
5. Apply the already-frozen deployment strengths: **A = 1/9**, **B = 1/3**.
6. Add the predicted residual correction to the 72-well OOF base for the held-out fold.

No held-out patient's residual contributes to its own correction model. No inner search is performed.

## Evaluation

Primary: equal-patient, equal-target average of A/B squared errors.

Secondary: p90 patient RMSE, patient wins, target-average wins, five outer-fold MSEs, and a prespecified 100,000-resample descriptive whole-patient bootstrap versus the 72-well base (seed 20261006).

The current 64-well scientific successor is a frozen comparator only, not a training input.

## Boundary

This remains repeated adaptive Lib1 development. Cross-fold residual calibration does not make it independent validation or a prospective uncertainty/clinical claim. No Protected22 response access. Report regardless of direction. No automatic retry or parameter change.

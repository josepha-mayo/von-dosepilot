# Cross-patient median-normalized bandwidth study

Status before biological fitting: **PREFROZEN**. This is one bounded Lib1 TRAIN
challenger. It is not permission to inspect Protected22/Lib2, add another
bandwidth menu after outcomes, or reinterpret a failed gate.

## Falsifiable hypothesis

The current additive residual kernel uses the same multiplier, 0.7, for every
two- or three-coordinate drug group. Coordinate-wise standardization does not
remove within-group dependence. A deterministic, response-free normalization
of each group by its fitting-patient distance scale may make the meaning of
"0.7-local" more comparable across the 24 groups.

For fitting rows `i,k` from different whole patients and drug group `j`, define

`D[i,k,j] = ||z[i,j] - z[k,j]||^2`, with pair weight `w[i] * w[k]`.

Let `m[j]` be the deterministic weighted median over cross-patient pairs. Use
the fixed reference medians

- `m0[2] = 2.772588722239781`
- `m0[3] = 4.731947768750675`

and set `b[j] = 0.7 * sqrt(m[j] / m0[d[j]])`. The candidate kernel is

`z z' + sum_j d[j] exp(-||z_j-z'_j||^2 / (2 d[j] b[j]^2))`.

Bandwidth estimation accepts paid fitting features, patient identities,
patient weights and the fixed ownership vector only. It receives no outcome,
residual, validation-row or held-patient argument. Same-patient row pairs are
excluded. Nonfinite input, fewer than two patients, an empty cross-patient pair
set or a median not exceeding `1e-12` is a hard failure. There is no clipping,
fallback or response-derived bandwidth.

## Fixed procedure

- Population: all 119 Lib1 TRAIN samples from all 59 whole patients.
- Targets: the unchanged 24 normalized log-dose AUC summaries.
- Budget: exactly 64 distinct physical treatment wells per deployment
  orientation, 32 per plate. A/B predictions remain separate and only their
  losses are averaged.
- Splits: unchanged five outer and three inner whole-patient folds and salts.
- Acquisition: unchanged fitting-slice R13 plan, regenerated inside every
  fitting partition.
- Base: unchanged own-drug ridge with penalty 0.01.
- Candidate inner menu: the existing ten residual-spectral options only:
  identity, or fraction in `{0.1, 0.3, 0.6}` crossed with residual ridge in
  `{0.1, 1, 10}`. There is no geometry menu.
- Immediate control: bandwidth-0.7, independently tuned over the same ten
  options in every inner fitting slice.
- Historical controls: R13, archived R18 and the previous additive-1.0 model.
- Weighting: equal whole-patient, equal target and equal A/B-orientation risk.
- Bootstrap: 10,000 whole-patient resamples with seed `20261004`; descriptive
  only and not a promotion clause.

All plans, scales, medians, bandwidths, centering statistics, residual
coefficients and option selections are fitted within the relevant fitting
partition. Held-patient outcomes and features do not enter fitting.

## Frozen promotion gate

The candidate is promoted only if **every** clause is true.

Against bandwidth-0.7:

1. strictly lower patient-balanced full-24 MSE;
2. at least 30 of 59 strict patient wins;
3. favorable mean error in all 5 outer folds;
4. nonworse p90 patient expected RMSE.

Against each of R13 and archived R18:

1. at least 5% lower MSE;
2. at least 40 of 59 strict patient wins;
3. at least 4 of 5 favorable outer folds;
4. nonworse p90 patient expected RMSE;
5. both candidate orientation-wide MSEs below that reference's expected MSE.

The candidate is also rejected if its complete predictions equal the
bandwidth-0.7 predictions within absolute `1e-12`. A lower point estimate with
insufficient breadth, fold consistency or tail behavior is not promoted.

## Required controls and reporting

- Reproduce bandwidth-0.7, additive-1.0 and R13 MSE within `1e-12`.
- Authenticate R18 sample, patient, drug, fold and target arrays before parsing
  its predictions; the R18 archive is never a fitting input.
- Confirm identical physical plans for candidate and bandwidth-0.7 in every
  outer fold and 64 distinct wells with a 32/32 plate split.
- Save private held-patient predictions before reading R18 predictions.
- Report all patient wins/losses/ties, all fold differences, both orientation
  MSEs, all 24 target deltas, selected options and aggregate fitting-bandwidth
  min/median/max. Patient identifiers, fitted biological arrays and private
  predictions remain private.
- Preserve the first attempt, including a failed result or implementation
  failure. No automatic scientific retry or post-result grid expansion.

## Pre-fit synthetic requirements

Weighted-median tie determinism, direct pair-loop parity, exclusion of all
same-patient pairs, row-permutation invariance, patient-row duplication with
split weights, exact anchor parity with bandwidth-0.7, group-label permutation,
query batching, positive semidefiniteness and hard rejection of malformed or
degenerate inputs must pass before the freeze is issued.

This is repeated adaptive development on the same 59 patients. Even a passing
result is not independent validation, prospective organ-on-chip performance,
clinical benefit, an official competition score or proof of finalist rank.

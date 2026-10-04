# Retrospective nested bandwidth-selection evaluation

Status before fitting: **PREFROZEN**. This is an evaluation of the already
opened additive-bandwidth family, not a new challenger and not an independent
validation set.

## Question

Bandwidth 0.7 was selected from the prefrozen `{0.7, 1.0, 1.4}` menu after
the five outer-fold development results had been inspected. How well would the
predeclared *procedure* "select one bandwidth and one residual-spectral option
inside each outer training set" have performed without using that outer fold's
outcomes for its choice?

## Frozen procedure

- Use all 119 Lib1 TRAIN samples, all 59 whole patients and all 24 fixed
  normalized log-dose AUC targets.
- Retain the historical five outer and three inner whole-patient folds and
  salts.
- Regenerate the R13 acquisition plan and every scale/model inside each
  fitting partition.
- Each alternative costs exactly 64 distinct treatment wells, split 32/32
  across the two plates. Keep A/B predictions separate and average losses,
  never predictions.
- Within each outer training set, evaluate the Cartesian product of the three
  already opened multipliers, in fixed order `{0.7, 1.0, 1.4}`, and the ten
  existing residual-spectral options: identity, or fraction
  `{0.1, 0.3, 0.6}` crossed with ridge `{0.1, 1, 10}`.
- Select the single pair with minimum equal-patient/equal-target/equal-
  orientation inner OOF MSE. Exact ties prefer earlier multiplier order, then
  earlier spectral-option order.
- Fit that selected pair once on the outer training rows and predict the held
  patients. There is no second-stage outer-outcome decision.
- Also reconstruct fixed 0.7, 1.0 and 1.4 controls, each choosing only its own
  spectral option in the same inner folds. R13 and archived R18 are identity-
  authenticated controls, not fitting inputs.

## Reporting and interpretation

Report full-24 patient-balanced MSE, p90 patient expected RMSE, all five fold
means, both orientation MSEs, all patient wins/losses/ties, all target deltas,
the selected multiplier/option in every fold and a 10,000-patient-resample
descriptive interval versus fixed 0.7 (seed `20261004`).

This replay is algorithmically nested with respect to the bandwidth choice,
but it is still retrospective repeated development: the same 59 patients and
outer folds were previously observed while the family was developed. It is
therefore not unbiased independent confirmation, selection-corrected evidence
for the wider historical campaign, prospective organ-on-chip validation, a
clinical claim or an official competition score. Whatever the result, the
current bandwidth-0.7 incumbent is not replaced by this evaluation alone.

The first completed attempt is preserved. No bandwidth expansion, fold/target
splice, automatic retry, Protected22/Lib2 access or accepted-Kaggle-entry edit
is allowed.

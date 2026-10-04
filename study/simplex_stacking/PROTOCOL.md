# Patient-balanced simplex spectral stacking

Status before biological fitting: **PREFROZEN**. Ten synthetic and contract tests
passed before this freeze. Any first Lib1 execution, including a code or
environment failure, must be preserved without an automatic scientific retry.

## Falsifiable hypothesis

The bandwidth-0.7 incumbent selects one of ten residual spectral settings by
minimum three-fold inner whole-patient loss. Because several settings are close,
hard selection may add variance. A single global nonnegative simplex combination
of their complete 24-output predictions, learned solely from the same inner OOF
predictions, may improve held-patient mean error, patient breadth, all five outer
folds and p90 without buying another well.

This is stacked generalization, not a new biological interaction claim. The ten
weights are global: they are not target-, patient-, fold-outcome- or orientation-
specific. The method does not average A/B predictions. For each orientation it
combines only the ten models evaluated on that same 64-well orientation.

## Fixed estimator

For each outer-training slice, regenerate the R13 acquisition, own-drug ridge
baseline, scaling and all ten bandwidth-0.7 residual candidates inside each of
the three inner patient folds. Let `p[m,o,i,t]` be candidate `m`'s inner OOF
prediction. Solve exactly over the ten-model simplex:

`min_w sum_patient mean_sample mean_orientation mean_target (sum_m w[m] p[m]-y)^2`

subject to `w[m] >= 0` and `sum_m w[m] = 1`. The solver enumerates all 1023
nonempty simplex faces and solves each equality-constrained least-squares KKT
system. Objective, squared weight norm, then the fixed option order break numeric
ties. There is no temperature, ridge, top-k rule or post-result retry.

Fit the ten residual coefficient matrices once on the entire outer-training
slice and store their weighted sum as one coefficient matrix. Deployment is one
bandwidth-0.7 model with the original single 64-reading input, not a runtime
ensemble and not an extra physical measurement plan.

## Frozen comparison contract

- Population: all 119 Lib1 TRAIN samples from 59 whole patients.
- Targets: all 24 fixed normalized log-dose AUC summaries.
- Budget: exactly 64 distinct physical treatment wells per alternative, 32 per
  plate; A/B squared losses are averaged, prediction vectors never are.
- Folds: unchanged five outer and three inner whole-patient folds and salts.
- Candidate menu: exactly the existing identity setting plus the nine fixed
  fraction/ridge pairs `(0.1,0.3,0.6) x (0.1,1,10)`.
- Direct control: the exact bandwidth-0.7 hard-selection incumbent, independently
  selected from those ten settings within every outer fold.
- Historical controls: additive-1.0, R13 and authenticated archived R18.
- Weighting: equal whole patient, target and deployment orientation.
- Descriptive bootstrap: 10,000 whole-patient resamples, seed 20261004.

Promotion requires every existing clause. Against bandwidth-0.7: strictly lower
MSE, at least 30/59 strict patient wins, all 5/5 outer-fold means favorable,
nonworse p90 and non-equivalent predictions. Against each of R13 and R18: at
least 5% lower MSE, at least 40/59 patient wins, at least 4/5 folds favorable,
nonworse p90 and both orientation MSEs below that reference's expected MSE.

Before result calculation, held-patient predictions are committed to disk. The
independent verifier must recompute metrics and gates, prove each saved simplex
solution satisfies convex KKT conditions, reload each saved model, reconstruct
held-patient predictions and confirm all controls. All 24 target and 59 patient
directions are reported. First-attempt failures are preserved; no automatic
scientific retry or stacking-rule change follows the result.

This remains repeated adaptive development on exposed Lib1 TRAIN. Protected22/
Lib2 is forbidden. A passing result would not be independent validation,
prospective organ-on-chip evidence, clinical benefit, an official competition
score or proof of finalist rank.

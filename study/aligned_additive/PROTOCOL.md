# Residual-alignment-weighted additive kernel (RAW-AK)

**Frozen before fitting, 3 October 2026.** This is one bounded Lib1 TRAIN
development experiment. It is not untouched, selection-corrected, external or
prospective validation.

## Hypothesis

The current additive kernel gives every drug-group Gaussian component its
fixed group-width weight. RAW-AK tests whether fitting-only centered alignment
with the complete 24-target R13 residual field can suppress uninformative group
similarities while preserving the successful additive structure.

For stacked A/B fitting rows, let `z` be the 64 base-standardized purchased
values, `w` the existing equal-patient/equal-orientation weights, `R` the
24-target R13 residuals and `I_j` the two- or three-coordinate group owned by
drug `j`. Define

`G_j(a,b) = exp(-||z[a,I_j]-z[b,I_j]||^2 / (2 |I_j|))`.

Weighted-double-center each `G_j`, then symmetrically weight it by `sqrt(w)` to
obtain `A_j`. Weighted-center `R` and form
`A_R = sqrt(W) R_c R_c' sqrt(W) / 24`. The fitting-only nonnegative alignment
is

`a_j = max(0, <A_j,A_R>_F / (||A_j||_F ||A_R||_F))`.

For `eta > 0`, set `s_j=max(a_j,1e-12)^eta`; for `eta=0`, set every `s_j=1`.
Let `e_j=trace(A_j)` and normalize

`rho_j = s_j * sum_k |I_k| e_k / sum_k |I_k| e_k s_k`.

The candidate kernel is

`K(z,z') = z z' + sum_j |I_j| rho_j G_j(z,z')`.

Every `rho_j` is nonnegative, and the nonlinear component preserves the
incumbent's fitting-row centered diagonal energy. A nonfinite or near-zero
normalization denominator is a hard error. On deliberately constant invented
fixtures only, zero residual-kernel energy deterministically falls back to
equal weights. `eta=0` must reproduce the incumbent `AdditiveKernel`.

## Fixed menu and containment

There are exactly 28 candidate configurations, ordered for deterministic ties:

1. unchanged R13 identity prediction;
2. increasing `eta` in `{0, 0.5, 1}`;
3. increasing spectral fraction in `{0.1, 0.3, 0.6}`;
4. increasing residual ridge in `{0.1, 1, 10}`.

One common option is selected by pooled equal-patient/equal-target error in the
unchanged three inner whole-patient folds. Acquisition, base ridge, scaling,
residuals, alignments, kernel centering and coefficients are rebuilt inside
every fitting partition. No target-specific weights or penalties, acquisition
changes, interactions, PC components, residual calibration, replicate
reweighting, sample exclusion, clipping, blending, extra exponents or retry are
allowed after outcomes.

If the complete held-patient RAW-AK predictions match the separately selected
additive predictions within absolute `1e-12`, RAW-AK is explicitly rejected as
additive-equivalent even if floating-point roundoff would otherwise create a
nominal strict win. Identity-selected outer folds still serialize their base
model state with an explicit identity marker so the no-refit audit covers every
held-patient prediction.

The task remains exactly 119 Lib1 samples, 59 whole patients, 24 original
unclipped targets, five outer patient folds, and 64 distinct treatment wells per
A/B alternative with 32 wells per plate. A/B squared losses are averaged;
predictions are never averaged. The unchanged R13 acquisition is used. No
Protected22, Lib2, external-response, bridge, genotype or original-workbook
input is permitted.

## Controls and decision

The same execution must reproduce within absolute `1e-12`:

- R13 MSE `0.001144858681382854`;
- S2 MSE `0.0010701439454817465`;
- additive incumbent MSE `0.001060552730112811`.

Before historical R18 comparison, new held-patient predictions are saved and
hashed. Against additive and S2, RAW-AK must have strictly lower MSE, at least
30/59 strict patient wins, at least 3/5 favorable folds and nonworse p90. It
must also pass every original rule against R13 and R18: at least 5% lower MSE,
at least 40/59 wins, at least 4/5 favorable folds, nonworse p90, and both
orientation MSEs below that reference's expected MSE. Failure of any clause
retains additive. A selected `eta=0` that reproduces additive is a rejection,
not a tie-promoted model.

Report every patient/target regression and a descriptive 10,000-resample
whole-patient interval using seed `20261003`. The interval is not
selection-corrected.

## Pre-fit and post-fit checks

Before fitting, invented tests must cover explicit weighted centering,
Frobenius alignment, energy normalization, positive semidefiniteness, group
permutation, query batching, nonfinite rejection, degenerate residual fallback
and `eta=0` parity. During fitting, assert patient separation, exact physical
well counts and masking invariance. After prediction commitment, a separate
verifier must recompute patient/fold/target/orientation metrics, gates,
alignments, weights and selected-model predictions without calling the fitting
procedure. Failures and adverse slices are preserved.

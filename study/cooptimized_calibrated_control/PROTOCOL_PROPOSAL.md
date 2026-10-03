# Proposed comparator audit: co-optimized calibrated interpolation

3 October 2026. **Preparation only: no response arrays opened, fits run, or predictions generated for this review.** This is a bounded, repeatedly exposed Lib1 development comparator audit, not independent confirmation, an acquisition theorem, or a submitted model change. Freeze a separate execution receipt and source hashes before any future run.

## Decision and distinction

Proceed only as one stronger-comparator audit. Test whether a scalar, own-drug interpolation summary with training-learned affine calibration and jointly selected native doses accounts for the incumbent's reconstruction performance. It is scientifically distinct from the rejected `study/multioutput_acquisition` experiment:

| Property | Rejected covariance sweep | This proposed control |
| --- | --- | --- |
| Predictor | R13 plus additive multioutput residual kernel | One own-drug interpolated scalar, optionally affine-calibrated |
| Acquisition objective | Fitting regularized multioutput linear covariance proxy | Actual calibrated squared loss on inner-held patients |
| Search | One greedy target sweep from R13 | Exhaustive 2/3-dose candidates; exact separable allocation for each shared calibration option |
| Upgrade ownership | Preserve R13's same 16 upgraded targets | Choose exactly 16 upgrades from the inner-CV criterion |
| Cross-drug response features | Allowed by kernel and proxy | Forbidden |
| Interpretation | Attempt to improve incumbent acquisition | Test whether a simpler, fairly optimized comparator removes an apparent advantage |

Both use standard methods and exposed data. Replacing the old sweep's name, step order, ridge penalty, or kernel while keeping its objective would not be this experiment. No new kernel, acquisition blend, slope grid, or follow-up sweep is proposed.

## Frozen scientific and physical contract

- Exactly the existing 119 Lib1 samples, 59 whole patients, 24 original unclipped target summaries, original target order, patient identities, five outer folds and three inner folds. Use `evaluate.SALT + '|outer'` and `evaluate.SALT + f'|inner|{f}'` with the existing `patient_folds` implementation.
- Authenticate the exact authorized TRAIN source and catalog through the existing adapter. No Lib2, protected records, external responses, original workbook, new response exclusions, or imputation. The source route must be explicit and hash-locked; no fallback.
- Keep every source-native dose and the fixed target integration bounds. Metadata inspection found 164 native identities; the per-target dose-count histogram is `{3:1, 4:2, 6:6, 7:3, 8:12}`. This gives exactly 1,410 size-2/3 subsets. Do not trim this universe using measured values or target performance.
- Select two native doses for eight targets and three for sixteen targets: 64 distinct treatment wells per alternative deployment, 32 from each source plate. This count does not include normalization/control/preparation overhead and is not a realized total-assay cost claim.
- Within each target, sort chosen native doses by exact decimal concentration, then native ID. Alternate plate positions. For the sixteen upgraded targets, lexicographically sort target IDs and alternate the starting plate; two-dose targets start at plate 0. Orientation B flips every plate choice in A. Thus each plate receives `8 + 8*2 + 8*1 = 32` wells. Audit actual physical well IDs, not just coordinate counts.
- A/B are alternative 64-well deployments. Average their squared losses, never prediction vectors or purchased readings. One shared calibration coefficient pair per target applies to both orientations. No orientation selection after observing query responses.

The target remains the original measured two-plate summary. Purchased values may contribute to it. This is measured-summary reconstruction, not recovery of noiseless biology or an independent repeat.

## Readout and affine family

For target j and native subset S, use the unchanged `interpolation_policy.integration_weights` to obtain the normalized log-dose trapezoid with constant tails on the fixed target bounds. Denote the resulting scalar readout for row i and orientation o by t(i,j,S,o). Weights depend only on dose metadata. A zero integration weight does not make its physical well free: retain the exact prescribed budget.

Use exactly six common options in this tie order: `identity`, `0.0` (OLS), `0.01`, `0.1`, `1.0`, `10.0`. No target-specific penalty selection. Identity returns t unchanged. For each other option lambda, fit one intercept and standardized scalar slope per target/subset using only the current fitting patients and both orientations.

If there are P fitting patients and patient p contributes n_p sample rows, assign each orientation-row weight q(i,o)=1/(2*P*n_p). Let weighted means be mu_t and mu_y, and let s=max(sqrt(sum q*(t-mu_t)^2), 0.05). Set z=(t-mu_t)/s, v=sum q*z^2, c=sum q*z*(y-mu_y), and b=c/(v+lambda). Use b=0 when v+lambda<=1e-24, matching the existing calibration implementation. Predict `mu_y + b*(t-mu_t)/s`.

No clipping, monotonicity constraint, slope-sign rule, dose-level curve fit, other-drug feature, residual model, or calibrated A/B average is added. Slopes can be negative. Accordingly, the calibrated output is a learned affine summary, not necessarily a physically monotone dose-response curve. This is a constrained own-drug linear estimator: its purchased-value coefficients are a scalar multiple of fixed interpolation weights. It makes no new algorithmic novelty claim.

## Exact outer/inner procedure

For outer fold f, quarantine its held patients. All of the following selection uses only the remaining outer-fitting patients F.

1. Enumerate the metadata-defined 1,410 subsets before reading fitting outcomes. For every target/subset/option and each of the existing three inner folds, fit its calibration on the inner-fitting patients. Calculate predictions for both orientations of the inner-held patients. The candidate subset is fixed metadata; there is no outer-fitted acquisition, scale, intercept or slope reused inside these fits.
2. For each target/subset/option, pool its out-of-fold errors across F. Define R(j,S,lambda) as the mean over patients in F of that patient's mean across sample rows of `(error_A^2 + error_B^2)/2`. Do not equally average the three fold means; fold sizes may differ.
3. For each common option, independently minimize R over size-2 subsets and size-3 subsets for each target. Break exact floating-point score ties by the ordered tuple of native IDs. Let the two minima be R2_j and R3_j. Upgrade exactly the sixteen targets with largest `R2_j - R3_j`, ties by target ID. Negative upgrade gains do not authorize fewer than 64 wells.
4. The option score is `[sum_j R2_j - sum_upgraded (R2_j-R3_j)]/24`. Select the lowest score, ties in the six-option order. Save the complete candidate score tables, chosen dose identities, upgrade assignment and option. This is exact minimization of the declared inner-CV criterion, not a global population-risk optimum.
5. Refit only the selected subset's calibration for each target on all F, retaining the selected common option and metadata readout. Freeze/hash that fold's plan and model before querying its outer-held patients. Predict each held patient separately for A and B from exactly that orientation's 64 purchased values.
6. Repeat for the original five outer folds. Commit/hash all complete outer prediction arrays before loading any saved historical prediction reference for score comparison. No outer error, saved old outer prediction or earlier fold score influences later plans, options or retries.

This is ordinary nested selection of a finite model class. A third split level is not required to evaluate this procedure on the outer-held patients: subset and option selection are both explicitly performed by the inner-CV table. **The minimum inner-CV score is selection-biased and is not a validation result.** In contrast, choosing the doses on all outer-fitting outcomes and then reporting calibration-only inner validation of that fixed plan would contaminate the claimed inner held-out selection criterion.

The expected-loss symmetry is essential to separability. Flipping a target's starting plate merely exchanges its two orientation terms; fitting both with equal mass leaves its coefficients and loss unchanged. This permits the final 32/32 balancing assignment without changing any target score. Cross-drug predictors, separate A/B coefficients, unequal orientation weights, or choosing a favorable orientation break this proof and are outside the protocol.

This run needs 5*3*1,410*5 = **105,750 scalar closed-form calibration fits**, plus selected refits. The same fitting moments can serve all five penalties. It is a fixed finite calculation, not a GPU or model-API search. No automatic retry or expanded option menu is allowed after any outer scoring.

## Controls and interpretation

Retain three comparator arms with no favorable-result selection:

1. **Raw optimized interpolation:** unchanged `interpolation_policy.plan_panel` on each outer-fitting slice. The identity option's inner-OOF scores aggregate to the same outer-fitting raw losses, so its plan must reproduce this control under the same tie arithmetic. If final plans disagree only because of roundoff, resolve using the reference arithmetic before response scoring; do not choose the better outer outcome.
2. **Calibrate the original raw plan:** within every inner-fitting split rebuild the original raw-optimized plan, fit each of the same six calibration options, and score inner-held patients. Select one shared option by pooled patient/target loss, then rebuild that original plan on the full outer-fitting slice and refit its calibration. This isolates the straightforward calibration control from acquisition co-optimization. Do not calibrate a plan first optimized using the inner-held patients.
3. **Joint control:** the exact procedure above. It contains raw interpolation as an option but is not guaranteed to outperform it on outer-held patients.

Compare all three with authenticated aligned R13, S2 and current additive outer predictions after commitment. Do not rerun or retune the failed multioutput sweep. Require exact sample/patient/target/fold identity and the existing reference MSE tolerance 1e-12. Existing aggregate numbers are authentication targets, never fitting inputs.

Primary report: equal-patient/equal-target mean A/B squared loss. Also retain all per-target losses, strict patient wins/ties/losses, five fold means, p90 patient expected RMSE, both orientation means, selected subsets/options and all regressions. Use a descriptive paired whole-patient bootstrap, 10,000 replicates, seed 20261003; it cannot undo the repository's repeated adaptive development. Do not call overlapping intervals equivalence.

This audit remains worth reporting if the simple control wins. An additive advantage over this control is evidence against this particular comparator, not proof that cross-drug information or nonlinearity is necessary: their acquisition policies also differ. If promotion of the simple model is later proposed, require all existing successor clauses against additive and S2, plus every original R13/R18 clause; do not weaken those gates. No model promotion, public artifact replacement or submission is authorized by this proposal.

## Required preflight and no-go conditions

Before any authorized fitting, freeze code, catalog/source hashes, dependencies, all salts, menu/ties, report fields and these rules. On fictional arrays only, independently verify:

- Scalar calibration against direct weighted least squares/ridge, including patient duplication weighting, zero variance, the 0.05 floor and negative slopes.
- Integration against a direct trapezoid implementation; query batching and native-order invariance; no changed endpoint or clipping.
- Exact top-16 allocation versus full enumeration on a tiny fictional target/budget analogue; shared-option selection versus explicit summation; A/B swap invariance; forced negative-gain upgrades.
- Inner patient isolation, outer quarantine and source-row alignment. Poison unused outer labels/values and show fit/selection invariance. Every model receives only its current fitting indices.
- Exactly 64 distinct physical IDs and 32/plate for each orientation; unpurchased-value NaN masking invariance of inference. Missing any required value fails closed; no baseline recovery is counted as primary prediction.
- Identity-plan/reference parity, immutable prediction commitment, explicit-loop patient/fold/orientation score verification, and saved-model reload prediction parity.

Do not execute if the exact source, original patient partition, target bounds, identity mapping or baseline receipts cannot be authenticated. Stop on incomplete/nonfinite data, cost failure, plan/scale/coefficients fitted across a held-patient boundary, a control mismatch, or inability to isolate source-legal input access. Preserve the failed attempt; correction requires an explicit bug-only amendment and must not turn into result-driven search.

No-go as a scientific successor if it merely repeats the failed covariance proxy, adds cross-target features or reopens a kernel family under this label. No-go for claims of independent generalization, actual assay savings, biological effects, prospective lab performance or a new optimization invention. No new external/protected data is needed or authorized. A valid negative comparator result closes this bounded audit; it does not authorize another dose/calibration family.

## Source inspection anchors

This review read repository source/protocols and the explicitly input-only catalog; it did not open response arrays, result JSONs or historical prediction archives. The prescribed future input adapter opens authorized TRAIN outcomes, which is separate from this preparation.

- `study/audits/interpolation_policy.py`: unchanged integration and raw exact 2/3 allocation; SHA-256 `ce16748d17e4d214f5b75bfb5665420b91fca8bbe4da5d0344c126f5deeb1a12`.
- `study/calibrated_control/calibrated_control.py`: existing affine menu, patient weights and scale floor; SHA-256 `295abb78dc19931b091829898d293d3407812dc83e599a977a506feff7c86f55`.
- `study/multioutput_acquisition/PROTOCOL.md`: rejected study's distinct contract; SHA-256 `2d1458a7db6e2d0fea42d38fcb1a304039bdb2ab46f93c57da2d0d256b6a8593`.
- `study/multioutput_acquisition/global_acquisition.py`: fixed-upgrade, one-sweep covariance proxy; SHA-256 `09080dbc291ae22fca4683feca6250291ae80e7bd1b6b593db83914e48fcb437`.
- `study/TRAIN_CATALOG.json`: source-native input metadata and fixed target bounds; SHA-256 `84eae3976307448ac696852d39d1b2376cce479d8af5e386ce04097020deff5e`.

Implement in a new directory without editing the frozen engine or incumbent. No runner or tests have been added or executed by this source-only preparation.

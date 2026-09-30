# DosePilot stromal-context stress test — frozen protocol

Frozen on 30 September 2026 before any RLU outcome field in the source file was decoded.

## Question
Does the sparse own-drug acquisition/reconstruction design, fitted only on distinct monoculture organoid IDs, retain an advantage over an independently optimized interpolation policy when evaluated once on matched autologous tumor-CAF cocultures from held-out organoid IDs?

This is a stress test of a design pattern under a stromal context shift. It is not direct validation of the submitted 24-head R13 model, not an organ-on-chip hardware experiment, and not a clinical-effect study.

## Source and response-blind split
Source file SHA-256: `f9a9a51fd77ae1a5b19ad71fc236ce446223b3c2fcc66631ab304ab69bec78f0`.
Only the first seven tab-separated metadata fields have been decoded so far. The RLU outcome column and later columns remain unopened.

Confirmation organoids are the response-blind set with a same-numeric, non-N fibroblast ID and metadata-complete mono/coculture grids for all four drugs:
O01, O05, O06, O07, O11, O13, O14, O15, O17, O19, O20, O22, O25, O26, O27.

Development is restricted to different organoid IDs with metadata-complete monoculture grids:
O02, O03, O04, O09, O10, O12, O16, O18, O21, O23, O24, O28, O29.

O30 and all other rows are excluded before outcomes because they do not satisfy the frozen metadata split. No confirmation organoid may enter development fitting or selection.

## Fixed endpoint and normalization
Drugs: 5-FU, Gef, Oxa, SN-38. The source's own concentration labels are retained; no unit conversion is invented.

For each organoid / condition / drug, raw luminescence is collapsed by arithmetic mean within each source concentration label. DMSO mean is the denominator. Normalized viability at a positive dose is mean(RLU at that dose) / mean(RLU at DMSO). Values are not clipped.

Gefitinib concentration 0.0 and all DMSO rows are controls, not positive-dose target nodes. The target is normalized trapezoidal AUC over log concentration across all seven positive native dose labels for that drug.

A selected condition is usable only if every positive-dose group and DMSO has at least two finite, nonnegative RLU replicates and DMSO mean is strictly positive. The 13 development organoids must all satisfy this rule or development stops. All 15 confirmation organoids must satisfy it in both matched coculture and monoculture or confirmation stops. There is no post-outcome sample deletion, imputation, retry, or shrinking of the confirmation cohort.

## Sparse design
There are 28 positive dose-level readouts per condition (4 drugs × 7 doses). The sparse budget is 11 dose-level readouts: two doses per drug plus exactly three third-dose upgrades. This approximately preserves DosePilot's measurements-per-target ratio, but these are replicate-averaged dose readouts, not physical-well counts.

For each fitting set, size-2 and size-3 subsets are exhaustively scored per drug using the original covariance residual proxy with allocation regularization alpha = 0.1. The three largest fitting-only upgrade gains receive a third dose.

The prediction model is an own-drug linear ridge head with an unpenalized intercept. Feature mean/scale are fit on the fitting rows only, with scale floor 0.05. One shared ridge penalty is selected from {0.01, 0.1, 1, 10}.

## Development selection
Development uses leave-one-organoid-out cross-validation across the 13 development organoids. For every held-out organoid and every ridge option, acquisition planning, scaling and fitting are rebuilt from the other 12 organoids. The shared ridge penalty is the option with lowest pooled development OOF MSE; ties use the earlier listed penalty.

The final learned plan and model are then fitted once on all 13 development organoids with the selected penalty and frozen before confirmation outcomes.

The comparator is constant-tail piecewise-linear interpolation in log concentration. It independently optimizes its own two-/three-dose subsets and three upgrades using development fitting outcomes under the same 11-readout budget. It has no fitted readout coefficients.

A development-mean target vector is retained as a sanity baseline but is not part of the promotion gate.

## One-shot confirmation
Primary confirmation is matched autologous tumor-CAF coculture for all 15 frozen confirmation organoids. No parameter, dose subset, normalization rule, ridge penalty, threshold, or metric may be changed after confirmation access begins.

Secondary, prespecified diagnostic: evaluate the same frozen learned model and interpolation policy on monoculture from the same 15 organoids. This separates held-out-organoid generalization from the additional stromal context shift; it does not replace the primary coculture endpoint.

Primary error is mean squared error averaged equally across the 15 organoids and four targets. Patient language is prohibited unless an independent source mapping proves organoid-to-patient identity.

## Promotion gate
All four conditions must pass:
1. learned coculture MSE is strictly lower than optimized-interpolation coculture MSE;
2. learned has strictly lower four-target MSE for at least 9 of 15 confirmation organoids;
3. learned per-drug MSE is nonworse for at least 3 of 4 drugs;
4. learned p90 confirmation-organoid RMSE is nonworse than interpolation.

Failure of any component means the stress-test gate fails. The gate will not be changed after outcomes are opened.

## Integrity and interpretation
The development parser is forbidden from decoding RLU values for confirmation IDs or coculture rows. The confirmation parser writes an access-start marker before decoding any confirmation RLU value.

The first confirmation execution is terminal evidence. A software failure after outcome access is preserved; there is no automatic retry. Any later repair must be labeled post-access and cannot become a fresh blinded confirmation.

The learned/interpolation comparison is about sparse reconstruction under a new biological context. It does not validate original R13 fitted weights, original two-plate coverage-vs-replication causality, clinical treatment choice, calibrated uncertainty, reagent savings, or prospective microfluidic/OoC performance.

Source workbooks/raw files are not to be published by DosePilot. Public release may include original code, invented tests, fixed protocol, hashes and aggregate metrics only.

Metadata evidence frozen before this protocol:
- METADATA_ONLY_002.json
- METADATA_PAIRS_003.json
- METADATA_SPLIT_004.json

The first metadata script failure is preserved as METADATA_FAILURE_001.json; it occurred before outcome access and changed only blank-label handling in the metadata audit.

## Descriptive stability summaries
After the fixed primary metrics and gate are computed, a fixed-seed 10,000-resample organoid bootstrap will summarize the mean primary MSE difference (learned minus interpolation). This interval is descriptive and not a clinical-effect confidence interval or a gate component.

The confirmation report will also show the candidate and interpolation change from held-out monoculture to matched coculture MSE. This is a prespecified domain-shift diagnostic only; no causal CAF effect is inferred from the prediction-error difference.
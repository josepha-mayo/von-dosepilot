# von DosePilot

## 24 response summaries from 64 traceable treatment wells

Joseph Ayanda | Model & Algorithm | Current submission report | 6 October 2026

> DosePilot freezes a physical assay layout before responses arrive, validates every purchased drug-dose-plate identity, and reconstructs 24 fixed research summaries with an explicit missing-data and evidence contract.

| Current verified development result | Value |
|---|---:|
| Patient-balanced full-24 MSE | 0.001042745722 |
| Improvement versus bandwidth-0.7 | 1.4674% |
| Improvement versus original R13 | 8.9193% |
| Patient wins versus bandwidth-0.7 | 40 / 59 |
| Favorable folds versus bandwidth-0.7 | 5 / 5 |
| p90 patient RMSE | 0.037419696 |
| Physical treatment wells | 64 per deployment |

The orientation-specific control-quality rank-1 model is the **lowest verified Lib1 development point estimate** currently recorded. It is repeated adaptive development, not independent confirmation, an official competition score, or a clinical result.

Repository: https://github.com/josepha-mayo/von-dosepilot

Live fictional-data demonstration: https://von-dosepilot.netlify.app

<!-- pagebreak -->

# Executive summary

## The decision DosePilot makes

Sparse screening is a physical measurement problem before it is a prediction problem. Each feature corresponds to a drug, an exact dose, a source plate, and a treatment well. DosePilot commits a 64-treatment plan before responses arrive, then reconstructs 24 normalized log-dose AUC summaries.

The development contract is deliberately strict:

- 119 organoid samples are grouped into 59 whole patients.
- The endpoint is fixed for all 24 drugs.
- Each A or B deployment uses exactly 64 distinct treatment wells, 32 per source plate.
- Every sample from one patient remains on the same side of inner and outer splits.
- A and B are scored separately; their losses are averaged.
- A/B prediction vectors are never averaged into a hidden 128-well ensemble.
- Planning, scaling, fitting, and inner spectral selection stay inside fitting splits.

## What changed on 6 October

The current candidate preserves the 64-well treatment acquisition and the bandwidth-0.7 residual geometry, then uses standard plate-control summaries to estimate a small shared target-deviation mode.

Orientation B uses an 11-column quality basis containing control range, negative/positive control level, and negative/positive control variation. Orientation A uses a more conservative seven-column level basis that omits the CV channels. Both corrections are rank 1 and deliberately damped.

The result is **0.001042745722 MSE**, 1.4674% below bandwidth-0.7 and 8.9193% below R13. Against bandwidth-0.7 it wins 40/59 patients, all 5/5 outer folds, p90, and 19/24 target-average errors.

## What is not demonstrated

The same 59-patient development population has been reused across many research rounds. Patient grouping prevents within-run patient leakage, but repeated inspection means the current point estimate is not untouched validation.

The immediate predecessor is already very close: 0.001043179589. The current candidate is only 0.0416% lower and wins 3/5 folds versus that immediate predecessor. The report therefore does not claim uniform incremental superiority.

Protected22 is closed and exposed; its full primary was not estimable. No Protected22 response was used to develop or verify the current candidate.

<!-- pagebreak -->

# Endpoint and physical budget

## Fixed response target

Each of the 24 outputs is the arithmetic mean of two identified source-plate trapezoidal AUCs over log concentration. Supplied normalized viability values are used without clipping.

The output is not IC50, a drug rank, or a clinical-response label.

## Sixty-four treatment wells

The retrospective source profile contains 416 eligible target-treatment measurements per sample across two plates. The frozen plan selects two native doses for every target and allocates a third-dose upgrade to 16 targets:

```text
24 x 2 + 16 x 1 = 64 treatment wells
```

Each alternative deployment has 32 p1 and 32 p2 treatment wells. Standard vehicle/viability controls are separate assay resources and are not counted as treatment wells.

The 64/416 ratio is a **treatment-measurement count** comparison. It is not a demonstrated 84.62% reduction in real laboratory cost, material, or time.

| Frozen schedule property | A | B |
|---|---:|---:|
| Treatment wells | 64 | 64 |
| p1 treatment wells | 32 | 32 |
| p2 treatment wells | 32 | 32 |
| Two-dose targets | 8 | 8 |
| Three-dose targets | 16 | 16 |

A and B are complete alternative 64-well layouts. Their prediction vectors are never combined.

<!-- pagebreak -->

# Model

## Stage 1 - training-contained acquisition

For each drug, the allocator compares two-dose and three-dose native subsets with a fitting-only covariance criterion. Sixteen targets receive a third-dose upgrade. Acquisition is recomputed inside fitting splits.

## Stage 2 - own-drug ridge

Each target has an unpenalized-intercept ridge head that sees only the purchased measurements for that drug. One shared ridge penalty is selected inside patient-grouped inner folds.

## Stage 3 - cross-drug residual correction

The bandwidth-0.7 additive model fits residual structure with grouped Gaussian kernels plus a linear component. Ten residual spectral options are evaluated in inner patient folds.

## Stage 4 - control-quality rank-1 calibration

The current candidate uses standard plate-control summaries, not additional treatment wells.

**Orientation B quality basis (11 features):**

- control range mean and half-difference;
- squared range mean;
- negative-control log-median mean and half-difference;
- positive-control log-median mean and half-difference;
- negative-control CV mean and half-difference;
- positive-control CV mean and half-difference.

A fitting-only ridge regression is reduced to its leading target-deviation mode, then applied at replacement strength **1/3**.

**Orientation A level basis (7 features):**

The same range and control-level features are used, but the CV channels are omitted. The rank-1 replacement strength is **1/9**.

The asymmetry is intentional. Orientation A's richer quality basis was noisier in crossfit diagnostics, while B benefited from the full quality basis.

Rank 1 is also intentional. Recorded rank-depth diagnostics show ranks 2, 3, and 4 all worsen the held-patient MSE.

<!-- pagebreak -->

# Same-task development results

| Complete procedure | Patient-balanced MSE | Interpretation |
|---|---:|---|
| R13 own-drug reconstruction | 0.001144858681 | historical baseline |
| R18 exploratory candidate | 0.001141404811 | historical reference |
| S2 spectral residual | 0.001070143945 | superseded |
| Additive group kernel, bandwidth 1.0 | 0.001060552730 | predecessor |
| Bandwidth-0.7 additive | 0.001058275042 | public operational baseline |
| Standard-control meanquad/plate interaction v2 | 0.001045585078 | adaptive development |
| Control rank-1 target deviation | 0.001044448281 | adaptive development |
| Orientation-A auxiliary rank-1 | 0.001043179589 | immediate predecessor |
| **Orientation-specific control-quality rank-1** | **0.001042745722** | **lowest verified development point estimate** |

## Breadth versus bandwidth-0.7

| Metric | Current | Bandwidth-0.7 |
|---|---:|---:|
| MSE | 0.001042745722 | 0.001058275042 |
| p90 patient RMSE | 0.037419696 | 0.037894285 |
| Orientation A MSE | 0.001100608798 | 0.001104752162 |
| Orientation B MSE | 0.000984882646 | 0.001011797922 |

The current model wins **40/59 patient means**, all **5/5 outer folds**, and **19/24 target-average errors** versus bandwidth-0.7.

The five regressing target averages are Afatinib, AZD7762, LCL161, Regorafenib, and Trametinib.

## Historical screens

Versus R13: **8.9193% lower MSE, 49/59 patient wins, 5/5 folds, 22/24 target-average wins**.

Versus authenticated R18: **8.6437% lower MSE, 50/59 patient wins, 5/5 folds, p90 nonworse**, and both orientation-wide MSEs remain below the reference expected MSE.

## Immediate-predecessor honesty check

Versus the 0.001043179589 immediate predecessor, the current point estimate is only **0.0416% lower**, with **32/59 patient wins, 27 losses, and 3/5 favorable folds**. p90 remains nonworse.

# Falsification and verification

## Exact replay

The frozen verifier reports:

| Check | Result |
|---|---:|
| Status | PASS_FLOATING_REPLAY |
| Base model refit | false |
| Calibration recomputed | true |
| Held-target predictions reconstructed | 5,712 |
| Maximum prediction difference | 2.22e-16 (fresh Windows replay) |
| Prediction tolerance | 5e-16 |
| Calibration folds checked | 5 |
| Protected22 access | false |

The saved candidate prediction SHA-256 is bound in the evidence receipt.

## Extensions that failed

The project keeps negative branches visible.

- rank-2, rank-3, rank-4 control-quality models: all worse than rank 1;
- robustized quality bases: worse;
- target-gated quality corrections: worse;
- wider bandwidth 1.4: rejected;
- cross-patient median bandwidth: lower point mean but only 4/5 folds, rejected;
- simplex spectral stacking: all inner objectives improved but held-patient mean/breadth/tail worsened;
- isotonic paid features: rejected.

This matters because repeated development can manufacture attractive decimals. DosePilot keeps the failed gates and does not splice targets or folds after seeing outcomes.

<!-- pagebreak -->

# External evidence and prospective boundary

## Protected22

The frozen Lib2 primary required 19,642 cells across 61 PDOs, 31 patients, and 22 targets. Five required cells were unavailable, so the full primary is **NOT_ESTIMABLE**. A conditional complete-patient diagnostic exists, but it is not the primary, and prior exposure prevents an untouched-confirmation claim.

All 61 PDOs and 31 patients are treated as exposed. No Protected22 value was used to build the current Lib1 successor.

## Separate external adaptations

A matched-CAF design adaptation passed its own frozen gate on a different cohort and endpoint panel. FORECAST-1 and eLife adaptations did not fully pass their preset gates.

These are design-level external studies. They do not directly validate the current fitted 24-output Lib1 weights.

## Correct next experiment

The scientifically strong next step is not another adaptive Lib1 sweep. It is a preregistered, patient-separated prospective or untouched assessment in which device identity, QC, missingness, comparator, output denominator, and success gates are frozen before responses are collected.

<!-- pagebreak -->

# Reproducibility and software

The repository separates three kinds of evidence:

1. **Biological development evidence:** grouped held-patient results and aggregate receipts.
2. **Numerical reproducibility:** frozen replay of saved candidate predictions without refitting the base model.
3. **Operational software:** an identity-bound fictional lifecycle that demonstrates commit, missing-input withholding, recovery, and prediction.

Current candidate artifacts:

```text
evidence/orientation_specific_control_quality_rank1_20261006.json
study/orientation_specific_control_quality_rank1/PROPOSAL.json
study/orientation_specific_control_quality_rank1/PROTOCOL.json
study/orientation_specific_control_quality_rank1/FREEZE.json
study/orientation_specific_control_quality_rank1/run_study.py
study/orientation_specific_control_quality_rank1/verify_study.py
```

The existing durable fictional lifecycle still represents the bandwidth-0.7 operational baseline. The newer calibration layer has not been silently substituted into that older demo. The separation is explicit so a reviewer can distinguish an accuracy experiment from a completed product-runtime migration.

The public repository excludes patient arrays, fitted biological weights, and protected responses.

# Claim boundary

DosePilot currently supports:

- a fixed 64-treatment acquisition contract;
- a lowest verified Lib1 adaptive-development MSE of 0.001042745722;
- broad improvement versus bandwidth-0.7;
- exact frozen numerical replay;
- transparent adverse slices and negative experiments;
- an executable fictional operational workflow;
- a clear prospective handoff.

It does **not** establish clinical utility, realized laboratory savings, prospective organ-on-chip performance, independent validation of the current fitted weights, an official competition score, or a guaranteed outcome.

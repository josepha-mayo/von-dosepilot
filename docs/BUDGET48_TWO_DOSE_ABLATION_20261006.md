# DosePilot 48-vs-64 treatment-well ablation

## Why this exists

DosePilot's deployment budget is **64 treatment wells**. The natural cheaper alternative is 48 wells: two native doses for each of 24 targets. This post-hoc ablation asks whether the sixteen fitting-only third-dose upgrades in the frozen 64-well R13 procedure actually buy measurable held-patient accuracy.

The protocol and implementation were committed publicly as `fd4564a` **before the first real-data outcome was opened**. The result is reported regardless of direction.

## Frozen comparison

Both arms use the same public reconstructed Lib1 TRAIN population, 5 outer whole-patient folds, 3 inner whole-patient folds, own-drug ridge family, four shared ridge penalties, patient weighting, and separate A/B orientation losses.

- **48-well arm:** exact fitting-only best two native doses for every target, 24 p1 + 24 p2 wells per deployment.
- **64-well arm:** the same best-two base plus the sixteen largest fitting-only third-dose upgrades, 32 p1 + 32 p2 wells per deployment.

No successor calibration, additive kernel, spectral model, or target dropping is used in this ablation.

## Result

| Metric | 48 wells | 64 wells |
|---|---:|---:|
| Patient-balanced full-24 MSE | 0.001543272538 | **0.001144858681** |
| p90 patient RMSE | 0.046738041 | **0.041107825** |
| Treatment wells | 48 | 64 |

Adding 16 wells is a **33.3% increase in treatment-well count** and yields a **25.82% MSE reduction** plus a **12.05% p90 patient-RMSE reduction** in this frozen own-drug comparison.

Breadth is strong:

- **58/59 patients** favor 64 wells;
- **5/5 outer folds** favor 64 wells;
- **21/24 target-average errors materially improve**;
- the other three targets are numerical/material ties at tolerance 1e-15;
- **zero material target regressions**.

The prespecified 100,000-resample whole-patient bootstrap for 64-minus-48 mean loss is **[-4.57e-4, -3.44e-4]**, entirely below zero.

The 64-well arm reproduces historical R13 to **4.34e-19 absolute MSE difference**, which is the main implementation-integrity gate.

## Interpretation

This does not prove that 64 is the globally optimal laboratory budget. It does answer a narrower and important design question: within the already-frozen R13 acquisition family, the sixteen third-dose upgrades are not cosmetic. Removing them causes a large and broad held-patient accuracy loss.

The result therefore makes the 64-well design interpretable as a measured budget/accuracy choice rather than an arbitrary round number.

## Boundary

This is repeated adaptive Lib1 development and a retrospective ablation, not independent validation, clinical evidence, or a prospective cost-effectiveness study. The 48-well rule was frozen before this outcome, but the underlying Lib1 population had already been repeatedly inspected during DosePilot development.

No Protected22 response was accessed. No patient-level loss rows or OOF prediction arrays are published.

Machine-readable aggregate evidence: `evidence/budget48_two_dose_ablation_20261006.json`

Frozen study: `study/budget48_two_dose_ablation/`

# DosePilot control-quality successor - 6 October 2026

## Decision

The **orientation-specific control-quality rank-1** model is the lowest verified patient-balanced full-24 development MSE currently recorded for DosePilot:

| Complete procedure | Patient-balanced MSE | p90 patient RMSE |
|---|---:|---:|
| Original R13 | 0.001144858681 | 0.041107825 |
| S2 spectral residual | 0.001070143945 | - |
| Additive kernel, bandwidth 1.0 | 0.001060552730 | 0.038073112 |
| Bandwidth-0.7 additive | 0.001058275042 | 0.037894285 |
| Standard-control meanquad/plate interaction v2 | 0.001045585078 | 0.037654315 |
| Control rank-1 target deviation | 0.001044448281 | 0.037532707 |
| Orientation-A auxiliary rank-1 calibration | 0.001043179589 | 0.037477260 |
| **Orientation-specific control-quality rank-1** | **0.001042745722** | **0.037419696** |

This is **repeated adaptive development on the same 59-patient Lib1 population**, not independent validation, an official competition score, or clinical evidence.

## What changed

The physical treatment acquisition does **not** change: each A or B deployment still uses exactly **64 identified treatment wells, 32 per source plate**, and A/B losses are evaluated separately.

The successor adds a low-rank calibration layer using standard plate-control summaries that are already part of assay QC rather than additional treatment wells.

- **Orientation B:** rank-1 target-deviation calibration from an 11-column quality basis: control range mean/half-difference/range-squared, negative-control log-median mean/half-difference, positive-control log-median mean/half-difference, and negative/positive control-CV mean/half-difference. Replacement strength: **1/3**.
- **Orientation A:** a deliberately smaller seven-column level basis that omits the CV channels, also rank 1. Replacement strength: **1/9**.
- Upstream acquisition, the 64-well treatment budget, patient grouping, bandwidth-0.7 geometry, and the existing meanquad/plate-interaction stack remain fixed.

The rank constraint matters. A recorded rank-depth diagnostic found rank 1 best; ranks 2-4 all produced higher MSE. Robustized bases and target gates also regressed.

## Breadth versus the public bandwidth-0.7 baseline

Against bandwidth-0.7:

- MSE: **0.001042745722 vs 0.001058275042**
- relative MSE reduction: **1.4674%**
- patient wins: **40/59**
- favorable outer folds: **5/5**
- p90 patient RMSE: **0.037419696 vs 0.037894285**
- target-average errors improved: **19/24**
- target-average regressions: **5/24**

The five target-average regressions versus bandwidth-0.7 are **Afatinib, AZD7762, LCL161, Regorafenib, and Trametinib**. They remain disclosed rather than spliced away.

Against original R13, the candidate lowers MSE by **8.9193%**, wins **49/59 patients**, improves **5/5 outer folds**, and improves **22/24 target-average errors**. The two target-average regressions versus R13 are **Methotrexate** and **Panobinostat**.

The authenticated R18 gate also passes: MSE is **8.6437%** lower, **50/59** patients improve, all five folds improve, p90 is nonworse, and both orientation-wide MSEs remain below the R18 expected MSE.

## Important incremental limitation

The immediately preceding verified development result is orientation-A auxiliary rank-1 calibration at **0.001043179589**. The new candidate improves the mean by only **0.0416%**, with **32/59 patient wins and 3/5 favorable folds** versus that immediate predecessor, while p90 remains nonworse.

Therefore the honest claim is:

> **lowest verified development point estimate, with broad gains versus the public bandwidth-0.7 baseline**

not “uniformly better than every immediately preceding adaptive variant.”

## Verification

The frozen replay verifier reports:

- status: **PASS_FLOATING_REPLAY**
- base model refit: **false**
- calibration recomputed: **true**
- held-target predictions reconstructed: **5,712**
- maximum prediction difference: **0.0**
- prediction tolerance: **5e-16**
- calibration folds checked: **5**
- Protected22 access: **false**

Machine-readable evidence:

- `evidence/orientation_specific_control_quality_rank1_20261006.json`
- `study/orientation_specific_control_quality_rank1/PROPOSAL.json`
- `study/orientation_specific_control_quality_rank1/PROTOCOL.json`
- `study/orientation_specific_control_quality_rank1/FREEZE.json`
- `study/orientation_specific_control_quality_rank1/verify_study.py`

## Selection boundary

This model was developed after repeated inspection of Lib1 outer outcomes. Whole-patient splitting prevents within-run patient leakage, but it does not transform repeatedly reused development folds into untouched confirmation. The current result must therefore stay labeled as adaptive development.

Protected22 remains closed and exposed. No Protected22 value was used to fit, select, diagnose, or verify this successor.

The next scientifically strong step is prospective or untouched patient-separated confirmation, not another claim that a tiny adaptive decimal is definitive.

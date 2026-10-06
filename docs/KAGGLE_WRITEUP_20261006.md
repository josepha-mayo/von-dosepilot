# von DosePilot - Kaggle writeup, 6 October 2026

**Category:** Model & Algorithm
**Author:** Joseph Ayanda
**Repository:** https://github.com/josepha-mayo/von-dosepilot
**Live fictional-data demo:** https://von-dosepilot.netlify.app
**Demo video (75 seconds):** https://youtu.be/QeOGJIgx378
**Current technical report:** https://github.com/josepha-mayo/von-dosepilot/blob/master/docs/DosePilot_Technical_Report_20261006.pdf
**6 October reviewer update:** https://github.com/josepha-mayo/von-dosepilot/blob/master/SUBMISSION_UPDATE_20261006.md

## Project Summary

Drug-response screening is constrained by physical assay capacity: every extra drug-dose measurement consumes a well, plate space, material, and experimental attention. DosePilot treats sparse screening as a coupled **measurement-design, reconstruction, and provenance** problem rather than ordinary regression. Before responses arrive, it freezes a traceable 64-treatment layout from a 416-measurement retrospective source profile, with **32 treatment wells per source plate**, then reconstructs **24 fixed normalized log-dose AUC summaries**. The 64/416 comparison is a measurement-count compression claim, not a claimed 84.62% reduction in real laboratory cost or time.

The newest verified Lib1 development candidate keeps the same 64-treatment plan and adds a conservative orientation-specific rank-1 calibration from standard plate-control quality summaries. On **119 organoid samples grouped into 59 whole patients**, it reaches **0.001042745722 patient-balanced full-24 MSE**, versus **0.001058275042** for the public bandwidth-0.7 baseline and **0.001144858681** for original R13. Against bandwidth-0.7 it lowers MSE by **1.4674%**, improves **40/59 patient means**, all **5/5 outer folds**, p90 patient RMSE, and **19/24 target-average errors**.

DosePilot is built to make those numbers inspectable: patient identity is preserved through model selection, A/B 64-well alternatives are never fused into a hidden 128-well predictor, incomplete primary inputs are withheld rather than imputed, failed model families remain published, and the frozen replay reconstructs **5,712 held-target predictions** within a **5e-16** numerical tolerance. The current result remains **repeated adaptive development**, not independent confirmation, an official competition score, or clinical evidence.

## 1. Problem

A full retrospective source profile contains **416 eligible treatment measurements per sample** across two source plates. DosePilot asks a narrower operational question:

> Can a fixed, traceable 64-treatment measurement plan reconstruct the 24 prespecified response summaries while keeping acquisition, identity, missingness, and evidence boundaries auditable?

One deployment uses **64 treatment wells**, 32 on each source plate, or **15.38%** of the retrospective treatment-measurement count. This is a measurement-count compression claim only. It is not a demonstrated 6.5x reduction in laboratory money, material, controls, or elapsed time.

Each output is the average of two plate-specific trapezoidal AUCs over log concentration using the supplied normalized viability values. It is not IC50, a drug rank, or a clinical-response label.

## 2. Physical and evaluation contract

The Lib1 development frame contains **119 organoid samples from 59 whole patients** and 24 targets.

- Every sample from one patient stays on the same side of every inner and outer split.
- Each A or B deployment uses exactly **64 distinct treatment wells, 32 per plate**.
- A and B are alternative 64-well layouts, not halves of a hidden 128-well predictor.
- A and B predictions are scored separately and their **losses**, not prediction vectors, are averaged.
- Planning, fitting, scaling, and inner model selection remain inside fitting splits.
- Missing purchased values are not silently imputed.

## 3. Model stack

### Stage A - training-contained acquisition

For each drug, fitting-only moments choose two native doses and rank the value of a third. Sixteen drugs receive a third-dose upgrade:

```text
24 x 2 + 16 x 1 = 64 treatment wells
```

### Stage B - own-drug ridge

Twenty-four unpenalized-intercept ridge heads reconstruct each target from its own drug's purchased measurements. One shared ridge penalty is selected inside patient-grouped inner folds.

### Stage C - cross-drug residual geometry

The bandwidth-0.7 additive model applies grouped Gaussian residual kernels plus a linear component. Bandwidth 0.7 was a bounded adaptive development choice and remains explicitly labeled as such.

### Stage D - standard-control calibration

The current lowest-MSE candidate preserves the 64 treatment wells and uses **standard plate-control QC summaries** to model a low-rank target-deviation mode.

- Orientation B uses an **11-feature** quality basis including control range, negative/positive control level, and negative/positive control variation, with a rank-1 replacement strength of **1/3**.
- Orientation A uses a more conservative **7-feature** level basis that excludes the CV channels, also rank 1, with strength **1/9**.

No extra treatment well is purchased. The calibration is intentionally rank 1: recorded rank-2, rank-3, and rank-4 alternatives all regress.

Full method note: https://github.com/josepha-mayo/von-dosepilot/blob/master/docs/CONTROL_QUALITY_SUCCESSOR_20261006.md

## 4. Same-task development results

| Complete procedure | Patient-balanced MSE | Status |
|---|---:|---|
| R13 own-drug reconstruction | 0.001144858681 | retained historical baseline |
| S2 spectral residual | 0.001070143945 | superseded |
| Additive group kernel, bandwidth 1.0 | 0.001060552730 | predecessor |
| Bandwidth-0.7 additive | 0.001058275042 | public operational baseline |
| Standard-control meanquad/plate interaction v2 | 0.001045585078 | adaptive development |
| Control rank-1 target deviation | 0.001044448281 | adaptive development |
| Orientation-A auxiliary rank-1 calibration | 0.001043179589 | immediate predecessor |
| **Orientation-specific control-quality rank-1** | **0.001042745722** | **lowest verified development MSE** |

### Current versus bandwidth-0.7

- relative MSE gain: **1.4674%**
- patient wins/losses: **40 / 19**
- favorable outer folds: **5 / 5**
- p90 patient RMSE: **0.037419696 vs 0.037894285**
- target-average wins/losses: **19 / 5**

The five regressing targets are **Afatinib, AZD7762, LCL161, Regorafenib, and Trametinib**.

### Current versus R13

- relative MSE gain: **8.9193%**
- patient wins/losses: **49 / 10**
- favorable outer folds: **5 / 5**
- target-average wins/losses: **22 / 2**

The two target-average regressions are **Methotrexate** and **Panobinostat**.

### Current versus the immediate 0.001043179589 predecessor

The mean gain is only **0.0416%**, with **32/59 patient wins and 3/5 favorable folds**. p90 remains nonworse.

That is why the claim is “lowest verified adaptive-development point estimate with broad gains versus bandwidth-0.7,” not “uniformly better than every nearby adaptive variant.”

## 5. Verification and falsification

The current candidate's frozen replay reconstructs **5,712 held-target predictions**. A fresh Windows replay had maximum numerical difference **2.22e-16**, below the frozen **5e-16** tolerance. It recomputes the calibration without refitting the base model.

The authenticated historical R18 screen passes:

- MSE reduction: **8.6437%**
- patient wins: **50/59**
- favorable folds: **5/5**
- p90 nonworse: yes
- both orientation-wide MSEs below the R18 expected MSE: yes

Several tempting extensions failed and were not promoted:

- rank 2-4 control-quality calibration: worse than rank 1;
- robustized control bases: worse;
- inner target gates: worse;
- wider bandwidth 1.4: rejected;
- cross-patient median bandwidth: lower point MSE but only 4/5 folds, rejected;
- simplex stacking: all inner objectives improved but held-patient performance worsened;
- isotonic paid features: rejected.

Negative results stay in the repository rather than disappearing after selection.

## 6. Reproducibility

The public repository includes:

- exact endpoint definitions and the 64-well A/B schedules;
- the public-workbook reconstruction route;
- the current candidate proposal, protocol, freeze, runner, and no-refit verifier;
- machine-readable aggregate evidence;
- an identity-bound fictional lifecycle demonstrating commit, missing-input withholding, recovery, and prediction.

Current candidate evidence: https://github.com/josepha-mayo/von-dosepilot/blob/master/evidence/orientation_specific_control_quality_rank1_20261006.json

Current candidate implementation: https://github.com/josepha-mayo/von-dosepilot/tree/master/study/orientation_specific_control_quality_rank1

The current fictional lifecycle still demonstrates the bandwidth-0.7 operational model. The newer control-quality calibration is verified research code and aggregate evidence, but it has **not** been silently substituted into that older lifecycle demo. This separation is deliberate.

## 7. Validation boundary

Protected22 does **not** rescue this result. Its frozen full-cohort primary was not estimable because five required cells were unavailable, and prior exposure prevents an untouched-confirmation claim. No Protected22 response was used for the 6 October successor.

Separate external adaptations are also kept separate. A matched-CAF design adaptation passed its own gate; FORECAST-1 and eLife adaptations did not fully pass theirs. None directly validate the current fitted 24-output weights.

The strongest next experiment is therefore a preregistered, patient-separated prospective or untouched confirmation with the device/control/QC contract frozen before responses are collected.

## 8. Why this matters

DosePilot's contribution is not “one more regressor.” The system treats sparse screening as a coupled **measurement-design + model + provenance** problem:

1. choose a physically explicit budget;
2. bind every measurement to identity and plate;
3. preserve patient separation through model selection;
4. use standard controls to correct a small shared error mode rather than buying extra treatment wells;
5. abstain on incomplete primary inputs;
6. keep failed experiments and selection boundaries visible.

That combination is the practical thesis: **fewer treatment measurements, stronger auditability, and a model that knows when not to fabricate a complete answer.**

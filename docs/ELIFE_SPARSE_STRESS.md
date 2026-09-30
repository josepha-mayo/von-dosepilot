# Public eLife CRC-organoid sparse-reconstruction stress test

30 September 2026.

A separate public colorectal-cancer organoid workbook from Verissimo et al. was used to ask whether the **DosePilot design pattern**, rather than the original 24-head fitted model, transfers to another assay and drug panel.

This is a retrospective stress test, not blind confirmation. Numerical source values were visible during workbook-structure inspection before this protocol was frozen, so the result is not presented as untouched validation.

## Task

Twelve patient-derived tumor organoid sheets were fixed: P6T, P8T, P9T, P11T, P14T, P17T, P18T, P20T, P23T, P25T, P26T and P31T. The engineered P18T-KRAS derivative and the two normal-organoid sheets were excluded before scoring this task.

Five monotherapies were present across all twelve sheets under spelling aliases: Afatinib, Lapatinib, Selumetinib, Trametinib and SCH772984.

For each drug, the target support was defined only by dose columns that were finite for all twelve organoid sheets. This completeness-only rule produced **54 total target readouts** across the five drugs: 12, 11, 14, 8 and 9 respectively. Targets were unclipped normalized log-dose trapezoidal AUCs.

Both sparse procedures received exactly **13 dose-level readouts**: two per drug plus three third-dose upgrades. This is a **75.93% measurement-count reduction relative to the 54 readouts used to construct these five targets**, not a physical-well or monetary-savings claim.

## Procedures

The learned arm used R13's structural pattern: independently selected own-drug measurements, own-drug ridge heads only, scale floor 0.05, one common ridge penalty chosen by nested inner leave-one-organoid-out CV, and fitting-only allocation inside every outer training fold.

The control was a separately optimized constant-tail piecewise-linear interpolation policy. It received the same 13-readout budget and selected its own two/three-dose subsets from the training organoids.

Outer evaluation was leave-one-organoid-out across all twelve fixed organoid sheets.

## Result

| Procedure | MSE | RMSE | p90 organoid RMSE |
|---|---:|---:|---:|
| Learned sparse reconstruction | **0.00417342** | **0.0646020** | **0.0801515** |
| Optimized interpolation | 0.00604235 | 0.0777325 | 0.1074444 |
| Training-organoid target mean | 0.03100236 | 0.1760749 | 0.2263419 |

The learned procedure has **30.93% lower MSE** than interpolation and lower target MSE for **4 of 5 drugs**. It wins **7 of 12 organoid-level losses** and loses five.

Per-target MSE:

| Drug | Learned | Interpolation |
|---|---:|---:|
| Afatinib | **0.00238138** | 0.00412111 |
| Lapatinib | **0.00328316** | 0.00450429 |
| Selumetinib | 0.00664118 | **0.00530293** |
| Trametinib | **0.00495496** | 0.00655910 |
| SCH772984 | **0.00360641** | 0.00972431 |

The descriptive paired-organoid bootstrap interval for learned-minus-interpolation MSE is **[-0.0047601, +0.0005744]**, so it crosses zero.

## Frozen stress gate

The rule required all five:
- at least 5% lower MSE: **pass**;
- at least 8/12 organoid wins: **fail, 7/12**;
- at least 4/5 target wins: **pass, 4/5**;
- p90 organoid RMSE nonworse: **pass**;
- paired-bootstrap upper bound below zero: **fail**.

**Decision: DOES_NOT_PASS_RETROSPECTIVE_STRESS_GATE.**

The mean-error result is promising but the organoid-level consistency and uncertainty are not strong enough for the preset label. That failed gate is retained rather than weakened after seeing the result.

## Verification

Ten unique synthetic tests passed before the complete run. A second implementation then reparsed the workbook, reconstructed every five-drug target exactly, recomputed every aggregate and per-target metric, recomputed the fixed-seed bootstrap interval and verified that each organoid appears exactly once as the outer holdout. Target reconstruction differed by **0.0** at machine precision.

Aggregate hashes and results are recorded in [the eLife stress-test receipt](../evidence/elife_sparse_stress_20260930.json).

## Limits

This experiment tests an **adapted sparse-reconstruction procedure**, not the fitted 24-drug R13 model. The source study, drug panel, support construction and replicate structure differ from DosePilot development. It supplies no clinical-response validation, no organ-on-chip hardware evidence, no physical-well equivalence and no official competition score.

The source workbook is public but is not redistributed by this repository. Original source rights remain with their authors and publisher.

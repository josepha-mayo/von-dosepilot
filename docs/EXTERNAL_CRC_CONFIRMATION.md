# External CRC confirmation: separate patient cohort

30 September 2026.

DosePilot's original 24-target result remains retrospective development on one colorectal-cancer organoid dataset. To test whether the underlying sparse-reconstruction design transfers at all, we froze a **new task on an independent public colorectal-cancer organoid study** before reading its confirmation outcomes.

This is not a direct external validation of the original 24 fitted heads. The external study has different drugs, dose grids, laboratories and response files. We therefore evaluate the **DosePilot design principle**: choose a small set of real dose measurements using training-only covariance, then predict each drug's full dose-response summary with an own-drug sparse ridge head.

## Public external source

Source: Tan et al., *Cell Reports Medicine* (2023), “Unified framework for patient-derived, tumor-organoid-based predictive testing of standard-of-care therapies in metastatic colorectal cancer,” DOI `10.1016/j.xcrm.2023.101335`, PMCID `PMC10783557`.

The article is distributed under CC BY-NC-ND 4.0. DosePilot does **not** redistribute the source workbooks. The external dataset license is separate from this repository's MIT license.

The study provides two useful raw single-agent cohorts: a community cohort with 84 PDTO lines from 82 patients, and a FORECAST-1 cohort with 19 PDTO lines from 19 different patients.

The eight common raw single-agent targets are 5FU, Pemetrexed, SN38, Temozolomide, Regorafenib, Erlotinib, TAS-102 and Gemcitabine. Five overlap the original DosePilot development drug list: 5FU, SN38, Regorafenib, TAS-102 and Gemcitabine.

Pinned source identities are in `evidence/external_crc_confirmation_20260930.json`.

## Protocol frozen before FORECAST-1 outcomes

For each sample and drug, the target is the normalized trapezoidal AUC over log concentration using all nine supplied response values, without clipping.

The sparse budget is **21 measured drug-concentration values per sample**: two concentrations for each of eight drugs, with exactly five drugs receiving one additional concentration.

The learned procedure keeps DosePilot's original design choices: allocation regularization `0.1`, own-drug ridge heads, and one shared ridge penalty chosen from `{0.01, 0.1, 1, 10}` by patient-grouped cross-validation. Plans, scales and models are rebuilt inside each community training fold.

The comparator independently optimizes its own 21-measurement acquisition policy for piecewise-linear interpolation in log dose. It is not forced to use the learned model's selected concentrations.

Only samples with all 72 required values are eligible. This complete-case rule was frozen before confirmation.

### Data-exposure record

During setup, a small slice of **community** outcomes was inadvertently displayed while checking workbook structure. For that reason the community cohort is treated only as development data. **No numerical FORECAST-1 response cell was opened before the protocol, final community model, comparator, metric, gate and confirmation executable were hash-frozen.**

## Community-only development

The complete-case rule retained 64 PDTO lines from 63 community patients.

| Procedure | Patient-balanced MSE |
|---|---:|
| Learned sparse reconstruction | **0.0015249304** |
| Separately optimized interpolation | 0.0026616589 |
| Community-mean baseline | 0.0192903489 |

The shared ridge penalty selected without FORECAST-1 was `0.01`. These numbers are development evidence only.

## One-shot FORECAST-1 confirmation

The final model and confirmation program were frozen before numerical access. FORECAST-1 was then opened once. The complete-case rule retained 13 of 19 source PDTO lines; six had at least one missing required response and were excluded exactly as prespecified.

| Procedure | Patient-balanced MSE | RMSE |
|---|---:|---:|
| **Learned sparse reconstruction** | **0.0021714654** | **0.0465990** |
| Separately optimized interpolation | 0.0038551794 | 0.0620901 |
| Community-mean baseline | 0.0254466756 | 0.1595201 |

Against optimized interpolation, the learned procedure had **43.67% lower MSE**, lower patient loss for **10 of 13** complete patients, and nonworse MSE on **7 of 8** targets. On the five targets shared with the original DosePilot task, MSE was `0.0018543411` versus `0.0026583760`.

The prespecified paired-patient bootstrap interval for `learned MSE - interpolation MSE` was `[-0.00280937, -0.00058147]`. This is a descriptive confirmation statistic under the frozen complete-case task, not a clinical-effect confidence interval.

## Prespecified gate: not fully passed

Before opening FORECAST-1 outcomes, the project required all four conditions: lower full-eight MSE than optimized interpolation; at least **12 strict patient wins out of the original 19 source patients**; nonworse per-target MSE on at least 5 of 8 targets; and lower MSE on the five DosePilot-overlap targets.

Conditions 1, 3 and 4 passed. Condition 2 did not: only 13 patients were complete and the learned procedure won 10 of those 13.

**The gate therefore fails. It is not rewritten after seeing the result.**

The result is still materially stronger evidence than the previous development-only comparisons: a model/design frozen on the community cohort outperformed a separately optimized measurement-matched baseline on a distinct FORECAST-1 patient cohort. But it is not presented as a clean universal external-validation success.

## Verification and limits

A second script recomputed every aggregate directly from the saved confirmation predictions and reproduced all three procedure MSE/RMSE values, all eight per-target MSEs, 10 patient wins / 3 losses, 7 of 8 nonworse targets, the shared-five comparison, the frozen bootstrap interval, and the failed four-part gate.

The audit did not refit a model, reopen the source workbook, or alter the result.

This external experiment does **not** validate the original fitted 24-drug R13 model, clinical decisions, prospective organ-on-chip hardware, calibrated uncertainty, or realized laboratory savings. It shows evidence for the sparse acquisition-and-reconstruction **design pattern** on a separate CRC organoid cohort.

## Later support-complete sensitivity analysis

A later, explicitly **post-hoc** sensitivity analysis asked whether the learned-versus-interpolation advantage persists when the task is restricted by support metadata to the six drugs with complete nine-dose values for **all 19** FORECAST-1 source patients. This analysis does not replace the frozen eight-drug confirmation and cannot retroactively satisfy its failed gate.

Using the same 2.667 sparse measurements per target as the original 64/24 DosePilot ratio, the six-drug task used 16 of 54 available values. The learned design family was selected only on the community cohort and reached FORECAST-1 MSE **0.00176996** versus **0.00353173** for separately optimized interpolation, a **49.88% reduction**, with **16/19 patient wins** and **6/6 drug-MSE wins**. The descriptive patient-bootstrap interval for learned-minus-interpolation MSE was **[-0.0032314, -0.0004103]**.

This later task is weaker evidence than the prefrozen confirmation because raw FORECAST-1 rows had been displayed during schema discovery and the earlier external result already existed in project history. It is therefore reported only as a robustness/sensitivity analysis. Full details and verification are in [FORECAST1_SUPPORT_COMPLETE_SENSITIVITY.md](FORECAST1_SUPPORT_COMPLETE_SENSITIVITY.md).

The original protected Lib2 frame remains closed.

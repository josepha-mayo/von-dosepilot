# FORECAST-1 support-complete sensitivity analysis

30 September 2026.

This analysis is **not a second independent confirmation**. The repository already contains a stronger, prefrozen eight-drug FORECAST-1 experiment whose complete-case support gate retained 13 of 19 source patients and whose prespecified four-part gate did not fully pass. The analysis below was defined later to ask a narrower question: if the external task is restricted by response-blind support metadata to drugs with complete numerical grids in all 19 FORECAST-1 lines, does the sparse learned reconstruction advantage persist?

It therefore **does not replace, repair, or retroactively pass** the frozen eight-drug experiment.

## Source and disclosure

The source is Tan et al., *Cell Reports Medicine* (2023), DOI `10.1016/j.xcrm.2023.101335`, PMCID `PMC10783557`. Source workbooks are not redistributed by this repository and retain the article's CC BY-NC-ND 4.0 terms.

The community single-agent workbook contains 84 PDTO lines from 82 patients. The FORECAST-1 workbook contains 19 PDTO lines from 19 different metastatic-CRC patients.

During schema discovery, a small number of raw FORECAST-1 rows were displayed before this sensitivity protocol was frozen. No aggregate external metric, candidate error, comparator error or patient-win count had been calculated at that point. Nevertheless, that exposure means this result is reported as a **post-hoc external-cohort sensitivity analysis**, not a prospectively blinded validation.

A separate earlier eight-drug external confirmation also already existed in the project history. That prior result is another reason not to treat this sensitivity analysis as an independent second trial.

## Support-complete six-drug task

Six single agents have complete nine-dose numerical grids across both cohorts:

- 5FU
- SN38
- Regorafenib
- Erlotinib
- TAS-102
- Gemcitabine

Five overlap the original DosePilot development target list; Erlotinib is outside that original 24-target panel.

The target for each drug is a normalized trapezoidal area under supplied viability versus log concentration across all nine native dose points, without clipping.

The sparse budget is **16 observed values for six targets**, exactly the same **2.667 observed treatment values per target** as DosePilot's 64-for-24 design. This does **not** mean the fraction of all available source measurements is identical between studies.

## Training-only selection

All allocation, preprocessing and model selection use only the 82-patient community cohort.

The learned arm reuses the R13 design family at the smaller target count:

- two native doses per drug;
- exactly four third-dose upgrades, for 16 values total;
- per-drug size-2/size-3 subsets selected by the covariance residual proxy with allocation regularization 0.1;
- own-drug linear ridge heads with unpenalized intercepts;
- one shared ridge penalty selected from `{0.01, 0.1, 1, 10}` using five-fold whole-patient community CV.

The selected ridge penalty was `0.01`.

The comparator independently optimizes its own size-2/size-3 acquisition policy for constant-tail piecewise-linear interpolation in log concentration under the same 16-value budget.

FORECAST-1 does not choose any plan, ridge penalty, scaler or comparator parameter.

## All-19-patient result

| Procedure | MSE | RMSE | p90 patient RMSE |
|---|---:|---:|---:|
| **Sparse learned reconstruction** | **0.0017699569** | **0.0420709** | **0.0543018** |
| Optimized interpolation | 0.0035317300 | 0.0594284 | 0.0926325 |

Relative to independently optimized interpolation, the learned sparse procedure had **49.88% lower MSE**, lower patient-average error for **16 of 19 patients**, and lower MSE on **all six drugs**.

The descriptive 10,000-resample patient bootstrap interval for `learned patient MSE - interpolation patient MSE` was **[-0.0032314, -0.0004103]**. It remained entirely below zero. This is a descriptive stability summary, not a clinical-effect confidence interval.

The first two SN38 dose labels differed between source tables only through decimal representation, with maximum relative discrepancy 0.0577%. A pre-score metadata amendment permitted dose identities within 0.1% relative tolerance while preserving each cohort's own original numeric labels for its AUC integration. The first failed attempt, which stopped before scoring on exact dose-label comparison, was preserved.

## Independent recomputation

A second implementation recomputed:

- every sparse-ridge prediction directly from the weighted normal equations;
- every interpolation prediction using sample-wise `numpy.interp` plus direct trapezoidal integration.

Maximum differences from the committed predictions were:

- learned arm: **0.0**
- interpolation arm: **2.22e-16**

Fourteen invented tests passed after one test-fixture correction. The failed fixture had corrupted an **unselected** dose and incorrectly expected the sparse predictor to consume it; the production code correctly ignored that unpaid value. The fixture was changed to corrupt a purchased dose. No production equation changed.

Exact result, prediction, verifier and source hashes are recorded in [the aggregate evidence receipt](../evidence/forecast1_support_complete_sensitivity_20260930.json).

## Published-AUC secondary endpoint

After predictions were already committed, the same prediction vectors were compared to the article's processed AUC table as a post-hoc secondary endpoint. No model was refit and no acquisition policy changed.

| Procedure | MSE against published processed AUC |
|---|---:|
| Sparse learned reconstruction | **0.00576390** |
| Optimized interpolation | 0.00796967 |

The learned arm remained 27.68% lower, with 16/19 patient wins and 5/6 drug wins.

Our transparent raw nine-dose log-AUC is highly correlated with, but not identical to, the article's processed AUC definition (Pearson 0.9559; mean absolute difference 0.0260). We therefore do **not** present the two target definitions as equivalent.

## Interpretation boundary

Together with the prefrozen eight-drug confirmation, this sensitivity analysis makes one narrow result more credible: the benefit of learned sparse reconstruction over an acquisition-matched interpolation baseline is not confined to the original DosePilot development cohort.

It still does **not** establish:

- direct external validation of the original fitted 24 R13 heads;
- validation of DosePilot's original two-plate coverage-versus-replication experiment;
- prospective organ-on-chip performance;
- clinical benefit;
- calibrated uncertainty;
- a competition leaderboard or judging score.

The original protected Lib2 cohort remains closed.

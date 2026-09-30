# DosePilot external-cohort replication protocol

Frozen 30 September 2026 before any aggregate FORECAST-1 prediction score was calculated.
Source article: Tan et al., Cell Reports Medicine 2023, DOI 10.1016/j.xcrm.2023.101335, PMCID PMC10783557.
Training: Table S3, 84 PDTO lines from 82 community-cohort patients. External evaluation: Table S7, 19 PDTO lines from 19 FORECAST-1 mCRC patients.
The cohorts are wholly separate from DosePilot's Kryeziu et al. development cohort.

## Important disclosure
During source/schema discovery, the first rows of the raw FORECAST-1 workbook were printed before this protocol was frozen. No candidate, baseline, AUC target, prediction error, patient comparison or aggregate external metric was calculated before freeze. Therefore this is an external-cohort replication, not a prospectively blinded validation.

## Frozen task
Use six complete single-agent grids shared across community and FORECAST-1: 5FU, SN38, Regorafenib, Erlotinib, TAS-102 and Gemcitabine. Five are also DosePilot targets; Erlotinib is an out-of-original-panel generalization target.
Each drug has the same nine concentrations in both cohorts. The target is the normalized trapezoidal area under supplied viability versus log concentration across all nine native doses, with no clipping.
A sparse procedure may observe exactly 16 of the 54 available drug-dose values per PDTO: two doses per drug plus four third-dose upgrades. This exactly preserves DosePilot's 64/24 = 16/6 treatment-measurement ratio.

## Candidate
Reuse the R13 design family, not its fitted biological weights: own-drug linear ridge heads, unpenalized intercepts, weighted standardization, one shared ridge penalty in {0.01,0.1,1,10}. For each fitting context, enumerate every size-2 and size-3 native-dose subset per drug. Choose each best subset with the R13 covariance residual proxy at alpha=0.1, then allocate four upgrades by largest proxy reduction. Select the shared ridge penalty by five-fold whole-patient CV on community data, rebuilding plan/scaler/model in every fitting fold. Refit once on all community data.

## Comparator and evaluation
Comparator: constant-tail piecewise-linear interpolation on log concentration, allowed to optimize its own size-2/3 subsets and four upgrades using community data only. It has no learned coefficients or test-tuned hyperparameters.
Primary external metric: equal-patient/equal-drug MSE over all 19 FORECAST-1 patients and six drugs. Secondary: RMSE, patient wins/losses/ties, per-drug MSE wins, p90 patient RMSE and a descriptive 10,000-resample patient bootstrap interval for candidate-minus-comparator MSE.
The external cohort must never select dose subsets, upgrades, ridge penalty, preprocessing or formula. Candidate and comparator predictions must be committed before aggregate external scores are calculated.

## Boundaries
This tests whether the sparse-reconstruction design family transfers to a separate CRC-organoid cohort/platform task. It does not validate the exact submitted 24-head R13 weights, the coverage-versus-replication plate experiment, clinical benefit, or organ-on-chip performance. No protected Lib2 data are used.
Preserve all failures. Do not drop a drug/patient because of performance. No post-test parameter changes count as independent evidence.
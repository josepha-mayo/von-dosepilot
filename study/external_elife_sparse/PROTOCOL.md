# eLife CRC organoid sparse-reconstruction stress test

Frozen 30 September 2026 before fitting or scoring this five-drug experiment.

## Evidence level

This is a retrospective external stress test on the public workbook from Verissimo et al., eLife 2016, not blind confirmation. During source-structure inspection before this protocol, numerical values from at least one sheet were displayed. Therefore no untouched-data claim is allowed. The purpose is to test whether the DosePilot sparse own-drug reconstruction pattern survives on a different public CRC-organoid assay and drug panel.

Source workbook: `elife-18489-supp1-v2.xlsx`, expected SHA-256 `b80557f95c35713df8ab0bec94acb64f266bde73dd24bbbeacb689ad701f2605`.

## Fixed cohort and targets

Use these 12 patient-derived tumor organoid sheets exactly:
`P6T, P8T, P9T, P11T, P14T, P17T, P18T, P20T, P23T, P25T, P26T, P31T`.

Exclude `normal` and `normal+KRAS`; exclude engineered `P18T-KRAS` to avoid treating an engineered derivative as an independent patient-derived line.

Use five monotherapies present under spelling aliases in all 12 sheets:
Afatinib, Lapatinib, Selumetinib, Trametinib, SCH772984.

For each drug, define its target-support dose grid as every positive-dose column whose response is finite for all 12 fixed organoid sheets. Support selection uses completeness only, never response magnitude or prediction error. Expected support sizes from preflight: 12, 11, 14, 8, and 9 dose points respectively, total 54.

The target is the normalized trapezoidal integral over log concentration on that drug's fixed complete support. Divide workbook viability percentages by 100, but do not clip; negative and >1 values remain valid.

## Fixed sparse budget and procedures

Each procedure receives exactly 13 dose-level observations per organoid: two doses for every drug plus exactly three third-dose upgrades. This is 13/54 = 24.07% of the response values used to construct the five targets. These are dose-level readouts, not a claim about physical-well or monetary savings.

### Learned sparse reconstruction
For each outer leave-one-organoid-out fold:
1. On the 11 fitting organoids only, enumerate every size-2 and size-3 subset on each drug's fixed support.
2. Rank subsets with the R13-style own-target ridge covariance proxy using alpha=0.1 and standardized paid values with scale floor 0.05.
3. Take each drug's best size-2 and size-3 subset, then assign the three third-dose upgrades to the three largest fitting-only proxy gains. Best-three may replace best-two.
4. Select one common ridge penalty from {0.01, 0.1, 1, 10} by inner leave-one-organoid-out CV. Every inner fitting slice rebuilds the sparse plan and scaler.
5. Fit five own-drug heads only. No drug may use another drug's measurements.

### Interpolation control
Independently optimize a constant-tail piecewise-linear interpolation policy on the same outer fitting organoids, the same fixed support grids and the same 13-readout budget. Enumerate all size-2/3 subsets per drug, choose the fitting-MSE best of each size, and assign exactly three upgrades by largest fitting-only gain. No learned response coefficients.

Also report a fitting-organism mean target baseline as context only.

## Scoring

Primary descriptive metric: mean squared error averaged equally across the 12 outer-held-out organoids and five targets. Report RMSE, strict organoid wins/losses/ties, per-target MSE, target wins, leave-one-organoid-out fold values, p90 organoid RMSE, and a fixed-seed 10,000-resample paired-organoid bootstrap interval for learned-minus-interpolation MSE.

A prespecified robustness label `PASSES_RETROSPECTIVE_STRESS_GATE` requires all:
1. learned MSE at least 5% below optimized interpolation;
2. at least 8/12 strict organoid wins;
3. at least 4/5 target MSEs lower;
4. p90 organoid RMSE nonworse;
5. paired bootstrap upper endpoint below zero.

Otherwise label `DOES_NOT_PASS_RETROSPECTIVE_STRESS_GATE`.

## Boundaries

This experiment adapts the sparse reconstruction design to a different drug panel and source study. It does not validate the original fitted 24-head R13 weights, the two Lib2 unsupported targets, clinical response, organ-on-chip hardware, or a competition rank. Missing-response support was inspected before protocol freeze, and some numerical source cells were also viewed during structure inspection; those facts stay disclosed. Results are retained whether favorable or unfavorable.
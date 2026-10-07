# Structural acquisition checkpoint, 7 October 2026

## Objective
The user's requested step change is operationalized here as a target of halving the retained research-candidate MSE from 0.001042745722096212 to 0.000521372861048106 without increasing the original 64-treatment-well budget, changing the 24-output target denominator, or weakening evaluation. This is a target, not an achieved claim.

## Error diagnosis
The worst six of 24 drug targets contribute 34.34% of the retained candidate's patient-balanced squared error, and the worst twelve contribute 60.54%. Error is not concentrated in one target. The six worst patients contribute 23.86% of total patient-balanced error; identities are not published. Mean squared plate-AUC half difference is 0.0007521757809186084. This is a retrospective disagreement/noise proxy, NOT an irreducible-error lower bound. It does not prove the half-error target impossible.

## Completed experiment: flexible 64-well allocation
Instead of changing another kernel scale, this experiment changed the measurement-design optimizer. It compared the original two/three-dose policy with exact fixed-budget dynamic programming that allowed one-to-six or two-to-six doses per target, using the same 64 distinct treatment wells and 32/32 source-plate balance. All 24 targets remained present. All allocation, scaling, model fitting and choice among the 30 predefined model combinations were nested within patient-separated training folds.

The code and protocol were frozen and pushed before the outcome at a2cc08ff67b8e0f89510c66d6dbf7f4865f78594. Eleven synthetic tests passed, including exhaustive small-problem DP comparison, original two/three-dose subset equivalence, original kernel equivalence, physical-budget checks, and poisoning of unpurchased inputs.

| Procedure | Patient-balanced MSE | p90 patient RMSE |
|---|---:|---:|
| Retained 64-well research candidate | 0.001042745722 | 0.037419695944 |
| Operating bandwidth-0.7 baseline | 0.001058275042 | 0.037894285309 |
| New flexible-allocation procedure | 0.001074500245 | 0.039506271676 |

Result: REJECT_FOR_PROMOTION. Flexible allocation was selected by inner validation for two outer folds and worsened both; the other three retained the incumbent. Overall error is 3.0453% worse than the retained research candidate and 1.5332% worse than the operating baseline. The half-error target was NOT achieved. The existing model and accepted Kaggle entry were not changed.

## Verification
A separately implemented saved-array metric audit agrees to within 6.94e-18. All 25 frozen source hashes and all five selected physical plans were checked. Changing only outer-fold-zero labels changed its rebuilt predictions by 0.0. Poisoning unpurchased query values changed predictions by 0.0. These establish software/numerical checks, not independent biological validation or a new external cohort result. No Protected22/Lib2 response was read. No patient-level rows or prediction arrays are published.

## Research implication
Within this tested design, a smaller training covariance-risk proxy did not reliably translate into lower held-patient error. Do not promote the surrogate optimum or retry the same menu as an unseen experiment. A future acquisition study needs a scientifically distinct risk estimator or information source, with a new pre-outcome protocol, rather than broader searching of this already-rejected menu.

The separately owned 72-well paired-noise run was read for status only: it had already completed and selected the incumbent in every fold. It was not rerun, changed, or promoted here. The earlier latent-curve quadrature family was also inspected to avoid duplicating that failed study.

## Files and submission schedule
Research branch: dosepilot-flexbudget64-20261007. Workspace: D:\von-dosepilot-flexbudget64-20261007. Private run: D:\von-dosepilot-data\flexible_cardinality64_20261007_run1.
Public aggregate evidence: evidence/flexible_cardinality64_20261007.json and evidence/error_concentration_20261007.json.

Keep improving through 8 October, Africa/Lagos time; 9 October is the agreed freeze, regression-test, existing-entry update and saved-submission verification day. The Google Calendar reminder was created for 9 October at 08:00 Africa/Lagos with popup and email notifications. Device notification delivery still depends on Google Calendar notification settings. The old ChatGPT one-off reminder was disabled, not the ongoing research task.

These results remain repeated adaptive development on 119 Lib1 samples from 59 whole patients, not independent validation, clinical performance or a competition leaderboard score.

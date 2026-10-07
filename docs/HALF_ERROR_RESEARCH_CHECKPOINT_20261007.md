# DosePilot half-error research checkpoint, 7 October 2026

## Current result
The half-error target has NOT been achieved. The retained 64-well research candidate remains MSE 0.001042745722096212, p90 patient RMSE 0.037419695944064885. The concrete target is MSE <=0.000521372861048106 at the same 64-well measurement budget, same 24 outputs and nonworse p90. The operating bandwidth-0.7 model remains unchanged, and the accepted Kaggle entry was not edited by this work.

| Procedure | Development MSE | p90 patient RMSE | Decision |
|---|---:|---:|---|
| Retained 64-well research candidate | 0.001042745722 | 0.037419695944 | Keep |
| Operating 64-well bandwidth-0.7 | 0.001058275042 | 0.037894285309 | Keep as operating baseline |
| New global conditional full-curve menu | 0.001058275042 | 0.037894285309 | Reject |
| New patient-deleted acquisition menu | 0.001067069904 | 0.038795846152 | Reject |

## Two completed structural hypotheses

### Global conditional full-curve reconstruction
Learn the joint distribution of all 416 historical TRAIN well measurements using global factors plus full drug-local residual covariance. Condition on only the original 64 purchased cells; reconstruct the exact AUC functionals; apply the existing residual kernel. The three population models (rank 0, 4, 12) were evaluated with an unchanged operating-model fallback. All five inner selections preferred the existing operating family, so the candidate tied its MSE and did not beat the retained research candidate.

The method was frozen at 069380f6706a708882859b918a50ab19d2dae314 before outcome evaluation. Thirteen synthetic tests passed. This is an application of established Gaussian conditioning and covariance shrinkage, not a novel statistical algorithm claim.

A prefit schema check distinguished 328 eligible physical query positions from 416 full historical treatment measurements. Some SN-38 and TAS-102 quadrature nodes are outside the eligible query catalog. The new loader uses full historical TRAIN curves only for fitting while preserving the original eligible query set at inference. It reconstructs the fixed AUCs within 4.44e-16. The initial endpoint-map preflight stopped before any candidate fit; correcting the new experiment's mapping did not alter the operating model or change any query eligibility. This is NOT evidence that the incumbent endpoint calculation was wrong.

### Patient-deleted acquisition risk
Keep exactly two or three native doses per target and sixteen upgrades, but choose doses using exact internal leave-one-fitting-patient-out prediction risk rather than the original in-sample covariance surrogate. Patient deletion includes every organoid and both alternative layouts from that patient; means and scales are recomputed from the remaining patients. Cached sufficient statistics were checked against explicit brute-force refits.

The new planner was chosen in three outer folds, replacing 7, 11 and 4 native doses. Its overall MSE was 0.8311% worse than the operating baseline and 2.3327% worse than the retained research candidate. Only 1/5 outer folds improved versus the operating baseline; p90 worsened. Eight synthetic tests passed, but the predictive improvement test failed. The protocol was frozen at 2eb969756ade0661c66169e201f12862472ef1b4. This is a new risk estimator, not a retry of the rejected variable-dose-count allocation.

## Verification, not independent biological validation
Twenty-one synthetic tests passed across the two studies. Separate saved-model replay code recomputed all ten saved outer-model predictions, using a separately written kernel-distance expression, within 2.22e-16. MSE/p90/fold metrics agreed within 6.94e-18. The verifiers checked 15 and 19 pinned source hashes respectively; these counts include shared dependencies. Neither verification performed a fresh training refit of the complete historical retained candidate.

Both studies kept exactly 64 treatment wells, 32 per plate, and averaged alternative A/B losses only. Poisoning every unpurchased query value left predictions unchanged. Rebuilding outer fold zero after changing its training-ineligible labels and curve values left fitted state and predictions unchanged. The global-curve test also changed that fold's full historical curve vector. No Protected22/Lib2 responses were accessed, and no patient-level rows or prediction/model arrays are published.

All outcomes remain repeated adaptive Lib1 development on 119 samples from 59 patients. The paired bootstrap intervals are descriptive and selection-unadjusted. Passing numerical and isolation checks is not a new biological validation result. Neither failed candidate was promoted or used to overwrite the current submission.

## Handoff
Continue genuinely distinct improvement work through 8 October, Nigeria time; reserve 9 October for final regression, packaging, updating the existing accepted writeup and verifying it saved. The Calendar reminder is already set; do not create a duplicate. Do not rerun these two completed menus or turn a small/tied result into a 2x claim.

The full-grid/eligible-grid distinction is worth auditing before any further acquisition redesign. No action-set expansion has been approved or tested here. Any proposal must state exactly which measurements are allowed and priced; extra historical columns are not free inference measurements. Prior flexible-cardinality, joint fitting, whitening, paired-noise, covariance and nested-mixture results remain closed as recorded in earlier handoffs. New work should add a genuinely different representation, risk principle, or legally usable training evidence rather than cycle the same regularization settings.

Workspace: D:\von-dosepilot-global-conditional64-20261007.
Research branch: dosepilot-global-conditional64-20261007.
Private runs: D:\von-dosepilot-data\global_conditional_curve64_20261007_run1 and D:\von-dosepilot-data\patient_deleted_acquisition64_20261007_run1.
Public aggregate receipts: evidence/global_conditional_curve64_20261007.json and evidence/patient_deleted_acquisition64_20261007.json.

## Method sources checked in this session
Rasmussen and Williams, Gaussian Processes for Machine Learning: https://gaussianprocess.org/gpml/
Official covariance shrinkage documentation: https://scikit-learn.org/stable/modules/covariance.html
Liland, Skogholt and Indahl, exact cross-validation for ridge regression: https://arxiv.org/abs/2211.15128
Cawley and Talbot, selection-criterion overfitting: https://www.jmlr.org/beta/papers/v11/cawley10a.html
Official nested-evaluation example: https://scikit-learn.org/stable/auto_examples/model_selection/plot_nested_cross_validation_iris.html
These sources support method background and evaluation cautions, not the DosePilot performance numbers above.

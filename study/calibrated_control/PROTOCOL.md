# Training-only calibrated interpolation audit

30 September 2026. This is a post-hoc comparator stress test on two already-exposed external tasks. It is not a new independent confirmation, an improved R13 model, or a contest score. The original experiments, gates, splits, exclusions and submitted model remain unchanged.

## Question
Does the reported learned-reconstruction advantage survive a stronger control that learns only an affine calibration of the optimized interpolation AUC? A gain over uncalibrated interpolation alone need not establish that multidose learned reconstruction is necessary.

## Fixed analysis
Use the original eight-drug FORECAST-1 task (21 dose-level readouts; 64 complete community lines/63 patients; 13 complete confirmation patients from the original 19) and the original four-drug matched-CAF task (11 replicate-averaged dose-level readouts; 13 development and 15 confirmation organoid IDs). No new source samples, different targets, added measurements, missing-value imputation or clipping are permitted. Source and saved-prediction hashes are authenticated. The six-drug FORECAST analysis is not used and is not a separate independent cohort.

Keep the independently optimized interpolation acquisition procedure unchanged. Inside each original community five-fold split, or each of the 13 stroma leave-one-organoid-out splits, rebuild its plan using only fitting observations. Learn one slope/intercept per target from that plan's scalar interpolation AUC and its full-curve target. Use equal patient mass for CRC and equal organoid mass for stroma. Feature standard deviation is floored at 0.05, matching the existing model convention.

Select one common option across all targets: identity (no calibration), ordinary least squares, or ridge with penalty 0.01, 0.1, 1, or 10. Minimize pooled group-balanced validation MSE; ties follow that order. This is the complete option set, not a starting point for test-driven search. Refit the selected option on the full original development cohort and its original interpolation plan. Verify that recomputing the full development interpolation plan reproduces the saved plan. Save and hash the calibration before opening confirmation predictions in this execution.

For confirmation, calibrate only the already-saved interpolation outputs. No new physical measurement or original confirmation workbook is opened. The original learned predictions and endpoint are read solely for scoring. Keep every original eligible sample and target, including errors and regressions.

Primary report: equal-group/equal-target MSE for original learned reconstruction, original optimized interpolation, and calibrated interpolation, separately for each task. Also report per-target MSE, strict group wins/ties/losses, p90 group RMSE and a descriptive 10,000-resample paired group bootstrap interval. The interval is not selection-corrected and does not restore untouched-data status. No pooled cross-task score or second independent-validation count is allowed.

The comparator and any failed attempts are retained regardless of result. No model promotion, new Kaggle entry, background job, protected Lib2 access or paid compute is authorized by this protocol. Any publication includes these limitations and the original unsuccessful FORECAST gate.

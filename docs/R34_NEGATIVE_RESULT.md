# R34: nonlinear-head challenger rejected

## Decision

Retain R13. The prespecified additive linear plus Matern-3/2 own-drug predictor produced patient-balanced development MSE **0.001146185234155711**, versus **0.0011448586813828535** for the matching ridge control: **0.1158704% worse**, not an improvement.

Among all 59 patients there were 19 wins, 17 losses and 23 ties. The descriptive paired-patient bootstrap interval for candidate-minus-control MSE was [-0.000003395972790066021, +0.000008011947895615447]. It includes zero. All 24 target and all five fold summaries, including regressions, are retained in `evidence/r34_nonlinear_challenger.json`.

This was one frozen existing-TRAIN experiment. Seven model-algebra/behaviour tests passed before the run. A separate direct recomputation from the frozen prediction arrays agreed with both aggregate MSEs, every target/fold summary and all patient win/loss/tie counts. That verification was performed by the same coordinating assistant, not a separately staffed external reviewer.

No original source workbook or protected Lib2 values were used in this challenger. It made no competition submission or change to the retained fitted model. The prediction arrays remain private. These reused development patients do not establish independent performance, and the outer results were not used to tune another option.

## Frozen experiment specification

Hypothesis: after an identical R13 panel is selected, a patient-weighted additive
linear plus Matern-3/2 kernel can reduce residual nonlinear reconstruction error.
This does not claim invention of kernel ridge regression or new scientific data.
Exactly 119 already-exposed Lib1 samples, 59 patients, 24 outputs, 64 paid wells
per alternative A/B layout. No protected responses or raw source access.
Use unchanged R13 panel selection, patient split salts, feature standardization
and 0.05 scale floor. Refit acquisition and scaling inside every inner fitting
slice. Select ONE global amplitude/penalty pair by the three-fold patient risk;
then refit inside each of the five outer TRAIN partitions. Matern length scale
is fixed at 3. Amplitudes (0,0.1,1), penalties (0.01,0.1,1,10). Amplitude zero
must match the retained ridge control. No adaptation to outer results is allowed.
Score A/B LOSSES, never predictions. Keep all patient and drug regressions.
A candidate passes this development screen only with >=2% lower aggregate MSE,
>=35/59 patient wins, >=4/5 nonworse folds, a negative upper descriptive paired
patient bootstrap bound (10000 draws, seed340034), and no drug MSE increase>10%.
This is exposed development, not independent confirmation or a leaderboard score.
Freeze files before execution. One run; preserve failure or complete result.
Do not change the submitted R13 model based solely on a lower point estimate.

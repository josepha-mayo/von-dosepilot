# von DosePilot
Measurement-aware drug-screen reconstruction

Joseph Ayanda | Model & Algorithm | Updated 30 September 2026

## Overview

DosePilot studies a practical screening decision: repeat a measurement, or spend the same treatment well on another concentration. It combines a retrospective coverage-versus-replication comparison with an operating workflow that checks the identity of every required measurement.

The task reconstructs 24 fixed drug-response summaries from 64 treatment wells. In 119 organoid samples from 59 patients, the retained broader-coverage procedure reduced patient-balanced mean squared error by 33.49% against an earlier paired-well method and 34.13% against a matched paired-native control. All methods used the same target and treatment-well allowance. [E]

Procedure | MSE | RMSE
--- | --- | ---
Earlier paired-well method, R9 | 0.0017214230 | 0.0414900
Matched paired-native control | 0.0017379326 | 0.0416885
Retained broader coverage, R13 | 0.0011448587 | 0.0338358

Against each control, 53 of 59 patients and all five outer-fold means improved. The tradeoff is not uniformly favorable: six drugs and six patients worsened versus R9. Gedatolisib and Palbociclib together worsened by 20.94%. [E]

## What is delivered

A fixed-inventory planner, 24-output predictor, explicit missing-input abstention, exact dose checks and recovery of an intact committed plan. The public software demonstration uses invented measurements and parameters; it is separate from the biological results.

Evidence boundary: repeated retrospective development, not independent validation. Ordinary organoid plates were studied, not prospective organ-on-chip experiments. No clinical benefit, calibrated uncertainty or realized laboratory savings are established.

# Study design
Data, target and physical budget

## Population and fixed endpoint

The source is the colorectal-cancer organoid study by Kryeziu et al. [1]. This project uses a task-specific Lib1 subset: 119 organoid samples, 59 whole patients and 49,504 supplied normalized-viability values. The 119 selected raw records differ from a paper-filtered count of 117. Lesions and repeated samples from one patient remain in one evaluation group. [E]

Each output is a normalized discrete trapezoidal area under the viability curve on a fixed log-dose interval. The two identified plate targets are averaged. Values are not clipped to [0,1]; the endpoint is not IC50, a drug rank or clinical response.

```
y(i,j) = 0.5 * [T_j(v_i,j,plate1) + T_j(v_i,j,plate2)]
```

T_j is the original normalized log-dose trapezoid, with boundary interpolation using the declared native support. This definition is fixed across comparisons. Purchased measurements may contribute to the measured reference, so the result concerns reconstruction of a measured summary, not recovery of a noiseless biological truth.

## Sixty-four treatment wells, not sixty-four free features

R13 chooses two native concentrations for each of 24 drugs plus sixteen third-dose upgrades: 24 x 2 + 16 = 64. One well is read for each selected drug-dose choice. A paired-dose observation in the controls consumes two real wells.

Two complementary layouts assign the selected doses across two plates. Each alternative uses 64 distinct wells, 32 per plate. The intended policy selects one layout independently of outcomes. Historical evaluation averages the two layout losses, never their predictions:

```
expected loss = 0.5 * loss(prediction_A, y)
              + 0.5 * loss(prediction_B, y)
```

The alternatives are not independent patient cohorts and cannot be combined into a free 128-well ensemble. Control wells remain additional and common. The source assay remains a parallel 96-hour process; well counts alone do not establish elapsed-time or financial savings.

# Method
Patient-contained acquisition and prediction

## Choose measurements inside the fitting split

For each drug, the allocator compares native two-dose and three-dose subsets using fitting-only moments and the fixed planning penalty alpha = 0.1. It keeps the best subset of each size, then awards a third dose to the sixteen largest estimated upgrades. A three-dose subset need not contain the best two-dose subset. Ties and ordering are deterministic. [E]

```
subset criterion = Var(y) - c^T (G + alpha I)^(-1) c
```

G is the standardized feature covariance and c the feature-target covariance. This is a regularized fitting objective, not a guarantee of future error. Means, scale factors and the acquisition plan are recomputed in every relevant fitting split.

## Predict across patients, not from a two-point curve fit

Twenty-four ridge heads use only their own drug's two or three measured values. These are predictor features across many training sample rows, not two or three training observations. Intercepts are unpenalized. Feature standard deviations use the original 0.05 floor.

```
beta_j = (G_j + lambda I)^(-1) c_j
prediction_j = mean_y_j + standardized_x_j^T beta_j
```

## Evaluation and final artifact

Five outer folds separate whole patients. Three inner patient folds select one common lambda from {0.01, 0.1, 1, 10} using equal-patient expected-layout loss. Planning, standardization and fitting are contained within those splits. Each sample has weight 1 / (number of patients x samples from its patient); stacked A/B training rows each receive half that mass.

A later construction on all 119 development samples produced the retained operating model, using a new fixed three-fold patient split for penalty selection. The selected penalty was 0.01. This final construction is not another generalization test.

Ridge regression, response-panel prediction and covariance-based acquisition are established methods. The contribution is this task-specific measured design tradeoff and its physical-identity-aware implementation, not a new general regression theory. [2-4]

# Results and limitations
What improves, and what does not

## Main comparison

R13 reduced MSE 33.49% versus R9 and 34.13% versus the matched paired-native procedure at the same treatment-well count. RMSE fell 18.45% versus R9. The p90 of patient expected-risk RMSE fell from approximately 0.051343 to 0.041108. These historical results were not rerun for this report. [E]

Target scope versus R9 | R9 MSE | R13 MSE | Change
--- | --- | --- | ---
Original 22 drugs | 0.0017688991 | 0.0011170971 | 36.85% lower
Gedatolisib + Palbociclib | 0.0011991857 | 0.0014502357 | 20.94% higher
All 24 drugs | 0.0017214230 | 0.0011448587 | 33.49% lower

The six regressing drug averages were Bemcentinib, Gedatolisib, Idasanutlin, LCL161, Palbociclib and SN-38. One layout's worst-patient error also worsened. An improved average or expected-risk tail is not a guarantee for every drug, patient or realized layout.

## Later candidates and a simple control

R18 achieved a slightly lower exploratory MSE, 0.0011414048, but did not pass the original replacement rule. The later prior-centered and functional-covariance variants also failed promotion. R13 remains the retained operational method, not the literal lowest observed point or a proven optimum.

A constant-tail, piecewise-linear log-dose readout on R13-selected measurements had MSE 0.0124455228, but that comparison favored the learned method's acquisition plan. A stricter post-submission control therefore optimized the interpolation policy's **own** measurement locations inside patient-separated training folds while preserving the same 24 targets and 64-treatment-well budget. That separately optimized interpolation procedure reached patient-balanced MSE **0.0024168103**. R13 remained **52.63% lower**, with lower patient-mean error for **59/59 patients** and lower mean error in **5/5 outer folds**. This remains repeated-development evidence and does not prove superiority to every possible interpolation method.

## Interpretation

Repeated trials reused the same development population. Patient-contained nested evaluation prevents within-trial leakage but does not erase selection across rounds. Bootstrap intervals are descriptive. The internal 5% improvement rule is model-selection discipline, not an official scoring formula or probability of winning. Post-submission challengers that changed allocation, regularization, calibration or cross-drug context were rejected when they failed their development gates. The public source replay strengthens reproducibility but does not create an independent predictive estimate.

# Operating workflow
Traceability, abstention and transfer boundaries

Stage | Implemented behavior
--- | ---
Inventory | Checks sample, run, drug, exact numeric dose, unit, plate instance and well.
Plan | Instantiates the supported fixed 64-well policy before values are accepted.
Predict | Complete inputs produce 24 research summaries.
Missing input | Retains the identity row with null; only affected own-drug outputs abstain.
Reject | Wrong dose, duplicate input, unsupported inventory or budget below 64 fails.
Recover | Exports the same intact committed plan after output failure; no new layout.

The model's own-drug coefficient structure makes affected-head abstention exact, not an imputation method. The local commitment ledger prevents repeated selection under the recorded identity, but cannot certify actual laboratory events or prevent a dishonest operator renaming a sample.

## No demonstrated full-24 cross-library transfer

The current R13-to-Lib2 surrogate mapping needs 69-70 existing wells, not 64. The dose-aware prototype also encounters positive-weight Lib2 target support beyond the source range: Gedatolisib at 2,500 nM versus a 1,000 nM source maximum, and Palbociclib at 15,000 nM versus 10,000 nM. A no-extrapolation model must refuse that full request rather than remove targets or invent measurements. [E]

## Independent attempt

The first external attempt failed on a required nonnumeric measurement before predictions or scoring. That value also contributed to the reference target. The original failed attempt and exposure record are preserved; 61 samples from 31 wholly unexposed patients remain reserved. This is neither a model loss nor successful validation.

## Scope

The measured study used conventional organoid plates. Chip-specific channels, flow coupling and tissue dependence were not validated. The software has not established calibrated uncertainty, clinical effectiveness, scientist adoption or realized reductions in material, money or culture time.

# Run, reproduce and inspect
Public code and evidence provenance

## Operating demonstration

```
python -m pip install -r requirements.txt
python run_demo.py --output demo_run_001
```

Run from the repository root with a fresh output directory. The synthetic workflow exercises successful prediction, explicit missingness, invalid-input rejection and same-plan recovery. It requires Python and NumPy, no GPU or model API. Its fictional parameters and values do not reproduce the biological study score.

## Biological reproduction status

The full historical R9/R13 development result can now be reconstructed from the exact public Mendeley Data v3 workbook without the old private input bundle. The public route first authenticates the exact `Data S4.xlsx` bytes, reconstructs the fixed 119-sample / 59-patient Lib1 TRAIN population from input metadata, and decodes exactly 49,504 selected viability values while recording zero Lib2 numerical-response conversions and zero raw-signal conversions. The resulting TRAIN CSV matches its historical SHA-256 byte identity. A fresh isolated environment then rebuilds the plans, fits and predictions through the unchanged scientific engines; all four locked R9/R13 MSE values match within absolute tolerance `1e-12` (maximum observed difference approximately `2.17e-19`). Thirty-four reconstruction/loader tests passed. See `docs/PUBLIC_REPRODUCTION.md` and `evidence/r33_public_pipeline.json`. This establishes reproducibility of the retrospective development result, **not independent biological validation**.

Original project code and documentation are MIT-licensed. External source data and dependencies retain their own rights. No biological workbook, private input arrays, real biological model weights or patient-level outputs are included in the public release. ChatGPT assisted with implementation and documentation; later Muse Spark 1.3 reviews had limited recorded scopes and are not independent biological validation.

## References

[1] Kryeziu et al. (2026). Patient-derived organoids from metastatic colorectal cancer mirror tumor heterogeneity and predict patient survival and drug sensitivity. Cell Reports Medicine, 102840. doi:10.1016/j.xcrm.2026.102840. Source study, not validation of DosePilot.

[2] Abdel-Rehim et al. (2026). Drug response profile-based machine learning enables strategic cell line and compound selection for drug development. Bioinformatics, btag293. doi:10.1093/bioinformatics/btag293.

[3] Xi, Briol and Girolami (2018). Bayesian Quadrature for Multiple Related Integrals. PMLR 80:5373-5382. proceedings.mlr.press/v80/xi18a.html.

[4] Longi et al. (2020). Sensor Placement for Spatial Gaussian Processes with Integral Observations. PMLR 124:1009-1018. proceedings.mlr.press/v124/longi20a.html.

[E] Project evidence: historical R13/R16/R21-R25 records, public R33 source-to-results reproduction, post-submission fixed-budget controls, original study code and aggregate evidence files. Aggregate figures are reported here; patient-level predictions, fitted biological weights and protected independent-study responses are not part of this public repository.

https://github.com/josepha-mayo/von-dosepilot

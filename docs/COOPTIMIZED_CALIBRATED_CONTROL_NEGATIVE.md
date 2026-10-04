# Co-optimized calibrated interpolation control — negative result

**4 October 2026 | same-task repeated development | closed after one prefrozen execution**

## Decision

The co-optimized calibrated-interpolation control is **rejected**. The bandwidth-0.7 additive model remains the development incumbent.

| Procedure | Patient-balanced MSE ↓ | p90 patient RMSE ↓ |
|---|---:|---:|
| Bandwidth-0.7 additive incumbent | **0.001058275042** | **0.0378942853** |
| Co-optimized calibrated interpolation | 0.001438906520 | 0.0480300184 |
| Calibrated original interpolation plan | 0.001786257321 | 0.0525492498 |
| Raw optimized interpolation | 0.002416810289 | 0.0627215219 |

The candidate was **35.97% worse** than bandwidth-0.7. It improved only **3/59** patient means, lost on 56/59, improved **0/5** outer folds, worsened p90, and regressed on **22/24** target means. Its candidate-minus-incumbent patient-balanced MSE difference was +0.0003806315; the descriptive patient bootstrap interval was [+0.0002660721, +0.0004790410]. The interval is not selection-corrected.

## Frozen question and fair comparison

The experiment asked whether a stronger simple comparator could close the gap by jointly choosing:

- one native two- or three-dose subset for each of the same 24 targets;
- exactly 16 third-dose upgrades, giving exactly 64 distinct treatment wells;
- one shared affine-calibration option from `identity, 0, 0.01, 0.1, 1, 10`.

Every choice was made inside the three inner whole-patient folds of each outer training set. The five outer held-patient folds, 119 samples, 59 patients, 24 fixed normalized log-dose AUC targets, equal-patient/equal-target loss, and 32+32 plate accounting were unchanged. A and B remained separately costed 64-well alternatives; their losses, never their predictions, were averaged.

All five outer fits selected unpenalized affine calibration (`0.0`) for the co-optimized control. That materially improved the raw interpolation comparator, but it remained well behind the cross-drug additive residual model.

## Integrity and limits

Four invented-data tests passed before the first Lib1 fit. The once-only execution completed in 72.26 seconds. A separate no-refit verifier then recomputed the candidate/control metrics from the committed prediction array and checked all five plans for 64 distinct wells, 24-target ownership, sixteen three-dose upgrades and complementary 32/32 layouts. It passed.

This is another retrospective result on the repeatedly reused Lib1 development population. It is not independent validation, prospective organ-on-chip evidence, clinical evidence, an official competition score or a claim about rank. No Lib2/Protected22 response was accessed, no cohort or target was dropped, no missing value was imputed, and the accepted Kaggle entry was not changed.

The family is closed: no retry, penalty grid, target/fold splice or rescue on exposed outcomes is authorized.

Machine-readable aggregate evidence: [`evidence/cooptimized_calibrated_control_20261004.json`](../evidence/cooptimized_calibrated_control_20261004.json).

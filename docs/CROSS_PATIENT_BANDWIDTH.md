# Cross-patient bandwidth challenger: rejected on breadth

## Decision

The fitting-only cross-patient median bandwidth challenger is a **prespecified negative result**. It slightly lowered the repeated-development point estimate, from **0.0010582750** for the bandwidth-0.7 incumbent to **0.0010574875** (0.0744%), and improved p90 patient RMSE from **0.0378943** to **0.0378734**. It nevertheless improved only **4/5 outer-fold means**, not the required 5/5. The bandwidth-0.7 model therefore remains the internal incumbent.

This is not independent validation, an official competition score, or a reason to splice models by fold, patient or target.

## What changed—and what did not

The challenger changed only the response-free geometry of the existing additive residual kernel. Within each inner- or outer-training partition, it:

1. used the same R13 acquisition and base prediction context as the incumbent;
2. standardized the paid measurements inside that fitting partition;
3. considered unordered feature-row pairs belonging to different whole patients;
4. computed one weighted-median squared distance per drug group; and
5. normalized each group around the already selected 0.7 bandwidth anchor.

The acquisition plan, 119-sample/59-patient cohort, 24 endpoints, five outer and three inner patient folds, ten residual-spectral options, equal-patient/equal-target loss and exact 64-treatment-well budget (32 per plate) were unchanged. Challenger and incumbent used identical plans in every fit. A/B alternatives were scored by averaging their squared losses, never by averaging predictions from a hidden 128-well design.

The geometry estimator has no outcome argument. Whole-patient identities were passed explicitly, same-patient pairs were excluded, and the bandwidth vector was regenerated inside every fitting boundary.

## Prefrozen gate and observed result

Promotion required every immediate incumbent clause plus the historical R13 and R18 clauses.

| Immediate clause versus bandwidth-0.7 | Required | Observed | Result |
|---|---:|---:|---|
| Patient-balanced MSE | Strictly lower | 0.0010574875 vs 0.0010582750 | Pass |
| Strict patient wins | At least 30/59 | 33/59 | Pass |
| Favorable outer folds | 5/5 | 4/5 | **Fail** |
| p90 patient RMSE | Nonworse | 0.0378734 vs 0.0378943 | Pass |
| Prediction identity | Must differ | Maximum absolute difference 0.0022774 | Pass |

The candidate passed the preserved historical R13 and R18 screens, but that cannot override failure against the current incumbent. Nine of 24 target means regressed: Afatinib, Atorvastatin, Bemcentinib, Idasanutlin, Lapatinib, Luminespib, Napabucasin, Regorafenib and SN-38. The descriptive whole-patient bootstrap interval for candidate-minus-incumbent MSE was **[-1.65e-6, +9.67e-8]**, crossing zero. It is not selection-corrected and was not a gate.

No retry, alternate multiplier, clipping rule, target splice or fold splice was opened after the outcome.

## Verification and privacy boundary

Fifteen fictional-data and decision-boundary tests passed before the biological fit. A separate no-refit verifier then:

- reconstructed all ten outer candidate/control models;
- independently recomputed all 15 inner selections;
- independently recomputed the five outer bandwidth vectors;
- rederived metrics and every gate from the committed predictions; and
- returned `PASS` with `REJECT_RETAIN_BANDWIDTH07`.

The public [aggregate receipt](../evidence/cross_patient_bandwidth_20261004.json) binds the private result, prediction commitment and verification hashes. Patient rows, predictions, the source workbook and fitted biological weights are not published. Protected22/Lib2 responses were not accessed, and the accepted Kaggle entry was not changed.

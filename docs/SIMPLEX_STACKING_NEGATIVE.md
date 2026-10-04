# Patient-balanced spectral stacking: negative result

**Joseph Ayanda | 4 October 2026 | repeated adaptive development**

## Decision

The prefrozen simplex-stacking challenger is rejected. The bandwidth-0.7
additive model remains the current development incumbent.

| Complete procedure | Patient-balanced MSE ↓ | p90 patient RMSE ↓ |
|---|---:|---:|
| **Bandwidth-0.7 incumbent** | **0.001058275042** | **0.037894285** |
| Simplex-stacked spectral settings | 0.001062090133 | 0.038343243 |

The candidate is **0.3605% worse** than the incumbent. It improves 23 of 59
patient means, loses 36, improves only 2 of 5 outer-fold means, worsens p90 and
regresses 16 of 24 target means. Its descriptive patient-bootstrap interval for
candidate-minus-incumbent MSE is `[-4.190e-7, +8.403e-6]`; it crosses zero and is
not selection-corrected. Every immediate promotion clause except prediction
non-equivalence fails.

The candidate still beats the older R13 and R18 development references by
7.23% and 6.95%, respectively, and passes their historical screens. That is not
enough: accepting it would move backward from the stronger current model.

## What was tested

Within every outer-training slice, the procedure rebuilt the exact R13
acquisition, own-drug baseline, bandwidth-0.7 kernel and ten existing residual
spectral settings inside the same three inner patient folds. One global
nonnegative ten-weight vector minimized equal-patient, equal-target and
equal-orientation inner OOF squared loss. The solver exhaustively evaluated all
1,023 nonempty simplex faces; it had no temperature, ridge, top-k parameter or
post-result retry.

The five inner fits used three, three, three, four and three active settings and
improved their corresponding hard-selection inner objectives by 0.105% to
0.626%. That improvement did not transfer to held patients. This is direct
evidence that more flexible inner-model averaging added selection variance here.

The final weights were global—not target-, patient- or orientation-specific—and
their weighted residual coefficients collapsed to one coefficient matrix. Each
orientation therefore still used its own single 64-reading input and original
32/32 plate split. A/B predictions were never averaged and no additional well
was introduced.

## Audit

Ten synthetic and protocol-contract tests passed before fitting. The independent
no-refit verifier then:

- recomputed every metric, comparison and gate;
- verified the convex KKT conditions for all five saved simplex solutions;
- reconstructed all 5,712 held-patient target predictions from the saved models;
- reproduced bandwidth-0.7, additive-1.0, R13 and archived R18 controls; and
- confirmed the exact 64-well, 32-per-plate accounting.

The audit passed. The first attempt is preserved and this stacking rule is
closed; no retuning is authorized to erase the negative result.

## Boundaries

This is the same exposed 119-sample, 59-patient Lib1 development task with all
24 fixed targets. Protected22/Lib2 was not accessed. It is not independent
validation, a prospective organ-on-chip experiment, a clinical-benefit claim or
an official competition score. Private held-patient predictions, training
features and fitted coefficients are not published.

See the [aggregate evidence receipt](../evidence/simplex_stacking_20261004.json)
and the frozen [protocol and source](../study/simplex_stacking/).

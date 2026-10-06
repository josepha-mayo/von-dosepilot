# 72-well global residual-gain study

The frozen 72-well bandwidth-0.7 residual frontier has MSE 0.0009326007417880046. This study tests whether the same residual family is systematically under- or over-applied.

For each outer fold:

1. Rebuild the same 72-well all-three-dose acquisition and the exact same 10 bandwidth-0.7 residual options.
2. Generate all 10 options under 3 whole-patient inner folds.
3. For each non-identity option, apply one frozen global gain from {0.5, 0.75, 1.0, 1.25, 1.5} to the residual correction: base + gain * (option_prediction - base).
4. Include the identity/base option once.
5. Select one option-plus-gain pair by lowest inner OOF patient-balanced full-24 MSE.
6. Refit the residual option on the full outer-training patients and apply the selected gain to held-out outer patients.

No target-wise gains, no orientation-wise gains, and no outer-fold splicing are allowed.

Promotion is not automatic. Versus the frozen global frontier, the research gate requires strictly lower MSE, at least 30 patient wins, 5/5 favorable folds, and p90 patient RMSE nonworse.

Repeated adaptive Lib1 development only. No Protected22 response access.

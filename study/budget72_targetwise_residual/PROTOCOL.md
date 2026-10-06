# 72-well target-wise residual selection

This study keeps the frozen 72-well acquisition and the same bandwidth-0.7 residual family.

For each outer fold:

1. Rebuild the same 72-well all-three-dose base and the exact same 10 residual options.
2. Generate predictions for all 10 options using 3 whole-patient inner folds.
3. For each of the 24 targets independently, select the option with the lowest **inner OOF patient-balanced target MSE**. Ties resolve by the existing option order.
4. Refit all ten options on the full outer-training patients.
5. For each target, use only the option selected from inner folds to predict the outer-held patients.

No outer-fold target result is used to choose an option. No target can be turned off or switched after outer outcomes are observed.

Primary comparison is against the already-frozen global 72-well bandwidth-0.7 frontier (MSE 0.0009326007417880046). Promotion is not automatic; the research gate requires strictly lower MSE, at least 30 patient wins, 5/5 favorable folds, and p90 nonworse versus the global frontier.

This remains repeated adaptive Lib1 development, not independent validation. No Protected22 response access.

# Frozen 72-well additive-kernel bandwidth sweep

The 72-well global frontier currently uses bandwidth multiplier 0.7. This study freezes five multipliers before outcomes:

**0.40, 0.55, 0.70, 0.90, 1.20**

For each multiplier, the exact existing nine residual shrinkage options are retained: spectral fraction {0.1, 0.3, 0.6} × ridge {0.1, 1, 10}. Identity/no correction is shared, giving 46 total options.

Within each outer-training partition, all 46 options are evaluated using 3 whole-patient inner folds. The single lowest inner patient-balanced full-24 MSE option is chosen, then refit on the full outer-training patients and applied to the outer-held patients.

The acquisition stays fixed at 72 treatment wells / 36 per plate. The own-drug base stays fixed at ridge 0.01. No target-wise outer selection, no post-outcome bandwidth changes, and no automatic retry.

Primary comparator: frozen 72-well bandwidth-0.7 frontier, MSE 0.0009326007417880046.

Research gate: strictly lower MSE, >=30 patient wins, 5/5 favorable outer folds, and p90 patient RMSE nonworse versus that frontier.

Repeated adaptive Lib1 development only; no Protected22 response access.

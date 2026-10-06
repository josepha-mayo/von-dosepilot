# 72-well orientation-specific residual selection

The current 72-well bandwidth-0.7 frontier selects one residual option jointly for A and B. This study relaxes only that constraint.

For each outer fold:

1. Rebuild the same 72-well acquisition and the exact same ten bandwidth-0.7 residual options.
2. Generate OOF predictions for all ten options with three whole-patient inner folds.
3. Score each option separately for orientation A and orientation B using equal-patient, equal-target MSE.
4. Select one option for A and one option for B by inner OOF score. Ties use existing option order.
5. Refit on the full outer-training patients and apply the selected A/B options to the held-out patients.

No target-wise option, no target splicing, no new bandwidth, and no gain parameter.

Promotion versus the frozen 72-well global frontier requires strictly lower MSE, at least 30 patient wins, 5/5 favorable folds, and p90 patient RMSE nonworse.

Repeated adaptive Lib1 development only. No Protected22 response access.

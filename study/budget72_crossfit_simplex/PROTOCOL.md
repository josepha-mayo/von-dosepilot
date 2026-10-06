# 72-well cross-fitted global simplex

This stacks three already-frozen OOF predictors that share the same 72 treatment-well acquisition:

1. raw 72-well own-drug base;
2. 72-well bandwidth-0.7 additive residual frontier;
3. 72-well no-retuning control-quality transfer.

Standard plate controls used by predictor 3 are assay QC resources and do not add treatment wells.

For each held outer fold, use only the other four folds' OOF predictions and outcomes. Fit one global nonnegative weight vector (w0,w1,w2), sum=1, minimizing equal-patient squared error across both orientations and all 24 targets. The optimum is solved exactly by checking the interior equality-constrained solution, the three simplex edges, and the three vertices. No weight grid is used.

Apply that same weight vector to every target and both orientations in the held fold. There is no target-wise, orientation-wise, or outer-outcome splicing.

Primary reference is the frozen bandwidth-72 frontier at MSE 0.0009326007417880046. Research successor gate: strictly lower MSE, >=30 patient wins, 5/5 favorable folds, p90 nonworse, all while retaining exactly 72 treatment wells.

Repeated adaptive Lib1 development only. No Protected22 response access. Report regardless of direction. No automatic retry.

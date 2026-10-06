# 72-well low-ridge + bandwidth-0.7 joint study

All five outer folds in the frozen 48–72 budget curve selected base ridge lambda 0.01, the smallest historical value offered. This pre-specified study tests whether that lower boundary was constraining the 72-well model.

The physical acquisition remains fixed at 72 treatment wells, 36 per source plate, with every target using its fitting-only best size-3 native subset.

For each outer fold, use 3 whole-patient inner folds. Evaluate the Cartesian product of:

- base ridge lambda: 0.0001, 0.0003, 0.001, 0.003, 0.01;
- the exact existing ten bandwidth-0.7 residual options: identity plus fraction {0.1,0.3,0.6} × residual ridge {0.1,1,10}.

Every inner candidate rebuilds the acquisition and refits the own-drug base and residual kernel using only the corresponding inner-fitting patients. Select one global pair by equal-patient, equal-target A/B loss. Ties resolve by the fixed grid order. Refit that pair on the full outer-training patients and score the held-out outer patients.

The current 72-well bandwidth frontier (base ridge 0.01, MSE 0.0009326007417880046) is the primary comparator. Research successor gate: strictly lower MSE, >=30 patient wins, 5/5 favorable folds, and p90 nonworse.

No target-wise or orientation-wise selection. Repeated adaptive Lib1 development only. No Protected22 response access. Report regardless of direction.

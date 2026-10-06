# 72-well separate-orientation residual kernels

The current 72-well frontier trains one bandwidth-0.7 residual kernel on A and B examples stacked together. Its orientation MSEs are asymmetric: A is lower than B. This frozen study tests whether the residual mapping itself should be orientation-specific.

For every fitting partition:

1. Rebuild the same 72-well all-three-dose plan.
2. Fit the exact same shared own-drug base at ridge lambda 0.01 using both A and B purchased features.
3. For orientation A only, fit a bandwidth-0.7 additive residual kernel using A standardized paid features and A residuals, with equal total weight per patient.
4. Independently do the same for orientation B.
5. Each orientation uses the exact existing ten residual options: identity plus fraction {0.1,0.3,0.6} x residual ridge {0.1,1,10}.
6. Use 3 whole-patient inner folds to select one global option for A and one global option for B by orientation-specific patient-balanced MSE.
7. Refit both orientation-specific residual models on all outer-training patients and predict the held-out outer patients.

No target-specific choices. No outer-outcome splicing. Treatment acquisition remains exactly 72 wells, 36 per source plate.

Primary comparator: shared-kernel 72-well frontier, MSE 0.0009326007417880046. Research successor gate: lower MSE, at least 30 patient wins, 5/5 favorable folds, and p90 nonworse.

Repeated adaptive Lib1 development only. No Protected22 response access. Report regardless of direction.

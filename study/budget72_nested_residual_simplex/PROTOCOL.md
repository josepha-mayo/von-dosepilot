# Nested residual simplex, 7 October 2026

Question: does convex pooling reduce discrete residual-option selection variance at the same 72-treatment-well budget?

This is a new adaptive-development experiment. Fixed experts are raw own-drug ridge and the existing bandwidth-0.7 residual options (fraction=0.1, ridge=1) and (fraction=0.3, ridge=1). All use exactly the same 72 treatment wells, 36 per source plate; no extra control features are added.

For each of the five outer patient folds, regenerate all ten parent options using the three existing inner patient folds restricted to outer-training patients. Fit one global nonnegative, sum-to-one weight vector for the three fixed experts from these inner out-of-fold predictions and equal-patient squared loss. Solve the convex quadratic by enumerating vertices, edges, and the full-support stationary solution. No target-specific or orientation-specific weights. Refit experts on all outer-training patients, then predict the outer test fold. Never train meta-weights from other OUTER folds' saved OOF predictions.

Reconstruct the parent's inner-selected, ten-option baseline alongside the mixture. Maximum prediction difference from the frozen saved baseline must be <=1e-12. Test outer-label isolation by perturbing only outer fold zero's target labels and requiring the complete fitted weights and predictions for that fold to remain unchanged within 1e-12.

Report all five folds, patient-balanced mean MSE, p90 patient RMSE, patient and target wins/losses/ties (absolute loss tolerance 1e-15), and 100,000-resample paired whole-patient descriptive bootstrap (seed 20261007). Compare both to the 72-well parent and the stored 64-well scientific successor.

Research gate versus 72: lower MSE, at least 30 patient wins, all five fold means lower, and p90 nonworse. Additional 64-well promotion screen: lower MSE, at least 30 patient wins, five favorable folds, and p90 <=0.037419695944064885. Neither screen automatically replaces the approved model or submission.

No independent-validation claim, no prospective/clinical guarantee, no Protected22 access, no automatic retries, no changes to grids or gates after this candidate's outcomes. Private patient rows and prediction arrays stay outside the public repository.

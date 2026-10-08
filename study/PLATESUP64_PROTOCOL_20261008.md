# DosePilot dual-plate AUC auxiliary supervision, fixed 64-well design

## Prespecified protocol, 8 October 2026

The current target equals the arithmetic mean of AUCs from p1/p2 full historical TRAIN response curves. The current residual spectral model trains exclusively on the averaged 24-target label, discarding the separate plate labels available for fitting. Hypothesis: sharing a multi-task spectral subspace between the mean and plate contrast might remove some orientation nuisance while retaining the shared biological signal. This is a new supervised output factorization, not a new measurement scheme and not the earlier full-curve covariance or two-stage dose acquisition.

Four frozen options are evaluated under the SAME original 64-distinct-native-dose plan with 32 wells on each plate and A/B complementary alternative layouts. The own-drug ridge baseline remains fixed lambda0.01 and predicts the 24 averaged targets. Spectral additive bandwidth0.7 options remain exactly identity plus fractions [0.1,0.3,0.6] crossed with ridge [0.1,1,10].

Arms:
1. **mean24**: 24 averaged-target residual channels, numerical reproduction control.
2. **plate48**: 48 channels [full-train-p1-AUC minus ridge, full-train-p2-AUC minus ridge]. Combine the TWO predicted plate targets from one paid orientation to predict their arithmetic mean. This is not averaging predictions across alternative physical layouts.
3. **orthogonal48**: 48 channels [averaged-target residual, 0.5*(full-train-p1-AUC minus full-train-p2-AUC)]. Return only predicted averaged-target residual.
4. **weakcontrast48**: same as orthogonal48 but contrast multiplied by 0.125 rather than 0.5.

Fitting-only patient-weighted centered residual kernel, identical 10 spectral coefficient options. Select one global spectral option per arm from 3 whole-patient inner validation folds fully nested inside 5 unchanged whole-patient outer folds, regenerating physical panel and all model fits in each fitting split. Every arm evaluated on both alternative A/B 64-well layouts; average losses only, never A/B predictions. Only authenticated 119 Lib1 TRAIN samples, 59 whole patients and 24 unchanged AUCs. Full two-plate AUCs are available solely as extra **training labels** for fit subsets, NEVER as inference features, and test labels are used solely for scoring after all predictions are written.

References: operating64 MSE 0.0010582750420801538, scientific64 MSE 0.001042745722096212 and p90 0.037419695944064885. 2x target <=0.000521372861048106 and p90 no-worse. Promotion gate: strict MSE reduction vs both references, at least 30/59 patient wins and 5/5 fold wins vs both, and p90 nonworse, subject to independent research review. No Protected22/Lib2, official leaderboard claims, Kaggle edits, extra assay wells, outcome-selected model blending or automatic promotion. These are repeated adaptive development results, not independent biological validation.

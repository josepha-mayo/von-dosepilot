# Additive bandwidth successor

**3 October 2026. Repeated adaptive Lib1 development, not independent validation.**

The current additive drug-group kernel uses a Gaussian component for each drug's
2/3 purchased coordinates with squared-distance denominator `2 * d`.

This study kept every other component fixed and compared exactly three global
length-scale multipliers before outcome scoring:

- **1.0**: exact additive incumbent;
- **0.7**: narrower drug-group similarity;
- **1.4**: wider drug-group similarity.

Every inner and outer fitting slice rebuilt the original R13 acquisition,
own-drug ridge baseline, centering, scaling, residuals, kernel and model
parameters. The original five outer and three inner whole-patient folds were
unchanged. Each family used the existing ten residual-shrinkage options:
identity plus fraction `{0.1, 0.3, 0.6}` × ridge `{0.1, 1, 10}`.

The task remains 119 Lib1 samples, 59 whole patients, 24 fixed targets, and
exactly 64 physical treatment wells per deployment alternative, 32 per plate.
A/B squared losses are averaged; predictions are never combined into a hidden
128-well ensemble.

Promotion over the additive incumbent required lower mean MSE, at least 30/59
strict patient wins, at least 3/5 favorable outer-fold means, nonworse p90
patient RMSE, and continued passage of the historical R13/R18 screens.

The 0.7 factor passed that screen. The 1.4 factor was rejected. No additional
bandwidths were introduced after seeing outcomes. Protected Lib2 responses,
external confirmation outcomes, clipping, target splicing and missing-value
imputation were not used.

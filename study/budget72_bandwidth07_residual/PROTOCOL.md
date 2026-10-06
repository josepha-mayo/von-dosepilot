# Frozen 72-well bandwidth-0.7 residual transfer

This transfers the existing DosePilot bandwidth-0.7 additive residual family to the frozen 72-well all-three-dose acquisition.

## Fixed acquisition and base

- Public reconstructed Lib1 TRAIN: 119 samples, 59 whole patients, 24 targets.
- Every target uses its fitting-only best size-3 native subset.
- Each A/B deployment uses exactly **72 treatment wells, 36 per source plate**.
- The own-drug ridge base uses fixed lambda **0.01**, which is the selected value in all five outer folds of the frozen seven-point budget curve.
- The 72-well OOF base must reproduce MSE **0.0010055928901387746** and the frozen saved base predictions within 1e-12.

## Residual family

For every fitting partition, stack A and B paid features after own-drug standardization. Fit one additive kernel composed of:

1. a global linear term; and
2. 24 target-group Gaussian kernels, one for each 3-dose target group, with the already-verified global bandwidth multiplier **0.7**.

Use the exact existing residual option grid:

- identity/no residual correction;
- spectral fraction in {0.1, 0.3, 0.6};
- ridge penalty in {0.1, 1.0, 10.0}.

Within each outer-training partition, select one of these 10 options using **3 whole-patient inner folds**. Allocation and kernel fitting are regenerated inside each fitting fold. Then refit the selected option on the full outer-training partition and predict the held-out outer patients.

## Evaluation and gate

Primary: equal-patient, equal-target mean of separate A/B squared errors.

Secondary: p90 patient RMSE, patient wins, target-average wins, all five outer-fold MSEs, and a prespecified 100,000-resample descriptive whole-patient bootstrap versus the frozen 72-well base.

Promotion is not automatic. The frozen research gate requires:

- strictly lower MSE than the 72-well base;
- at least 30/59 patient wins;
- **5/5** favorable outer folds;
- p90 patient RMSE nonworse.

The current 64-well scientific successor is a comparator only.

## Boundary

Repeated adaptive Lib1 development, not independent validation. No Protected22 response access. No budget change after outcomes. No automatic retry.

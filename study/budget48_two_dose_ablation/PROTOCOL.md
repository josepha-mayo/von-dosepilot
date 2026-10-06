# Budget48 two-dose ablation protocol

## Scientific role

Post-hoc **measurement-budget ablation**, not candidate selection or independent validation.

## Fixed population and endpoint

- Public reconstructed Lib1 TRAIN only: 119 organoid samples, 59 whole patients, 24 fixed normalized log-dose AUC targets.
- Input curve SHA-256: `b192dc242362d74c4faa941752792336c7610d9bd403cccbf1cee7a8a1fc7c94`.
- Catalog SHA-256: `84eae3976307448ac696852d39d1b2376cce479d8af5e386ce04097020deff5e`.
- No Lib2 / Protected22 response access.

## Only experimental variable

**48-well arm:** for each target, use the exact fitting-only best size-2 native subset already defined by the R13 allocation objective. Every target therefore has exactly two purchased treatment wells. Orientation A assigns the two ordered native doses to p1/p2; orientation B flips them. One deployment is exactly 48 treatment wells, 24 per source plate.

**64-well arm:** unchanged R13 single-well procedure: best size-2 or size-3 native subset per target, with the sixteen largest fitting-only third-dose upgrade gains promoted to three doses. One deployment is exactly 64 treatment wells, 32 per source plate.

No target is dropped. No output definition changes. No downstream control-quality, spectral, additive-kernel, or successor calibration is used in either arm.

## Evaluation

- Outer whole-patient folds: 5, salt `von-organoid-sentinel-v1|outer`.
- Within each outer-training set, each arm independently selects one shared ridge penalty from `[0.01, 0.1, 1.0, 10.0]` using 3 whole-patient inner folds and the same outer-specific salt used by R13.
- Allocation is regenerated using fitting rows only inside every inner/outer training split.
- A/B orientation predictions are never averaged. The loss is the equal average of A and B squared errors.
- Primary metric: equal-patient, equal-target full-24 MSE.
- Secondary: p90 patient RMSE, five outer-fold MSEs, patient win count, target-average win count.

## Integrity gates

1. The reproduced 64-well arm must match historical R13 MSE `0.001144858681382854` within absolute `1e-12`.
2. Every 48-well plan must contain 48 distinct native doses, exactly 2 per target, 24 p1 + 24 p2 per orientation.
3. Every 64-well plan must satisfy the existing frozen validator.
4. No patient crosses an inner or outer split.
5. Report the 48-vs-64 result regardless of direction.
6. No retry or post-outcome change of the 48-well rule.

# 72-well global quadratic interaction augmentation

The current frontier uses a global linear term plus 24 target-group Gaussian kernels. This study adds one homogeneous degree-2 polynomial kernel over all 72 standardized paid coordinates:

```text
K_quad(x,z) = 72 * (x^T z / 72)^2
```

This is PSD and has a typical diagonal scale comparable to the summed local Gaussian block when standardized feature norm squared is about 72.

Candidate kernel:

```text
K = K_bandwidth0.7_additive + eta * K_quad
```

Frozen eta values: **0, 1/16, 1/8, 1/4, 1/2, 1**. Eta=0 is exactly the incumbent frontier.

For each outer fold, 3 whole-patient inner folds choose one global (eta, residual spectral option) pair. The residual option grid is unchanged: identity plus fraction {0.1,0.3,0.6} x ridge {0.1,1,10}.

No target-wise or orientation-wise interaction strength. No outer-result splicing. Treatment budget remains exactly 72 wells, 36 per plate.

Primary comparator: 72-well bandwidth frontier MSE 0.0009326007417880046. Successor gate: lower MSE, >=30 patient wins, 5/5 favorable folds, p90 nonworse.

Repeated adaptive Lib1 development only. No Protected22 response access. Report regardless of direction. No automatic retry.

# 72-well global-RBF augmentation

The current frontier uses a linear term plus 24 additive target-group Gaussian kernels. This study adds one **full 72-dimensional Gaussian RBF kernel** to capture nonlinear cross-target state interactions while keeping the exact same 72 treatment wells, patient folds, base ridge, and local bandwidth 0.7.

For standardized purchased feature vectors z and z':

```text
K_global(z,z') = 72 * exp(-||z-z'||^2 / (2*72))
```

The factor 72 matches the summed diagonal scale of the 24 local group Gaussian terms (24 groups x width 3). The candidate kernel is:

```text
K = K_bandwidth0.7_additive + eta * K_global
```

Frozen eta values: **0, 1/16, 1/8, 1/4, 1/2**. Eta=0 is exactly the incumbent frontier kernel.

For each outer fold, 3 whole-patient inner folds choose one global (eta, residual spectral option) pair among 5 x 10 candidates. No target-wise or orientation-wise strength. No outer-result splicing.

Primary comparator: frozen 72-well bandwidth frontier MSE 0.0009326007417880046.

Successor gate: strictly lower MSE, >=30/59 patient wins, 5/5 favorable outer folds, p90 nonworse.

Repeated adaptive Lib1 development only. No Protected22 response access. Report regardless of direction. No automatic retry.

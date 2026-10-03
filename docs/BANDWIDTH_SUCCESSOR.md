# von DosePilot bandwidth successor

**Joseph Ayanda | 3 October 2026 | repeated adaptive development**

## Decision

The additive drug-group kernel remains the model family, but its global Gaussian group lengthscale changes from the historical multiplier **1.0** to **0.7**. This candidate clears the incumbent-facing promotion screen and the historical R13/R18 screen without changing one purchased well.

| Procedure | Patient-balanced MSE ↓ | p90 patient RMSE ↓ |
|---|---:|---:|
| Original R13 | 0.001144858681 | 0.041107825 |
| Previous additive incumbent | 0.001060552730 | 0.038073112 |
| **Bandwidth-0.7 additive successor** | **0.001058275042** | **0.037894285** |

The gain versus the previous additive incumbent is **0.2148%**, small but broad: **38/59 patient means improve, all 5/5 outer folds improve, and p90 improves**. The descriptive paired-patient interval for candidate-minus-incumbent mean loss is **[-4.159e-6, -4.157e-7]**.

Against R13, the candidate is **7.5628% lower MSE**, wins **49/59** patient means and all five folds. Against the archived R18 patient-loss ledger it is **7.2831% lower**, wins **47/59** patients and all five folds. Both candidate orientation-wide MSEs, **0.0011047522** and **0.0010117979**, remain below the expected MSE of each historical reference.

This is not independent validation. It is another model selected after substantial reuse of the same Lib1 development population.

## What changed

The previous additive residual kernel used, for every drug group j,

`d_j * exp(-||z_j-z'_j||^2 / (2 d_j))`

plus the unchanged linear 64-coordinate kernel.

The successor changes only the Gaussian denominator:

`d_j * exp(-||z_j-z'_j||^2 / (2 d_j * 0.7^2))`.

So the nonlinear group kernel is narrower in the base-standardized purchased-value space. Acquisition, own-drug ridge baseline, patient folds, residual spectral grid, endpoints and physical budget are unchanged.

The study prefroze exactly three bandwidth families: **1.0** (exact incumbent), **0.7**, and **1.4**. No further bandwidths were added after outcomes. The wider 1.4 model regressed to MSE 0.001063709359, with 18/59 patient wins and zero favorable folds, and is rejected.

## Containment and physical accounting

Every inner and outer fitting slice independently rebuilds:

- the original R13 64-well acquisition;
- the own-drug baseline at ridge 0.01;
- fitting means/scales;
- the bandwidth-specific additive kernel;
- one option from the unchanged ten residual settings.

The 0.7 and 1.0 candidates use **identical physical plans in all five outer folds**. Each deployment purchases exactly **64 distinct treatment wells, 32 per plate**. A/B are alternative deployments; their squared losses are averaged. Their predictions are never averaged into a hidden 128-well ensemble.

The 1.0 control reproduces the previously verified additive predictions exactly, with maximum prediction difference **0.0**.

## What did not improve

Only **14/24 target mean errors are nonworse** than the previous additive model. Ten regress:

Afatinib, Bemcentinib, Encorafenib, Idasanutlin, LCL161, Lapatinib, Regorafenib, SN-38, Trametinib, and Volasertib.

The successor is promoted because the predeclared overall patient/fold/tail screen passes, not because every slice improves.

## Public-input reproduction

The new runner rebuilds the study from the same hash-bound public-derived Lib1 TRAIN CSV, without historical predictions or the old private metadata kit:

```bash
python study/hybrid_residual/reproduce_bandwidth.py \
  --curves reconstructed_train/train_curves.csv \
  --output bandwidth_replay \
  --fit-final
```

A fresh replay reproduced:

- bandwidth-0.7 MSE: **0.0010582750420801538**
- previous additive MSE: **0.001060552730112811**
- R13 MSE: **0.0011448586813828537**
- **38/59** patient wins versus additive
- **5/5** favorable folds.

The final all-TRAIN constructor selected spectral fraction **0.1** and ridge **1.0**. Construction is not another validation estimate. The fitted archive contains training feature vectors and must remain private.

## Inference verification

The constructed model has its own model kind: `dosepilot.additive_kernel_bandwidth.v1`. The inference backend verifies the stored bandwidth metadata before evaluating the kernel.

On the author's machine, all **238 sample/orientation training-record requests** matched direct matrix evaluation within **2.22e-16**. Every one of the **64 single-missing-position cases** withheld the primary output. These are software checks on training records, not new biological samples.

The current model also has a dedicated durable lifecycle at
`study/durable_runtime/bandwidth_lifecycle.py`. It binds the bandwidth model,
plan, construction trust anchor and runtime sources into a fresh commitment;
enforces recovery history; and restores lost exports without rewriting the
authoritative ledger. See [Bandwidth-0.7 durable lifecycle](BANDWIDTH_LIFECYCLE.md).
The older additive-1.0 compiled speed result remains separately labelled and
is not transferred to this backend.

## Evidence boundary

No Lib2 response was read. Protected22 remains exposed and its full primary remains not estimable. No external cohort was newly evaluated. The live Kaggle entry was not silently replaced by this model. The public demo remains a fictional operating demonstration.

The current result is a stronger **development** model, not proof of clinical benefit, prospective cost savings, or a competition win.

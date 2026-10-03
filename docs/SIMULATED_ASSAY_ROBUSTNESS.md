# DosePilot simulated assay-robustness audit

**Joseph Ayanda | 3 October 2026 | synthetic software stress test**

This audit holds the verified bandwidth-0.7 model, outer-fold fits, patient splits, physical plans, and 64-well budget fixed. It changes **only the purchased values presented at inference**. No model is refit or selected from these outcomes.

It is **not biological validation** and it is **not an estimate of actual organ-on-chip assay CV**. The perturbations are deliberately simple synthetic failure modes meant to expose sensitivity before any prospective wet-lab claim.

## Frozen reference

The unperturbed replay exactly reproduces the current development incumbent:

| Metric | Frozen value |
|---|---:|
| Patient-balanced MSE | **0.001058275042** |
| p90 patient expected RMSE | **0.037894285** |
| Purchased treatment wells per A or B deployment | **64** |
| Per source plate | **32 + 32** |
| Saved-prediction parity | **0.0 max difference** |

A and B remain separate 64-well deployments. Each is perturbed and predicted independently; only their **losses** are averaged.

## Independent random measurement noise

For each purchased coordinate, the audit adds independent Gaussian noise of
`N(0, sigma * training_scale_x)`, which is equivalent to `sigma` noise in the model's standardized z-space. Five fixed seeds are used: 11, 29, 47, 83, and 131. No values are clipped.

| Sigma in z-space | Mean MSE | Mean MSE change vs frozen | Worst seed MSE |
|---|---:|---:|---:|
| 0.01 | 0.001058934 | **+0.062%** | 0.001059367 |
| 0.05 | 0.001072857 | **+1.378%** | 0.001076917 |
| 0.10 | 0.001117345 | **+5.582%** | 0.001123921 |

The model is fairly insensitive to the smallest independent perturbation in this toy stress test. At 10% of a training feature scale, the effect is no longer small.

These numbers should **not** be translated into assay-CV claims. They depend on this synthetic noise definition and the repeatedly reused Lib1 development population.

## Coherent single-plate calibration drift

The harsher test multiplies every purchased reading assigned to one source plate by 0.95 or 1.05, with no clipping. The other plate is left unchanged.

| Synthetic plate perturbation | MSE | Relative change |
|---|---:|---:|
| p1 × 0.95 | 0.001235812 | **+16.78%** |
| p1 × 1.05 | 0.001211491 | **+14.48%** |
| p2 × 0.95 | 0.001231380 | **+16.36%** |
| p2 × 1.05 | 0.001214539 | **+14.77%** |

This is the important failure mode. A coherent plate-level scale error is much more damaging than small independent noise.

The engineering implication is concrete: **future laboratory integration needs explicit plate-level calibration and QC before trusting prediction output.** The current evidence does not establish a numeric QC threshold, and no control-based recalibration rule is being claimed as validated.

## Missing purchased value

The current bandwidth model depends on all 64 purchased inputs. Existing runtime verification checks all 64 single-missing positions.

**Result:** one missing required reading causes the primary prediction to be withheld. There is no silent imputation and no free replacement treatment well.

The separately labelled older own-drug baseline recovery path can still expose unaffected historical baseline heads, but those are not bandwidth-model predictions and are never given the bandwidth model's headline accuracy.

## Reproduce this audit

First reproduce the bandwidth model from the public-derived TRAIN route:

```bash
python study/hybrid_residual/reproduce_bandwidth.py \
  --curves reconstructed_train/train_curves.csv \
  --output bandwidth_replay \
  --fit-final
```

Then run the frozen robustness audit:

```bash
python study/hybrid_residual/simulate_bandwidth_robustness.py \
  --study study \
  --curves reconstructed_train/train_curves.csv \
  --replay bandwidth_replay \
  --runtime-receipt FINAL_RUNTIME_VERIFICATION.json \
  --output robustness.json
```

The author's independent public-route replay reproduced the frozen robustness report with result SHA-256
`a0d5d405a9f7e4965a94917975cab8e065a59f7139486b7ab205306b55677723`.

## What judges should take from this

The positive result is **not** “DosePilot is robust to lab noise.” That would be too strong.

The defensible result is:

- the model's exact current software path can be stress-tested without changing the 64-well budget;
- small independent standardized perturbations have modest effect under this simulation;
- coherent plate-level drift is a clear weakness;
- missing purchased readings are handled by withholding, not by inventing data;
- therefore, plate calibration/QC is a priority item in a future prospective biological validation contract.

That is a more useful readiness statement than pretending software replay is already wet-lab robustness.

See the machine-readable aggregate receipt at
`evidence/bandwidth_robustness_20261003.json`.

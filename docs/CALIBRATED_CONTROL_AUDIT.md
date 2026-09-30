# Stress test: can simple calibration explain the external gains?

30 September 2026. This is a **post-hoc comparator audit on already exposed external data**, not another independent confirmation. The original R13 model and accepted competition entry are unchanged.

## Why add this control?

The existing interpolation comparator optimizes its own dose selection, but its final AUC readout is not calibrated. A learned reconstruction model might beat it partly by correcting systematic scale or offset errors. This audit therefore adds a slope and intercept to each drug's interpolation output, without purchasing another measurement or using another drug's features.

The original interpolation acquisition procedure is retained. It is rebuilt inside every development split. Calibration is fitted on those training rows only; one common option across all drugs is selected by development cross-validation: identity, ordinary least squares, or ridge penalties 0.01, 0.1, 1, and 10. The original patient-grouped five-fold splits are used for the colorectal-cancer task, and leave-one-organoid-out splits for the stromal task. Full-training plans must exactly reproduce the previous saved interpolation plans.

This is a stronger readout control, not an optimization of dose acquisition specifically for calibrated interpolation and not a search over every alternative model.

## Completed results

All numbers below are mean squared errors on the original eligible external observations, with the original endpoint and measurement count unchanged. Lower is better.

| External task | Original learned reconstruction | Optimized interpolation | Training-calibrated interpolation |
|---|---:|---:|---:|
| FORECAST-1: 13 complete patients, 8 drugs, 21 dose-level readouts | **0.0021714654** | 0.0038551794 | 0.0028731430 |
| Matched-CAF coculture: 15 organoid IDs, 4 drugs, 11 replicate-averaged dose-level readouts | **0.0029697117** | 0.0052366266 | 0.0058699031 |

### FORECAST-1: the advantage narrows

Development selected calibration penalty 0.01. Against this calibrated control, learned reconstruction has **24.42% lower MSE**, wins 9 of 13 patient means, and wins 5 of 8 drug MSEs. This is a smaller advantage than the original 43.67% comparison against uncalibrated interpolation.

The descriptive paired-patient interval for learned-minus-calibrated MSE is **[-0.0015859, +0.0001052]**, which includes zero. The result does not support a claim of decisive superiority over this stronger control. The six incomplete patients remain excluded under the original full-eight-target rule; they have not been silently replaced or counted as wins. The original support gate failed and remains failed.

### Stromal coculture: calibration did not rescue interpolation

Development selected calibration penalty 0.1. On the existing coculture confirmation, this calibration performed worse than the original interpolation control. Learned reconstruction has **49.41% lower MSE** than the calibrated version, winning 12 of 15 organoid means and 3 of 4 drug MSEs. The descriptive paired-organoid interval is **[-0.0055898, -0.0007202]**.

Because raw interpolation achieved the better comparator score here, **retain the more conservative 43.29% advantage against raw interpolation as the headline**. The original four-part stromal gate remains passed, but this new audit does not supply another independent pass. Distinct organoid IDs are not proof of distinct patients.

## Execution and checks

The new calibration was saved and hashed before loading confirmation predictions in this execution. Confirmation inputs were the previously saved interpolation AUCs, not newly opened raw confirmation measurements. Both tasks were already exposed before this audit was proposed, so this ordering does not restore blinding.

All **14 unique synthetic tests** passed. Tests cover weighted least-squares equivalence, affine recovery, constant inputs, patient-balanced weights, fold leakage, target isolation, invalid inputs, and identity fallback. The exact four downloaded source files matched their tested SHA-256 values.

The original full-training interpolation plans and old learned/interpolation errors reproduced. A second implementation recomputed every target metric and the cross-validation choice, and reconstructed saved calibrated predictions with maximum difference **2.22e-16**. Weighted augmented least-squares coefficient checks agreed within **4.44e-16**. These are coordinator-authored checks, not an independent external review.

The [aggregate execution receipt](../evidence/calibrated_interpolation_audit_20260930.json) records source, model, prediction and original result hashes. The [frozen protocol](../study/calibrated_control/PROTOCOL.md) and [source](../study/calibrated_control/) are public. An initial transcription error in the companion receipt's protocol digest was corrected; executed source and scientific outputs were not changed.

## Reproduction and access limits

The numerical unit tests require NumPy:

```bash
python -m unittest discover -s study/calibrated_control -v
```

The audit runner expects the original, locally retained directory structure and hash-bound outputs of the two external studies:

```bash
python study/calibrated_control/run_calibration_audit.py --project-root /path/to/von-dosepilot-audit-20260930 --output /path/to/new_calibration_audit
```

Required inputs include the community workbook, each source backend, the historical interpolation plan and freeze, the stroma development cache, and the two original confirmation prediction files with their manifests. Exact paths and hashes are enumerated in the runner. See [the external CRC study](EXTERNAL_CRC_CONFIRMATION.md) and [the stromal study](STROMA_CONTEXT_CONFIRMATION.md) for the earlier workflows. A bare repository clone does not include those patient-level caches, and this runner does not fabricate or automatically replace missing inputs. Reproducing a result is not another independent experiment.

No patient arrays, fitted weights, raw workbook, or RLU data are published in this update. The repository includes code and aggregate evidence only. Keep generated output directories private. No protected Lib2 outcomes, clinical endpoints, new samples, imputed values, additional measurements, model promotion, or official competition-score change occurred.

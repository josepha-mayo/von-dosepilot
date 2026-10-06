# Current successor grouped reliability diagnostic

DosePilot now publishes a **post-hoc patient-grouped uncertainty diagnostic** for the 6 October scientific successor. This does not change the model, acquisition budget, or MSE.

Each patient is the calibration unit. For every target and A/B orientation, the score is the **maximum absolute OOF residual across all organoid samples belonging to that patient**. For each held-out outer patient fold, interval radii are calibrated from the other four OOF folds only.

| Nominal level | Observed grouped coverage | Orientation A | Orientation B | Lowest target coverage | Targets at/above nominal |
|---|---:|---:|---:|---:|---:|
| 80% | 81.00% | 81.00% | 81.00% | 79.66% | 19/24 |
| **90%** | **91.95%** | **91.74%** | **92.16%** | **90.68%** | **24/24** |
| 95% | 95.94% | 96.12% | 95.76% | 94.92% | 19/24 |

The machine-readable receipt also contains per-target/per-orientation calibration radii computed from all 59 OOF patient scores as a **deployment-preparation artifact**.

## Boundary

This is not independent validation and not a prospective conformal guarantee. Lib1 was repeatedly inspected during model development, so the diagnostic is selection-naive. Cross-fold calibration prevents using an evaluated patient's own residuals to set that fold's interval, but it does not erase the broader adaptive-development history.

No patient-level residual rows or prediction arrays are published. Protected22/Lib2 is not accessed.

Verify the public aggregate receipt:

```bash
python study/audits/verify_current_successor_grouped_conformal.py --root .
```

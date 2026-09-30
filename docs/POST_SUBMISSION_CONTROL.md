# Post-submission control: separately optimized interpolation policy

30 September 2026.

To avoid giving the learned R13 readout an unfair panel advantage, a new piecewise-linear log-dose interpolation baseline was allowed to optimize its own acquisition policy inside each patient-separated training fold. It used the same 24 targets and the same 64 physical treatment wells per deployment, with 32 wells from each plate. R13 predictions were not used to fit or select the interpolation policy.

| Procedure | Patient-balanced MSE |
|---|---:|
| Separately optimized interpolation | 0.002416810289196867 |
| Retained R13 | 0.001144858681382854 |

R13's error was 52.6294% lower. R13 had lower patient-mean error for 59/59 patients and lower mean error in all five outer folds. The interpolation policy's orientation-specific MSEs were 0.0025303844536349925 (A) and 0.0023032361247587413 (B).

This is a stronger task-specific baseline, not proof of universal superiority to interpolation and not independent validation. The finite interpolation policy class can still be imperfect, and all 59 patients belong to the repeatedly reused development cohort.

The fixed result is summarized in `evidence/optimized_interpolation_control.json`. No Lib2/protected responses were accessed and no official judge score is claimed.

## Reproduce this comparison without the private input kit

The original policy, public-CSV adapter and regression tests are now under `study/audits/`. Follow [the comparison reproduction guide](REPRODUCE_COMPARISONS.md). The public-input replay matched the optimized control, R13 and the earlier readout control within `1e-12`; all 24 interpolation and shift-constraint tests passed. [The replay receipt](../evidence/public_comparison_replay_20260930.json) records exact code and result hashes.

The separate shift-constraint hypothesis also has executable code. All five inner selectors chose the original R13 model, producing no gain; it was not promoted. Neither code publication nor reproducing the existing comparison changes the scientific validation level.

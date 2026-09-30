# Reproduce the post-submission comparisons

30 September 2026. The retained method remains R13. This addition makes the stronger interpolation comparison executable from the public input route, and preserves a rejected shift-constraint experiment.

## Prepare the public inputs once

Follow [public-workbook reproduction](PUBLIC_REPRODUCTION.md) from the repository root, using the pinned study environment. Its commands create `reconstructed_train/train_curves.csv` and `reconstructed_results/r13`. No private 16-file metadata kit is needed. Reuse those verified outputs rather than opening the workbook again.

The comparison scripts authenticate the original study lock, all 16 scientific engines, dependency versions and exact TRAIN CSV hash. The optional `--private-legacy-inputs` flag exists only for explicit historical compatibility checks; it is neither required nor an automatic fallback.

## Separately optimized interpolation

```bash
python study/audits/reproduce_interpolation.py --study study --curves reconstructed_train/train_curves.csv --r13-run reconstructed_results/r13 --output interpolation_comparison
```

Use a new output directory. The script optimizes the interpolation policy on each outer training fold, commits its held-patient predictions, and only then opens the R13 comparison predictions. R13 predictions never train or select the interpolation policy. A second, sample-by-sample trapezoid implementation checks the predictions. Masking every unpurchased input must leave them unchanged.

Expected equal-patient development MSEs, tolerance `1e-12`:

| Complete procedure | MSE |
|---|---:|
| Retained R13 | 0.001144858681382854 |
| Interpolation with its own optimized acquisition | 0.002416810289196867 |
| Earlier interpolation readout on R13-selected panels | 0.012445522811884428 |

R13 has 52.6294% lower error than the separately optimized control, with 59/59 patient-mean and 5/5 fold-mean wins. This is the existing fixed comparison reproduced through a new input interface, not a newly lowered R13 error. The finite interpolation class uses two or three native doses per drug and exactly sixteen third-dose upgrades. It is not an optimization over all interpolation or experimental-design methods.

## Shift-constraint experiment: not promoted

```bash
python study/audits/evaluate_shift.py --study study --curves reconstructed_train/train_curves.csv --output shift_comparison
```

The hypothesis constrains each own-drug head's raw coefficients to sum toward one. The full constraint makes an additive shift of all purchased measurements for one drug produce the same output shift. That algebraic property does not establish laboratory robustness, remove an intercept or validate transfer to another assay.

The experiment selects one common constraint strength from `{0, 0.5, 1}` and one common ridge penalty from `{0.01, 0.1, 1, 10}` within three inner whole-patient folds. Acquisition and preprocessing are rebuilt in each fitting slice. All five outer folds selected strength zero and penalty 0.01. The resulting predictions equal R13: 59 patient ties, no predictive gain. The internal promotion rule fails, so R13 remains unchanged.

The public-CSV execution is a compatibility replay of that same hypothesis, not another independent validation experiment.

## Tests and verified execution

```bash
PYTHONPATH=study/engine python -m unittest discover -s study/audits -v
```

On Windows, set `PYTHONPATH` to `study/engine` in the current shell before running the same Python command. There are 11 invented interpolation tests and 13 invented constraint tests. All 24 passed in the existing isolated, pinned R33 environment. All seven new source files matched the locally tested SHA-256 values.

Both public-input comparisons completed. The interpolation replay matched all three expected metrics and its separate trapezoid check differed by at most `4.44e-16`. Aggregate outcomes, code hashes, protocol hashes and exact private result-file hashes are recorded in [the public replay receipt](../evidence/public_comparison_replay_20260930.json).

## Boundaries

Every deployment alternative purchases 64 physical treatment wells, 32 per plate, for all 24 targets. Only the two alternative losses are averaged, never their predictions. The 119 samples from 59 whole patients are repeatedly reused development data. Neither these comparisons nor their reproduction establish independent clinical or organ-on-chip validation, calibrated uncertainty, actual laboratory savings or a competition rank.

No protected Lib2 outcomes or source workbook were opened by these comparison runs. The original workbook reconstruction remains a separate, previously recorded R33 stage. Generated output folders contain patient-level predictions, plans and fitted weights: keep them outside public commits. The repository contains only original code, fictional tests, patient-free metadata and aggregate evidence. No competition entry was replaced by this update.

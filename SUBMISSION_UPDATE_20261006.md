# DosePilot submission update - 6 October 2026

The immutable 4 October evidence snapshots remain preserved. This page points reviewers to the stronger 6 October adaptive-development result without rewriting those older receipts.

## Current lowest verified development result

**Orientation-specific control-quality rank-1:** patient-balanced full-24 MSE **0.001042745722**, p90 patient RMSE **0.037419696**.

Versus the public bandwidth-0.7 baseline (0.001058275042):

- **1.4674% lower MSE**
- **40/59 patient wins**
- **5/5 favorable outer folds**
- **19/24 target-average wins**
- unchanged **64 treatment wells / 32 per source plate** physical acquisition

Versus original R13 (0.001144858681):

- **8.9193% lower MSE**
- **49/59 patient wins**
- **5/5 favorable outer folds**
- **22/24 target-average wins**

The frozen verifier reconstructs **5,712 held-target predictions**; a fresh Windows replay had maximum difference **2.22e-16**, below the frozen **5e-16** tolerance, with no Protected22 access.

This remains repeated adaptive development on the same 59-patient Lib1 population. The immediate 0.001043179589 predecessor is only 0.0416% worse and wins two of five folds against the current candidate, so no claim of uniform incremental superiority is made.

## Reviewer files

- [6 October Kaggle writeup](docs/KAGGLE_WRITEUP_20261006.md)
- [6 October technical report PDF](docs/DosePilot_Technical_Report_20261006.pdf)
- [Diffable report source](docs/DosePilot_Technical_Report_20261006.md)
- [Current model note](docs/CONTROL_QUALITY_SUCCESSOR_20261006.md)
- [Machine-readable result](evidence/orientation_specific_control_quality_rank1_20261006.json)
- [Implementation and frozen protocol](study/orientation_specific_control_quality_rank1/)

Historical 4 October writeup/report/evidence remain untouched so their recorded hashes continue to mean what they said at the time.

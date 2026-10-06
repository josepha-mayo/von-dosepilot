# DosePilot submission update - 6 October 2026

**Category:** Model & Algorithm  
**Team:** von DosePilot (solo)  
**Author:** Joseph Ayanda

The immutable 4 October evidence snapshots remain preserved. This page is the fast route to the stronger 6 October adaptive-development result without rewriting those historical receipts.

**Required deliverables:** [public repository](https://github.com/josepha-mayo/von-dosepilot) · [75-second demo video](https://youtu.be/QeOGJIgx378) · [live fictional-data demo](https://von-dosepilot.netlify.app) · [6 October Kaggle writeup](docs/KAGGLE_WRITEUP_20261006.md) · [9-page technical report](docs/DosePilot_Technical_Report_20261006.pdf)

## 90-second judge path

### 1. Problem importance and impact - 30%

DosePilot treats sparse drug screening as a **measurement-design + reconstruction + provenance** problem. A deployment commits **64 identified treatment wells, 32 per source plate**, from a retrospective source profile containing 416 eligible treatment measurements, then reconstructs 24 fixed normalized log-dose AUC summaries.

The 64/416 comparison is explicitly a **measurement-count compression** claim, not a claim of 84.62% lower real laboratory cost, material, or elapsed time.

### 2. Technical approach and innovation - 30%

The model stack is:

1. fitting-contained 64-well acquisition;
2. own-drug ridge reconstruction;
3. bandwidth-0.7 cross-drug residual geometry;
4. an orientation-specific **rank-1 standard-control calibration** that uses plate QC summaries without purchasing additional treatment wells.

Orientation B uses an 11-feature control-quality basis at replacement strength 1/3. Orientation A uses a more conservative seven-feature level basis at strength 1/9. Recorded rank-2 through rank-4 variants, robustized bases, and target-gated variants all regress and remain negative evidence.

### 3. Results and validation - 20%

The current lowest verified Lib1 adaptive-development point estimate is:

**patient-balanced full-24 MSE 0.001042745722, p90 patient RMSE 0.037419696.**

Versus the public bandwidth-0.7 baseline (0.001058275042):

- **1.4674% lower MSE**
- **40/59 patient wins**
- **5/5 favorable outer folds**
- **19/24 target-average wins**
- unchanged **64 treatment wells / 32 per source plate**

A post-hoc **100,000-resample whole-patient bootstrap** gives a descriptive 95% interval of **[-2.60e-5, -6.54e-6]** for current-minus-bandwidth-0.7 mean loss. It is deliberately labelled **selection-naive**, not confirmatory.

Versus the immediate 0.001043179589 predecessor, the mean gain is only **0.0416%**, with **32/59 patient wins and 3/5 favorable folds**; the same descriptive interval **[-1.13e-6, 2.58e-7] crosses zero**. We do not claim uniform superiority over nearby adaptive variants.

Versus original R13 (0.001144858681), the current candidate is **8.9193% lower**, with **49/59 patient wins, 5/5 folds, and 22/24 target-average wins**.

### 4. Reproducibility and implementation - 10%

The frozen verifier reconstructs **5,712 held-target predictions**. A fresh Windows replay differs by only **2.22e-16**, below the frozen **5e-16** tolerance, and uses no Protected22 response.

The public development source is the Kryeziu et al. colorectal-cancer organoid study. The exact Mendeley Data v3 `Data S4.xlsx` source is hash-pinned at SHA-256 `3847aa93b2a84c7d5d0b04c26494f39f35963fc41e96eae97d8a180fbc33d81c`, with the deposit listed under **CC BY 4.0**. DosePilot code/documentation/fictional fixtures are **MIT**.

The operating fictional lifecycle remains the bandwidth-0.7 operational baseline rather than silently pretending the newer calibration has already been productized.

### 5. Presentation - 10%

- public demo video: **75 seconds**, below the 5-minute rule;
- public repository and live fictional-data demo are anonymously reachable;
- current technical report is **9 pages** and visually checked for clipping/overlap;
- report and writeup expose adverse targets, failed families, validation boundaries, data rights, and AI assistance instead of hiding them.

## Evidence shortcuts

- [6 October Kaggle writeup](docs/KAGGLE_WRITEUP_20261006.md)
- [9-page technical report PDF](docs/DosePilot_Technical_Report_20261006.pdf)
- [Diffable report source](docs/DosePilot_Technical_Report_20261006.md)
- [Current model note](docs/CONTROL_QUALITY_SUCCESSOR_20261006.md)
- [Machine-readable current result](evidence/orientation_specific_control_quality_rank1_20261006.json)
- [Descriptive patient bootstrap](evidence/current_successor_descriptive_bootstrap_20261006.json)
- [Current successor visual](docs/figures/current_successor_summary_20261006.png)
- [Target-level aggregate diagnostic](evidence/current_successor_target_deltas_20261006.json)
- [Target-level CSV](evidence/current_successor_target_deltas_20261006.csv)
- [Implementation and frozen protocol](study/orientation_specific_control_quality_rank1/)

## Claim boundary

This remains **repeated adaptive development on the same 59-patient Lib1 population**, not independent confirmation, clinical performance, prospective organ-on-chip validation, or an official competition score. Protected22 remains exposed and its frozen full primary was not estimable.

ChatGPT assisted with research synthesis, implementation, numerical checking, adversarial review, and documentation. The DosePilot reconstruction runtime itself uses no language-model API or paid model service.

Historical 4 October writeup/report/evidence remain untouched so their recorded hashes continue to mean what they said at the time.

# Current scientific-successor finalist-rubric evidence

**Status:** PASS
**As of:** 6 October 2026
**Rubric weights last verified on Kaggle:** 1 October 2026

This immutable successor preserves the retrieval-bound r6 rubric map and adds
the centrally verified scientific-successor evidence map. It does not assign a
self-score or estimate finalist probability, and it does not claim that public
repository work changed the already accepted Kaggle entry.

## 30% — Problem importance and impact

The unchanged measurement contract predicts 24 treatment-response summaries
from exactly 64 treatment wells, 32 per source plate, across 119 samples and 59
whole patients. Prospective organ-on-chip performance, clinical utility, and
biological validation remain unverified.

## 30% — Technical approach and innovation

Orientation-specific control-quality rank-1 adds no treatment wells and does
not refit the base model. It uses standard control-quality summaries to calibrate
the two plate orientations under the frozen whole-patient evaluation protocol.
Protected22/Lib2 was not accessed.

## 20% — Results and validation

The strongest repeated-development point estimate has MSE
`0.001042745722096212`, p90 patient RMSE `0.037419695944064885`, 40/59 patient
wins and 5/5 favorable folds versus bandwidth-0.7, and 19/24 target-average
wins. It retains the R13 and R18 gates. Against the immediate predecessor the
gain is only 0.0416%, with 32/59 patients and 3/5 folds.

The whole-patient bootstrap is post-hoc and selection-naive. Its interval versus
bandwidth-0.7 lies below zero, but its interval versus the immediate predecessor
crosses zero. Because patient-level loss rows and frozen bootstrap inputs are not
public, the bootstrap is not independently recomputed or confirmatory.

## 10% — Reproducibility and implementation

The exact public candidate receipt, descriptive bootstrap, 24-target JSON/CSV,
and central successor verifier are hash-bound. The candidate receipt records its
original replay at `0.0` under a `5e-16` tolerance. Documents separately report a
fresh Windows replay at `2.22e-16`; no separate immutable machine-readable
Windows receipt binds that environment, so independent reproduction is not
claimed.

## 10% — Presentation

The successor binds the complete 24-target visual, nine-page 6 October report,
AI4S write-up, and 90-second reviewer path by exact hash. All five regressing
targets remain visible. No favorable-target filtering or target splicing is used.

This is repeated adaptive-development evidence, not independent validation,
finalist confirmation, an official competition score, or a clinical claim.

# Nested bandwidth-selection evaluation

**4 October 2026 | retrospective repeated-development evidence**

## Result

The already-opened bandwidth menu was replayed as a fully nested procedure:
inside each of the five outer training sets, the three inner patient folds
selected one joint pair from bandwidth `{0.7, 1.0, 1.4}` and the existing ten
residual-spectral options. No held-out outer-fold outcome entered that fold's
selection.

All **5/5 outer training sets selected bandwidth 0.7**. The resulting held-
patient predictions are exactly the fixed bandwidth-0.7 incumbent:

| Procedure | Full-24 MSE | p90 patient RMSE |
|---|---:|---:|
| Nested bandwidth-selection procedure | **0.001058275042** | **0.0378942853** |
| Fixed bandwidth 0.7 | **0.001058275042** | **0.0378942853** |
| Fixed bandwidth 1.0 | 0.001060552730 | 0.0380731116 |
| Fixed bandwidth 1.4 | 0.001063709359 | 0.0383041430 |

The nested and fixed-0.7 predictions are identical, so all 59 patient losses,
all five fold means, both orientation errors and all 24 target means tie. This
is useful evidence that the selected 0.7 setting was not created by mixing
bandwidths across favorable outer folds or targets.

The foldwise joint selections were:

| Outer fold | Bandwidth | Residual fraction | Ridge |
|---:|---:|---:|---:|
| 0 | 0.7 | 0.3 | 1.0 |
| 1 | 0.7 | 0.1 | 1.0 |
| 2 | 0.7 | 0.1 | 1.0 |
| 3 | 0.7 | 0.1 | 1.0 |
| 4 | 0.7 | 0.1 | 1.0 |

Every alternative retained the same fitting-slice acquisition plan and exactly
64 distinct physical treatment wells, split 32/32 across the two plates. A/B
predictions stayed separate; only their losses were averaged.

## What this resolves—and what it does not

The original bandwidth result remains a post-selection development point
estimate because the three fixed-bandwidth outer results were inspected during
the broader campaign. This new replay addresses a narrower question: if the
predeclared three-bandwidth choice were made strictly inside each outer training
set, would a different bandwidth have been used? On these five folds, the
answer is no.

The replay is not independent validation or a correction for every earlier
model-family decision. The same 59 development patients and already exposed
folds were reused. It creates no prospective organ-on-chip evidence, clinical
claim, official competition score or rank. Protected22/Lib2 was not accessed,
and the accepted Kaggle entry was not edited.

## Reproducibility boundary

The prefrozen protocol and runner are in
`study/nested_bandwidth_selection/`. The public aggregate receipt is
`evidence/nested_bandwidth_selection_20261004.json`. Private held-patient and
inner-fold prediction arrays are deliberately not published. The independent
no-refit audit recomputed the 30 inner scores per outer fold, all selections,
all aggregate metrics, comparisons and the descriptive bootstrap from the
preserved private arrays and passed.


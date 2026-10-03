# Additive bandwidth-0.7 successor

**Joseph Ayanda | 3 October 2026 | Research software**

## Decision

The fixed global bandwidth-0.7 additive kernel is the strongest verified
development result currently available for DosePilot.

| Procedure | Patient-balanced MSE | p90 patient RMSE |
|---|---:|---:|
| Original R13 | 0.001144858681 | 0.041107825 |
| S2 spectral correction | 0.001070143945 | 0.038733242 |
| Additive factor 1.0 | 0.001060552730 | 0.038073112 |
| Previous RMS-half + half-alignment combo | 0.001060411034 | 0.038050495 |
| **Additive bandwidth factor 0.7** | **0.001058275042** | **0.037894285** |

The new procedure improves 38/59 patient means and all five outer-fold means
versus the published additive incumbent. It also improves 34/59 patient means
and all five folds versus the previous private combo. Its paired whole-patient
descriptive interval versus additive is
`[-4.1626e-6, -4.3656e-7]`; versus the previous combo it is
`[-4.1264e-6, -2.0083e-7]`.

Against R13 it is 7.56% lower in mean MSE, with 49/59 patient wins and 5/5
favorable folds. Against R18 it is 7.28% lower, with 47/59 wins and 5/5 folds.
The unchanged historical screens pass in both comparisons.

These are repeatedly reused adaptive Lib1 development results. They are not
untouched confirmation, a clinical claim or an official competition score.

## What changed

The existing additive correction is a linear kernel plus 24 Gaussian
drug-group components. For drug group (j), the incumbent similarity is:

[
exp{-\|z_j-z'_j\|^2/(2d_j)}.
]

The successor changes only the global group length scale. With factor (b):

[
exp{-\|z_j-z'_j\|^2/(2d_j b^2)}.
]

Exactly three factors were fixed before scoring: 1.0, 0.7 and 1.4. Factor 1.0
is the existing additive model. Factor 0.7 passed the complete screen; factor
1.4 was rejected. No extra bandwidth was introduced after seeing outcomes.

Everything else is unchanged: the R13 64-well acquisition, 32/32 plate balance,
own-drug ridge baseline, five outer and three inner whole-patient folds, equal
patient weighting, and ten residual spectral options.

No extra measurement, target-specific bandwidth, target splicing, clipping,
missing-value imputation, Lib2 response or A/B prediction averaging was used.

## Verification

Three source-only tests passed before fitting. A separate no-refit verifier then
recomputed patient/fold/tail metrics from saved predictions using explicit
patient arithmetic, rechecked the historical R13/R18 screens, and compared the
new model against the previous private combo.

Exact private execution hashes are published in
`evidence/additive_bandwidth_20261003.json`. Patient arrays, fitted biological
weights and the source workbook remain private.

A full-TRAIN research artifact was also constructed using a training-only
three-fold selection. It selected residual fraction 0.1 and ridge penalty 1.0.
That construction is not another validation result.

## Deployment boundary

The existing public additive runtime was built for bandwidth factor 1.0.
**Do not silently load the bandwidth-0.7 research weights into that runtime.**
A bandwidth-aware, identity-bound runtime must be implemented and regression
tested separately before this successor becomes the recommended operating
artifact.

Until then:

- bandwidth 0.7 is the current **research benchmark**;
- the published factor-1 additive runtime remains the **operating benchmark**;
- the accepted Kaggle entry and submitted video remain unchanged.

## Negative follow-up retained

A single fixed follow-up combined bandwidth 0.7 with the earlier RMS-half
target geometry and half residual-alignment mechanisms. It slightly improved
p90 to 0.037856394 but worsened mean MSE to 0.001058323066 and improved only
2/5 folds. It was rejected. The simpler bandwidth-only model remains retained.

Protected22 remains exposed and its full primary remains not estimable. Nothing
in this experiment repairs or reopens that study.

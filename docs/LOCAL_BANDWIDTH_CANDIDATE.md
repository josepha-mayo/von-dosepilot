# Response-free local-bandwidth candidate

**Status: verified development candidate, not the public incumbent.**

This branch evaluates one prefrozen response-free extension of the current bandwidth-0.7 additive kernel. It does not change a physical well, the own-drug base model, the residual spectral grid, or the evaluation folds.

## Result

| Procedure | Patient-balanced MSE | p90 patient RMSE |
|---|---:|---:|
| Current bandwidth-0.7 release | 0.001058275042 | 0.037894285309 |
| **Response-free local bandwidth** | **0.001058149699** | **0.037893995609** |

The local candidate is **0.01184% lower** in mean MSE, wins **32/59** patient means, improves **4/5** outer-fold means, and has nonworse p90. It also passes the historical R13/R18 screens. The paired descriptive interval for candidate-minus-bandwidth-0.7 patient loss is `[-5.57e-7, +3.26e-7]`, so it crosses zero and is not selection-corrected.

Twelve of 24 target-average errors regress versus bandwidth-0.7. This is why the candidate is not being promoted in the judge-facing package solely because its point estimate is lower.

## Response-free geometry

For each drug group j, using only standardized purchased-input values and the existing whole-patient fitting weights:

1. compute the weighted median q_j of pairwise squared Euclidean distances;
2. set r_j = sqrt(q_j / (2 d_j)), with a unit fallback for degenerate geometry;
3. compute the geometric mean g of all 24 r_j;
4. use ell_j = 0.7 * sqrt(r_j / g).

The 24 local multipliers therefore have geometric mean exactly **0.7**. Target responses do not enter this rule. Only the existing common residual spectral option is selected by the original inner patient folds.

Across the five outer fitting populations, each 24-dimensional multiplier vector correlates **0.949–0.983** with the final all-training multiplier vector. Median per-target coefficient of variation is **1.05%** and the maximum is **2.27%**. The final multiplier range is **0.5283–0.7346**.

## Reproduction

After reconstructing the public Lib1 TRAIN CSV:

    python study/hybrid_residual/reproduce_local_bandwidth.py \
      --curves reconstructed_train/train_curves.csv \
      --output local_bandwidth_replay \
      --fit-final

A fresh clone reproduced:

- local MSE `0.0010581496990391417`;
- bandwidth-0.7 MSE `0.0010582750420801538`;
- R13 MSE `0.0011448586813828537`;
- 32/59 patient wins and 4/5 favorable folds versus bandwidth-0.7;
- exactly the five frozen outer-fold spectral selections.

No historical prediction array or old private metadata kit is an input.

## Runtime check

The constructed final artifact was evaluated on 238 existing sample/orientation requests. Identity-checked inference matched direct matrix evaluation within `2.22e-16`. Every one of 64 single-missing-position cases withheld the primary prediction. This is implementation verification on existing training records, not new biological validation.

## Release decision

The method passes the prefrozen internal promotion rules, but its incremental gain is small relative to the project's extensive adaptive development history, its descriptive paired interval crosses zero, and half of target means regress.

Therefore this branch is retained as a technically verified candidate while the public submission continues to present bandwidth-0.7 as the stable estimator. Promoting it later would require updating reproduction, lifecycle, finalist audit, technical report and live demo together rather than silently changing the headline number.

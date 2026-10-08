# Current verified research state — 8 October 2026

## Purpose

This page is the single current-state map for reviewers. It reconciles the operating 64-well demo, the retained 64-well research candidate, the separately rejected 72-well trade-off and the latest closed research families. It does not change any estimator, create a new accuracy claim or prove that the accepted Kaggle entry was updated.

## Current decision table

| Role | Physical treatment wells | Patient-balanced MSE | p90 patient RMSE | Decision |
|---|---:|---:|---:|---|
| Operating/demo baseline: bandwidth-0.7 additive | 64 (32 + 32) | `0.0010582750420801538` | `0.037894285308720174` | Remains the deployed demonstration baseline |
| Retained research candidate: orientation-specific control-quality rank-1 | 64 (32 + 32) | `0.001042745722096212` | `0.037419695944064885` | Retained scientific successor; not silently substituted into the demo |
| Exploratory bandwidth-0.7 residual frontier | 72 (36 + 36) | `0.0009326007417880046` | `0.03770730634910972` | Rejected for promotion: eight extra wells and worse p90 than the retained 64-well candidate |
| Explicit half-error research target | 64 (32 + 32) | `<=0.000521372861048106` | `<=0.037419695944064885` | **Not achieved** |

The retained research candidate improves 40/59 patient means, all 5/5 outer-fold means and 19/24 target-average errors versus the operating baseline while retaining the R13/R18 gates. These are repeated adaptive-development results on Lib1, not an official score, independent validation or evidence that the research candidate is deployed.

The 72-well result is a separate measurement/error trade-off. It is not a 64-well improvement, and the retrospective 48-to-72 curve is not proof of global optimality or realized laboratory-cost savings.

## Closed recent research lanes

All rows below preserve negative evidence. None replaces the retained candidate.

| Study or fixed arm | MSE | Outcome |
|---|---:|---|
| Global conditional full-curve model | `0.0010582750420801534` | Inner selection retained the operating family; exact tie; rejected |
| Pooled cross-drug ridge | `0.0010582750420801534` | All five inner selections retained the incumbent; rejected |
| Output contrast whitening | `0.0010576854058442203` | Small mean change but insufficient patient/fold breadth and worse than retained research; rejected |
| Chemical partial external prior | `0.0010612090565783913` | 20/59 patient wins and 0/5 favorable folds versus retained research; rejected |
| Patient-deleted acquisition risk | `0.0010670699038616163` | 1/5 favorable folds versus operating baseline; rejected |
| External generic-shape transfer | `0.001068618046193161` | 18/59 patient wins and 0/5 favorable folds versus retained research; rejected |
| External source-prototype mixture | `0.0010729912368558343` | 19/59 patient wins and 0/5 favorable folds versus retained research; rejected |
| Flexible-cardinality 64-well allocation | `0.001074500244708035` | 1..6/2..6-dose dynamic-programming acquisition worsened; rejected |
| Mixed physical replication | `0.0010957924` | Same-budget replicate allocation failed promotion gates; rejected |
| Fixed equal three-channel estimator | `0.0011032463102158827` | 17/59 patient wins and 0/5 favorable folds versus retained research; rejected |
| Spatial control transport | `0.0011114867137742334` | 17/59 patient wins and 0/5 favorable folds versus retained research; rejected |
| Direct TabPFN-v2 regression | `0.00118679846` | Same 64-well contract; rejected |
| Mask-augmented nonlinear curve learner | `0.0011989960402994302` | 0/5 favorable folds versus retained research; rejected |
| Exact-contribution TabPFN-v2 regression | `0.00121042081` | Same 64-well contract; rejected |
| Dose-shape mixture | `0.0012866979` | Rejected |

The recovered-trial registry also preserves the alternative TabPFN context arm, original-mask control and earlier negative families. Values above are compact navigation, not a substitute for their machine-readable receipts.

## Current open ownership boundary

The public branch [dosepilot-external-output64-20261008](https://github.com/josepha-mayo/von-dosepilot/tree/dosepilot-external-output64-20261008) remains freeze-only at the time of this snapshot. Its fixed proposal uses source-derived output covariance under the original 64-well input plan. No completed result or promotion claim is recorded here. Do not merge, rerun or extrapolate from that frozen protocol unless its owner releases a completed result and immutable audit.

## Fast verification path

Run the response-free scientific-reliability package:

    python3 study/audits/finalist_package_preflight_scientific_reliability.py --output finalist_package_preflight.json

Primary public anchors:

- [scientific-reliability criterion evidence](FINALIST_RUBRIC_EVIDENCE_CURRENT_SCIENTIFIC_RELIABILITY.md)
- [late-session research checkpoint](LATE_RESEARCH_CHECKPOINT_20261007.md)
- [recovered completed-trial registry](../evidence/recovered_completed_trials_20261007.json)
- [spatial control and transport receipt](../evidence/control_transport64_20261007.json)
- [fixed three-channel receipt](../evidence/fixed_three_channel64_completed_20261007.json)
- [mixed-replication receipt](../evidence/mixed_physical_replication64_20261007.json)
- [external generic-shape receipt](../evidence/external_shape_shrink64_20261008.json)
- [external prototype receipt](../evidence/external_prototype_mixture64_20261008.json)
- [chemical partial-prior receipt](../evidence/chemical_partial_prior64_20261008.json)
- [72-well public audit](../evidence/budget72_bandwidth07_public_audit_20261006.json)

## Interpretation boundaries

- Every accuracy result here is repeated adaptive Lib1 development over 119 samples grouped into 59 patients.
- Whole-patient folds prevent within-run patient leakage, but repeated inspection of the same development folds is selection-unadjusted.
- Grouped bootstrap and reliability diagnostics are post-hoc and selection-naive.
- Public receipts preserve metrics, hashes and software-integrity checks; private response arrays and source inputs required for full numerical replay are not public.
- Saved-model replay and mutation/poisoning tests are software and numerical integrity checks, not independent biological reproduction.
- Protected22/Lib2 is exposed and permanently forbidden for tuning, rescue or subgroup search.
- No result here establishes clinical suitability, independent validation, finalist status, an official competition score, guaranteed selection or global optimality.
- Repository commits, reports and prepared archives are not proof that the accepted Kaggle writeup was changed.

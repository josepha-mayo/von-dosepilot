# von DosePilot | 2x MSE campaign: 8 October 2026

**Status:** numeric 2x improvement NOT achieved. Original submission and shared research worktree were not changed. The three new candidate families were implemented, frozen in isolated Git worktrees before results, fully evaluated, independently replayed and rejected.

## Objective and reference
- Best retained scientific 64-well MSE: **0.001042745722096212**.
- Required absolute half-error threshold: **0.000521372861048106**.
- Best retained scientific 64-well p90 whole-patient RMSE: **0.037419695944064885**.
- Operating 64-well spectral bandwidth0.7 MSE: **0.0010582750420801538**.
- Authenticated reconstructed Lib1 TRAIN only: 119 samples / 59 whole patients / 24 unchanged normalized log-dose AUC targets. Five whole-patient outer folds, three whole-patient inner folds for global spectral option selection; equal-patient, equal-target, two ALTERNATIVE A/B orientation losses.
- This data has been used repeatedly for method development. Results are not independent biological validation, official rankings or new Kaggle submission scores.

## New hypothesis 1: deliberate cross-plate matched-dose replication
**Branch:** research-crossplate64-20261008; prefit commits 74ac634, 92993f6 (weight normalization fixed before candidate results).
**Source:** D:/von-dosepilot-crossplate64-20261008/study/run_crossplate64_20261008.py
**Result:** D:/von-dosepilot-data/crossplate64_20261008_run1/RESULT.json

| Physical wells | Distinct doses | MSE | p90 | Change vs best scientific 64 |
|---|---:|---:|---:|---:|
| 64 | 64 | 0.0010582750420801536 | 0.037894285309 | -1.49% |
| 64 | 60 (4 paired) | 0.0010699938231502094 | 0.038426805950 | -2.61% |
| 64 | 56 (8 paired) | 0.0011235782120460934 | 0.038649674641 | -7.75% |

Conclusion: exchanging unique dose coverage for matched repeat plate measurements regresses accuracy. This family intentionally changes the *distinct-dose* contract even though physical well count remains 64. No promotion.

Audit: synthetic physical budget tests pass (64/60/56 distinct dose counts, 32/32 plates), 5-fold patient evaluation complete, original baseline reproduced to max absolute difference 6.661338147750939e-16. Independent no-refit scorer passed with code study/verify_crossplate64_20261008.py. No Protected22 or Lib2.

## New hypothesis 2: learn minority-plate concentration placement
**Branch:** research-plateperm64-20261008; frozen source commit 3eef9f0.
**Source:** D:/von-dosepilot-plateperm64-20261008/study/run_plateperm64_20261008.py
**Result:** D:/von-dosepilot-data/plateperm64_20261008_run1/RESULT.json

All policies preserve 64 distinct native doses, 64 physical wells and a 32/32 plate split. Leave two-dose target assignments alone, alter only which of the three native drug doses receives the minority-plate measurement.

| Strategy | MSE | p90 |
|---|---:|---:|
| Original fixed alternating | 0.0010582750420801536 | 0.037894285309 |
| Place lowest on minority plate | 0.0010709048481089313 | 0.038889096553 |
| Place highest on minority plate | 0.0010793006992359487 | 0.040700272651 |
| Fit-only target risk selection | 0.0010675450188854787 | 0.038240017115 |

All three variants regress against current retained scientific 64; 0/5 favorable outer folds versus it. Original baseline reproduced and independent replay checked in study/verify_plateperm64_20261008.py. No promotion.

## New hypothesis 3: plate-separated AUC auxiliary supervision
**Branch:** research-platesup64-20261008; frozen source commit d3736e6.
**Source:** D:/von-dosepilot-platesup64-20261008/study/run_platesup64_20261008.py
**Result:** D:/von-dosepilot-data/platesup64_20261008_run1/RESULT.json

All four variants keep the original 64-distinct native dose plan, target 24 original averaged AUCs, and same 32/32 p1/p2 well budget. Aux channels use separately reconstructed p1/p2 **fitting labels only**, not extra held-out/test measurements.

| Residual spectral label channels | MSE | p90 |
|---|---:|---:|
| Original averaged 24-target | 0.0010582750420801536 | 0.037894285309 |
| Dual full-plate AUC 48-target | 0.0010596812658317718 | 0.037993787502 |
| Average plus 0.5 contrast 48-target | 0.0010596812658317718 | 0.037993787502 |
| Average plus 0.125 contrast 48-target | 0.001058230621675709 | 0.037888827871 |

The last variant yields only approximately 0.0042% relative improvement against the operating reference, not against the stronger scientific 64 successor. All 3 candidate auxiliary variants regress relative to retained best scientific 64. Independent scorer study/verify_platesup64_20261008.py passed all four outputs and the old baseline identity. The synthetic multioutput spectral check passes. No promotion.

## New diagnostic: why 2x is materially harder than calibration
- Full-curve-from-*one*-plate diagnostic, predicting averaged full two-plate AUC: per-patient MSE **0.0007521757809186084**. This is a useful measurement-variability indicator, NOT a universal lower bound on attainable accuracy.
- Original retained 64-well errors decompose exactly as:
  - Shared error of the hypothetical mean of complementary-layout predictions: **0.0006985774467545808** (67.0%).
  - Layout-specific difference term: **0.00034416827534163117** (33.0%).
  - Sum **0.001042745722096212**.
- Averaging A/B predictions at inference is disallowed as it would require purchasing both complementary panels; this decomposition is only retrospective diagnosis.
- Even an imagined zero layout-specific term leaves 0.00069858, above the required 0.00052137. Meaningful progress demands both a structural predictor improvement and a way to handle plate-specific uncertainty.

## Next research frontier, not implemented or claimed validated
A hierarchical model that jointly estimates latent **drug dose-response shape** and explicit plate-specific **measurement effects** from each single purchased 64-well layout, using train-only full-curve measurements for learning the structured prior. Unlike the earlier global covariance, this would explicitly separate shared biology from plate measurement nuisance and propagate uncertainty into each original averaged AUC. It must be benchmarked against the untouched 64-well scientific reference, with all inner policy/model selection within outer patient folds. Additional data or new independent patient cohorts likely matter more than another marginal residual-calibration sweep. A change to 72/96+ physical wells is a separate cost tier and cannot be presented as a same-budget 2x gain.

## Research integrity
- No Kaggle score, official rank or submission changed.
- D:/von-dosepilot-work shared master untouched.
- Frozen source and protocol hashes are in each RESULT.json; complete prediction arrays remain private on D:, never public.
- Original 64-well spectral pipeline reproduced exactly in every new family.
- Preserved all negative candidates and the original strongest 64/72 scientific references.

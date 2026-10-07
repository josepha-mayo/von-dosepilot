# DosePilot late-session research checkpoint

## Outcome
The requested 2x accuracy gain is NOT achieved. The retained 64-well research value is still **MSE 0.001042745722096212**, p90 patient RMSE **0.037419695944064885**. The target remains **MSE <=0.000521372861048106**, on all 24 original outputs without worse tail error. These are repeated-development values, not an official score or independently validated clinical performance.

Two new structural studies were implemented, frozen, executed across all five patient-held-out folds and independently replayed during the continuation begun 7 October 2026 at 22:27 UTC. A previously frozen three-channel ensemble was also completed. None qualifies for promotion.

| Tested procedure | Development MSE | p90 patient RMSE | Status |
|---|---:|---:|---|
| Retained research64 comparator | 0.001042745722 | 0.037419695944 | Retain |
| Flat standard-control transport | 0.001089881185 | 0.037931450540 | Reject |
| Spatial standard-control transport | 0.001111486714 | 0.039587498197 | Reject |
| Distinct-dose physical pattern optimization | 0.001081751550 | 0.040059051776 | Reject |
| Mixed physical replication | 0.001095792404 | 0.040038006924 | Reject |
| Prefrozen fixed three-channel ensemble | 0.001103246310 | 0.039366448469 | Reject |

Each listed replacement had **0/5 favorable outer folds versus retained64**. The identity/original controls separately regenerated the operating bandwidth-0.7 MSE **0.0010582750420801538** within numerical tolerance. No poor arm replaced the operating or retained research model. This work made no Kaggle submission edit.

## Spatial controls: tested new information, not a kernel sweep
The routine assay inventory contains 13 negative and 9 positive controls on each of 238 authorized Lib1 TRAIN plates. A guarded extraction converted 5,236 standard-control signals while performing zero semantic numerical conversions of treatment signals, viability cells or Lib2 responses. It reproduced the existing control summaries exactly. This is the same required control resource as the retained control-aware model, not additional free treatment measurements. XML byte traversal is not falsely represented as zero byte access.

The new trial estimated additive/multiplicative fields from known control positions, transformed fitting responses to a common coordinate system, predicted full curves from the 64 purchased values, then mapped predictions back into the ORIGINAL raw AUC endpoint. It did not relabel a cleaner target. Spatial transport was **6.5923% worse** than retained64; the flat control was **4.5203% worse**. Both failed, so this particular field model is closed rather than retuned from the outer outcomes.

The spatial source was prefrozen at **86bdc2c**, completed evidence published at **d48ccd75c46efa2422bd31b964ed753d51d73eb2**, on branch **dosepilot-spatial-controls64-20261007**. Aggregate receipt: https://github.com/josepha-mayo/von-dosepilot/blob/d48ccd75c46efa2422bd31b964ed753d51d73eb2/evidence/control_transport64_20261007.json .

## Replication: explicit physical-cost test
The second study asked whether selected doses should be measured on BOTH plates instead of using every well for a different native concentration. It kept **64 distinct physical cells, 32 per plate**, and all 24 endpoints, but explicitly relaxed the previous **64 distinct native concentrations** condition. The original validator was left unchanged; a synthetic test confirms it rejects a repeated-native design. No result is silently treated as a pass under that old design contract.

The primary mixed planner used **56, 60, 61, 60 and 59 distinct native doses** in the five outer plans, respectively. The missing native slots were paid cross-plate replicates, not extra observations. This mixed design was **5.0872% worse** than retained64. A separate control allowing new plate patterns but preserving 64 distinct doses was **3.7407% worse**. Both are rejected. The earlier all-paired R9/matched paired baselines were inspected and are not presented as new experiments.

The mixed study was prefrozen at **a1a6c0dccaace4cb164de57a301e9c1508de8b1d**. Protocol and replay code are in `study/mixed_physical_replication64/`; aggregate result is `evidence/mixed_physical_replication64_20261007.json`.

## Verification scope
Across the two new studies, **28 unique synthetic tests** passed: 19 control-extraction/transport tests and 9 mixed-design tests. Separately written replay code reconstructed **30 saved outer models**. Control-field reconstruction differed by at most 4.44e-16; prediction replay differed by at most 4.44e-16; metric differences were at most 1.39e-17. The two audit passes checked 22 and 19 source hashes respectively, including shared dependencies; these are not claimed as 41 unique source files. Held-out-label/curve mutation and unpurchased-input poisoning checks passed.

The completed fixed ensemble uses the already frozen one-third weights for operating kernel, direct TabPFN and exact-contribution TabPFN, with verified identical paid layouts. It has no outcome-fitted stacking weights and no indirect OOF meta-training. Independent arithmetic and metric recomputation passed, but its MSE is **5.8020% worse** than retained64. Aggregate receipt: https://github.com/josepha-mayo/von-dosepilot/blob/d48ccd75c46efa2422bd31b964ed753d51d73eb2/evidence/fixed_three_channel64_completed_20261007.json .

Replayed numerical states and software-isolation checks are NOT fresh biological validation. All original Lib1 patients have been repeatedly inspected during development. The bootstrap intervals are post-hoc and selection-unadjusted. Private patient predictions, fitted numeric states and raw control values remain local, not published.

## Closed recovered work
Direct/full-context TabPFN, balanced-context TabPFN, exact-contribution TabPFN, empirical sigmoid-mixture and its Gaussian control, and both nonlinear mask-augmentation arms had already completed and lost to retained64. They were not rerun. Their recovered status/hashes are preserved at: https://github.com/josepha-mayo/von-dosepilot/blob/d48ccd75c46efa2422bd31b964ed753d51d73eb2/evidence/recovered_completed_trials_20261007.json . This registry distinguishes available independent audits from merely recorded run results.

## Next direction and schedule
Do not recycle these model menus. The next research lead is an independently sourced dose-response prior, subject to source/rights, assay-scale and overlap checks; see `EXTERNAL_CURVE_PRIOR_LEAD_20261008.md`. This lead is not a trained model and is not an achieved improvement. Generic TabPFN priors have already failed here; an external curve-specific prior needs a genuinely different biological evidence source and an honest transfer design, not a rebrand.

Research remains authorized through 8 October, Africa/Lagos. Reserve 9 October for final regression, provenance checks, updating the EXISTING accepted Kaggle writeup and verifying the saved entry. Do not rely on repository commits or ZIP generation as evidence of submission. No duplicate reminder is needed: the Calendar reminder already exists.

This checkpoint is not a statement that the half-error objective is impossible. It records which concrete hypotheses failed so subsequent work does not repeat them or hide their outcomes.

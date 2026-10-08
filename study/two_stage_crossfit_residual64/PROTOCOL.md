# Cross-fitted cross-drug correction for the frozen two-stage acquisition policy

## Why this follow-up exists
The completed two-stage trial's primary adaptive ridge MSE was 0.0011468052747423553, versus 0.001174394681333341 for its matched static control. That is a small within-family change, not a win over retained64; tail error worsened and both failed promotion. This follow-up is explicitly proposed AFTER seeing those outcomes. The acquisition policy and its risk model are not retuned.

This experiment asks whether an output model using the OTHER already purchased drugs can recover useful information omitted by the prior trial's own-drug-only heads. A fixed paid-column kernel cannot directly handle patient-specific dose choices. The new representation explicitly records measured values, their dose/plate metadata and the missing-third indicator, rather than pretending variable columns have fixed meanings or obtaining unpurchased measurements.

The half-error target remains MSE <=0.000521372861048106 with retained p90 <=0.037419695944064885, all 24 original outputs and 64 physical treatment measurements. A small mean gain, a good control result, synthetic tests or algorithmic novelty does not meet that target.

## Unchanged acquisition and explicit operational difference
Reuse study/two_stage_risk64 exactly: first 48 R13 best-two observations, then sixteen third-dose requests committed using only those initial values, eight on each plate. The primary is the frozen adaptive policy; a fixed-plan policy is a matched control. Both preserve 64 distinct eligible doses, 32 physical cells per plate, and the 24-target denominator. Full historical curves are fitting-only except for deterministic endpoint verification. The policy's final layouts need not be complements; they are alternative deployments and their predictions are never averaged.

This remains a two-round laboratory proposal, not the existing single-round product. Extra decision/measurement latency and prospective assay comparability remain unvalidated. No claims of identical laboratory time or immediate deployment, no changes to the original validator, and no automatic promotion or Kaggle edit.

## Cross-fitted residual training
Inside EACH fitting partition, create three whole-patient calibration folds. For each calibration fold rebuild the entire original best-two planner, population mixture, all ridge heads and policy on the other two folds, then generate its held-patient staged readings, raw predictions and metadata features. Thus no patient's curve or label fits the acquisition/reconstruction model generating that patient's residual-training row. Do not recycle the globally available outer-OOF arrays. After assembling these internally held-out rows, fit the correction on y minus the raw prediction. Finally refit the acquisition/raw-prediction bank on the whole fitting partition for future queries.

For every target, the feature block contains eleven values: first reading, first normalized log-dose coordinate, first plate index; second reading, second dose coordinate, second plate index; third reading, third dose coordinate, third plate index; third-present indicator; raw predicted AUC. When no third dose is purchased, its value and metadata slots are zero and the indicator is zero. Zero is a masked placeholder, not a measured zero. Normalized dose coordinates use the fixed source-grid metadata, never response values or a held-out outcome. The 264 derived features do NOT imply 264 purchased measurements.

A fitting-patient-weighted mean/scale (floor0.05) standardizes these blocks. Use one additive input kernel: global linear term plus 24 eleven-coordinate Gaussian blocks with multiplier0.7, each weighted by block size11. This is the existing kernel construction extended to a different explicitly typed observation representation, not a newly invented kernel. Center residual targets by their fitting weighted mean and add that mean back for nonidentity correction options, since cross-fitted residuals need not have zero mean.

The unchanged ten residual options are identity/no correction, or spectral fraction{0.1,0.3,0.6} crossed with ridge{0.1,1,10}. Identity returns the raw full-fitting-bank predictor exactly without adding a calibration mean. One global option per policy is selected using THREE further whole-patient inner folds. Each inner model rebuilds its own three-fold residual-training procedure strictly inside its inner-training set. Therefore the outer test patient cannot reach either the base model or the meta-training rows indirectly. No target/plate-specific option selection or post-outcome mixture.

Report adaptive+residual PRIMARY and static+residual CONTROL separately, along with their raw two-stage references and original retained/operating comparators. Calibration models are trained on fewer patients than the final bank; that potential train-size/domain shift is acknowledged, not corrected after observing outcomes.

## Evaluation and invariants
Original five outer patient folds, authenticated Lib1 TRAIN: 119 organoids, 59 patients, 24 raw AUCs. Raw prediction outputs from the refitted full outer banks must reproduce the preceding frozen two-stage trial within1e-12. The old trial's predictions are only comparators, not residual-training data. Every fitting bank, calibration partition, scaling, kernel and option choice excludes all organoids of outer test patients.

An arm needs lower MSE, >=30 patient wins, all five favorable folds and nonworse p90 against BOTH retained64 and operating64 for numerical eligibility. Half-error uses the separate absolute threshold. Any numerical success still requires independent fresh full replay, R13/R18 checks and review of the changed two-round workflow before promotion. No automatic change of model/demo/submission. All five folds and both policies finish before aggregate errors are inspected. Bootstrap100000 patient draws, seed202610080940, descriptive and selection-unadjusted.

Synthetic tests cover feature semantics/masks, derived-only inputs, kernel PSD, saved-model equivalence, zero residuals, and patient-isolation wiring. Record meta-training index partitions privately. Poison unpurchased values and verify prediction/request invariance. Rebuild outerfold0 after perturbing its training-ineligible labels and full curves with original paid queries retained; predictions, chosen options and fitted numeric states must be invariant. Save outer banks, kernel numeric states, staged query traces and calibration arrays for independent feature/kernel/metric recomputation. No Protected22/Lib2, external biological dataset, additional controls, network request or patient-array publication.

This is repeated adaptive development, not independent biological validation. Existing failures remain preserved. This new residual-training and observation-representation construction must not be described as retuning the first policy or retroactively improving its recorded score.

## Established references
Cohn et al., Active Learning with Statistical Models (1996), https://arxiv.org/abs/cs/9603104 .
Cawley and Talbot, On Over-fitting in Model Selection and Subsequent Selection Bias in Performance Evaluation (2010), https://www.jmlr.org/beta/papers/v11/cawley10a.html .
The additive/spectral kernel implementation is explicitly derived from this repository's frozen operating model. These sources support method context, not a DosePilot performance claim.

# Patient-deleted acquisition risk, original 64-well task

## Hypothesis
Replace the existing in-sample covariance surrogate for choosing doses with exact internally leave-one-patient-out prediction error. This is a new risk estimator, not a rerun of the rejected flexible-cardinality menu. The allowed plan is unchanged: two or three native doses per target, exactly sixteen third-dose upgrades, 64 treatment wells, 32 per source plate, all 24 targets. No target-specific manual rescue or extra measurements.

The current concrete research goal remains MSE <=0.000521372861048106, half the retained research candidate's 0.001042745722096212, with nonworse p90. It is an aspiration, not an achieved score.

## Frozen planner
For each fitting partition and each target, enumerate the same native two-dose and three-dose subsets. For each subset, hold out each fitting patient in turn, together with ALL organoids and both alternative layouts from that patient. Fit the same own-drug ridge at lambda 0.01 on the remaining patients, recomputing patient-weighted means and standard deviations (scale floor 0.05). Average squared prediction error over the held patient's organoids and the two alternative layout LOSSES; then average equally across fitting patients. This is the subset's predictive risk.

Implement the exact deletion using per-patient sufficient statistics, small batched covariance solves and held-patient second moments. It must match explicit brute-force grouped refitting on synthetic data. No approximation to deletion, reuse of removed-patient normalization, or ordinary sample-wise LOO is allowed.

For each target choose the minimum-risk size-2 and size-3 subsets, tie-break by existing native identity order. Upgrade exactly sixteen targets by the largest risk reduction, even if some reductions are negative; no output is dropped. Use the original complementary plate-start rule and validate 32/32 physical balance.

## Model and selection
Two acquisition policies in fixed order: original R13 planner and patient-deleted planner. For each fit the unchanged own-drug ridge 0.01 and bandwidth-0.7 additive residual kernel. Offer the exact ten existing residual options: identity; then spectral fraction {0.1,0.3,0.6} crossed with ridge {0.1,1,10}. Thus 20 total options. Select one global policy/residual option by three regenerated whole-patient inner folds, shared across every target and both orientations; ties pick the earliest menu index.

Evaluation uses the original five whole-patient outer folds. Every acquisition policy, its internal patient deletions, scaling, kernel and residual option fitting is rebuilt entirely within each fitting split. Outer test labels cannot enter any level of the planner. Existing global OOF arrays are used ONLY for the retained comparison, not for training.

The first ten options must regenerate the operating baseline MSE 0.0010582750420801538 within 1e-12. Eligibility for a separate full numerical replay requires lower MSE, >=30 patient wins, 5/5 favorable folds and nonworse p90 against both operational and retained research comparators. Same 64-well cost required. No automatic promotion. Prespecified descriptive bootstrap: 100000 whole-patient draws, seed 202610071300, selection-unadjusted.

## Integrity and scope
Synthetic tests verify exact grouped deletions, recalculated scaling, patient weighting, constant/degenerate inputs, plan accounting and malformed-input rejection. In real evaluation poison all unpurchased cells and perturb outer fold 0's labels/curves only on its training-ineligible rows; predictions with the original paid queries must remain invariant. Save every outer model and plan privately for a separately implemented saved-model replay. Pin source/input bytes before any candidate outcome.

A lower-variance risk estimator is NOT guaranteed: optimizing a cross-validation criterion can itself overfit. This is one bounded trial, not independent validation of the repeatedly reused Lib1 patients. No Protected22/Lib2 access, no new treatment/control requirement, no automatic retry, no target/fold splicing, no Kaggle-entry change.

## Sources checked 7 October 2026
Liland, Skogholt and Indahl, A New Formula for Faster Computation of the K-Fold Cross-Validation and Good Regularisation Parameter Values in Ridge Regression: https://arxiv.org/abs/2211.15128 . This supports exact grouped-deletion reasoning; this implementation uses recomputed sufficient statistics rather than their particular residual-update algorithm.
Cawley and Talbot, On Over-fitting in Model Selection and Subsequent Selection Bias in Performance Evaluation (2010): https://www.jmlr.org/beta/papers/v11/cawley10a.html .
Official nested-evaluation example: https://scikit-learn.org/stable/auto_examples/model_selection/plot_nested_cross_validation_iris.html .

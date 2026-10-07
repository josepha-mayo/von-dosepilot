# Nonlinear pooled curve learning from same-budget mask augmentation

## Specific new hypothesis
The previous pooled model was shared/private linear ridge. Here a nonlinear shared curve-residual model is trained on multiple physically realizable sparse views of each historical curve. The extra views can teach sensitivity to dose placement rather than requiring an entirely new patient's biological label. They do NOT create new independent patients, new external evidence, or free inference measurements.

This family was designed while the direct and exact-contribution TabPFN trials were running. Their partial errors were not consulted. Those trials are unchanged. A repository-wide commit/content search found no completed CatBoost/forest/pooled-boost or mask-augmentation curve study, but completeness of unpublished historical work is not asserted. No claim of algorithmic novelty is made.

## Physical contract and folds
Authenticated Lib1 TRAIN only: 119 samples, 59 whole patients, 24 original normalized log-dose AUC outputs. The original fitting-only R13 planner chooses 64 distinct native doses, two or three per target and exactly sixteen third-dose upgrades. Every A/B layout uses 32 physical cells per source plate. The five original outer patient folds are unchanged. All organoids from a test patient are excluded from fitting, augmentation, scaling, residual targets and tree construction. No Protected22/Lib2 or source-control/genotype input is used.

## Augmentation
For each fitting fold and each target with k=2 or k=3 purchased doses, enumerate every k-dose combination from the unchanged eligible query catalog for that target. Replace ONLY that target's own chosen doses; keep its plate assignment sequence and the other targets' measurements unchanged. Thus every virtual training input is still a realizable 64-treatment-well observation with the original per-plate budget and number of doses per target. At inference use only the original selected plan, never a union or average across alternative physical layouts.

Fit an own-drug ridge head with penalty 0.01 for each fitting target/subset using both A/B views and equal-patient weighting. Its in-sample residual is the label for the nonlinear pooled model. Input features are: fixed 24-way target identity; up to three paid values and their normalized log-dose positions and known plate indicators (two-dose views repeat their final value/position with an explicit cardinality feature); two finite secant slopes; dose count; own-ridge prediction; trapezoidal area of the paid-point interpolant with constant boundary extension; seven summaries of the OTHER targets' purchased values; and the known layout bit. The approximate paid-point area is a feature, NOT a replacement for the true endpoint. No original unpurchased own-dose value is retained in the context summaries.

All source moments and ridge heads are fitted only on the outer-training patients. No outer OOF array becomes a fitting feature. Fitting on in-sample residuals is part of the declared sequential architecture, not an inner validation estimate.

## Two fixed arms, no post-outcome selection
PRIMARY: mask-augmented nonlinear residual model. MECHANISTIC CONTROL: identical nonlinear residual learner trained only on the original selected mask. Report both separately, irrespective of direction. Neither is a mixture with the other.

Estimator: scikit-learn HistGradientBoostingRegressor, squared error, learning rate 0.03, 400 iterations, maximum 7 leaves and depth 3, minimum 64 rows per leaf, L2 regularization 10, 128 bins, all numeric features (target identity is one-hot), no early stopping, fixed seed 202610071719. One CPU numerical thread. No parameter search. Each fitting patient/target/layout receives equal total weight; that weight is divided among its masks and organoids. Both arms have identical total sample-weight mass 2*n_training_organoids*24. Augmentation changes the distribution and number of correlated rows, not the number of independent patients; the unweighted leaf-size constraint is explicitly a row-count constraint.

## Evaluation and half-error target
Equal-patient/equal-target MSE and p90 patient RMSE, averaging A/B LOSSES only. Saved operating and retained64 arrays are comparators only, never fitting features. Each arm independently requires lower MSE, >=30 patient wins, 5/5 favorable outer folds and nonworse p90 versus BOTH comparators to become eligible for a further fresh full replay. Preserve R13/R18 gates before any later promotion. Half-error additionally means MSE <=0.000521372861048106 and p90 <=0.037419695944064885. No automatic promotion or Kaggle update.

Prespecified descriptive bootstrap: 100000 patient resamples, seed 202610071719, not selection-adjusted. No hyperparameter selection is performed, so no inner model search is added. Report final errors only after all five folds complete. No early exit because of poor partial results and no target/fold splicing.

## Integrity
Synthetic tests compare the own-ridge formula against an independent weighted fit, verify that every mask preserves target cardinality and plate budget, that augmentation preserves total patient/target weight, that context features exclude own-target values, and that saved numerical trees replay the library's predictions. Reject incomplete/nonfinite paid inputs. On real data check all outer folds' extraction under poisoned unpurchased values, exact base-head agreement with the existing 64-well own-drug predictor, numerical-tree replay and a fold-zero rebuild after altering only its training-ineligible rows. Save numerical states and tree-node arrays privately without executable model pickles. Publish only aggregate evidence and source. Hash the source and installed runtime before first biological fit; preserve failures without outcome-driven retries.

All results remain repeatedly reused adaptive Lib1 development, not independent biological validation. Additional synthetic masks must never be reported as additional real experiments or patients.

## Primary implementation reference
Official scikit-learn histogram-gradient-boosting regressor documentation (accessed 7 October 2026): https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.HistGradientBoostingRegressor.html . This supports estimator semantics, not a performance claim for DosePilot.

# Joint own-drug and cross-drug fitting at the original 64-well budget

## Question and rationale
The existing predictor first fits own-drug ridge heads and then fits a residual kernel while keeping those heads fixed. This experiment fits the own-drug coefficients and the same cross-drug kernel simultaneously. A jointly optimized training objective need not generalize better; the held-patient test decides. This is an application of established semiparametric kernel regression, not a new algorithm claim.

Primary reference: Rasmussen and Williams, Gaussian Processes for Machine Learning, Chapter 2, especially section 2.7 on explicit basis functions: https://gaussianprocess.org/gpml/chapters/RW2.pdf . Evaluation reference: https://scikit-learn.org/stable/auto_examples/model_selection/plot_nested_cross_validation_iris.html .

## Fixed contract
Lib1 TRAIN only: 119 samples, 59 whole patients, 24 unchanged normalized log-dose AUC targets. Existing fitting-only R13 acquisition remains 64 distinct physical treatment wells, 32 per plate, with eight two-dose and sixteen three-dose targets. Every A/B deployment is separately costed. Average losses, never prediction vectors. No extra controls or treatment measurements. No Protected22/Lib2 reads.

## Candidate menu, frozen before this outcome
Thirteen options, one global option selected per outer fold: the exact ten existing bandwidth-0.7 sequential residual options (identity, then fractions 0.1/0.3/0.6 crossed with ridge 0.1/1/10), followed by three joint options. The joint options retain own-drug ridge penalty 0.01 and use kernel penalties 0.1, 1, 10. The kernel, standardization and acquisition are unchanged. No target-specific or orientation-specific selection.

For each target j minimize weighted squared residual plus 0.01*||beta_j||^2 plus kappa*||f_j||_K^2, with y_j = mean_y_j + Z_own_j beta_j + f_j. Solve exactly by an eigendecomposition and a two/three-dimensional Schur complement. Joint fitting has no output spectral shrinkage. Sequential options are retained as fallbacks; ties choose the earliest menu entry.

## Evaluation
Five original whole-patient outer folds; three regenerated whole-patient inner folds inside each outer training set. All acquisition, standardization, kernel centering, fitting and option selection exclude the outer test patients. Never reuse global outer OOF rows as training features. Prespecified descriptive whole-patient bootstrap: 100,000 draws, seed 202610071130, not selection-adjusted.

The existing sequential procedure must reconstruct saved 64-well bandwidth-0.7 MSE 0.0010582750420801538 within 1e-12. The retained 64-well scientific candidate (0.001042745722096212, p90 0.037419695944064885) is a comparator only. A promotion proposal requires lower MSE, at least 30/59 patient wins, all five folds improved and nonworse p90 against BOTH references. No automatic promotion or Kaggle update.

## Integrity checks
Synthetic tests compare the Schur solution against an independent summed-kernel solve, verify normal equations, verify lower joint training objective than sequential fitting, reject nonfinite inputs, and test inference shape. On real data poison every unpurchased query value and verify prediction invariance. Rebuild outer fold 0 after perturbing only its labels; fitted predictions must be unchanged. Record code/input hashes, software versions, environment, selections and adverse slices. Preserve private arrays locally, publish aggregates only. One outcome run plus a separately recorded numerical replay is allowed; no outcome-driven retries or menu changes.

These are repeatedly reused development patients, not independent biological validation. The original submission and production model remain untouched regardless of this experiment's outcome.

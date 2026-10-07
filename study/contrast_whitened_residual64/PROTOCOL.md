# Paired-plate contrast whitening of multi-output residuals, 64 wells

## Distinct hypothesis
The current shared spectral shrinkage ranks response modes by residual magnitude. This trial uses historical TRAIN plate-contrast covariance as a noise proxy, whitens residual outputs before spectral shrinkage, and transforms predictions back to the original AUC units. It may improve the signal-to-noise structure of the learned output modes. Plate contrast is a proxy, not a proven noise-only process and not a clinical uncertainty estimate.

This differs from the active budget72_paired_noise study: that method changes the input-coordinate conditional predictor using source-well covariance. This trial leaves the 64-well input geometry and own-drug base unchanged and changes only output-space regularization. It is not a retry of input noise conditioning, output target-wise selection, isotope smoothing or joint own-drug fitting. Standard GP covariance and explicit basis-function background: Rasmussen and Williams, Chapter 2, https://gaussianprocess.org/gpml/chapters/RW2.pdf .

## Frozen procedure
Same Lib1 TRAIN population (119 samples, 59 patients, 24 targets), same fitting-only 64-well acquisition (32 per plate), same own-drug ridge 0.01, same bandwidth-0.7 additive input kernel, same ten sequential residual options and five outer/three inner whole-patient folds. No new treatment well or plate-control requirement at inference.

For EACH fitting partition only, calculate d=(AUC_plate1-AUC_plate2)/2, subtract its fitting patient-weighted mean, and form C=Cov_patient(d). Let mu=trace(C)/24. Three fixed output transforms are offered in order: identity; diagonal covariance proxy 0.5*diag(C)+0.5*mu*I; full covariance proxy 0.5*C+0.5*mu*I. Normalize covariance proxies by mu, use inverse positive square root to whiten, and the positive square root to restore units. If mu <=1e-12, use identity. The 0.5 shrinkage is fixed, not tuned. Exact identity is the incumbent.

Each transform is crossed with the existing ten spectral options, giving 30 choices. A single global transform/option is selected by patient-balanced inner OOF MSE across all targets and both alternative layouts. Ties choose the earliest index. Acquisition, scaling, noise proxy, spectral fitting and selection are rebuilt inside each inner training set; no global OOF predictions become training features.

Primary output is unchanged equal-patient/equal-target mean of A/B losses. Against BOTH operational baseline and retained scientific candidate require lower MSE, >=30 patient wins, 5/5 better outer folds and p90 nonworse for eligibility for a separate replay. No automatic model promotion. Prespecified descriptive bootstrap: 100000 patient resamples, seed 202610071200, not selection-adjusted.

## Integrity and boundaries
Identity must reproduce operational MSE 0.0010582750420801538 within 1e-12. Outer fold 0 labels AND its historical plate AUCs are perturbed after fitting; rebuilding that fold's prediction must be invariant. Inference only receives the purchased 64 values. Synthetic tests check whitening inverse, positive definiteness, weighted patient handling, zero-noise fallback, and NaN rejection. Code and input hashes are frozen before outcome; report negatives. No Protected22 access, no clinical or independent validation claim, no Kaggle entry change, no automatic retry.

Implementation reuses the audited incumbent construction and metrics from the joint_own_drug_kernel64 runner; its joint candidates are NOT offered or used by this trial. The reuse is code reuse only, not a model ensemble.

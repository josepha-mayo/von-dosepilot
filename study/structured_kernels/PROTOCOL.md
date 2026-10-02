# DosePilot structured-kernel study, 2 October 2026

## Scope and fixed hypotheses
This is one new adaptive Lib1 development study, not untouched validation. The live public base was 613aa18. A newer shared-workspace source commit 4afbac69059d88d433186df96b94be104d36b608 supplied a completed additive-kernel control with reproduced MSE 0.001060552730112811. That source and its historical reference receipts are fixed for this study. The other continuation's patient-bootstrap work is not repeated or claimed as ours.

Two new arms are fixed before execution. Neither changes the measurement plan, endpoint, patient weighting, base ridge or spectral parameter grid.

**Pair mixture:** retain the linear paid-value kernel. Center each drug-group Gaussian kernel using fitting-row patient weights. Let A=sum(d_j*C_j), where d_j is the number of purchased values for drug j. Let P=sum_{j<k}(d_j*C_j)*(d_k*C_k), with elementwise products. The nonlinear component is (A + q*P)/2, with q=weighted_diag_energy(A)/weighted_diag_energy(P), determined on fitting rows only. If pair energy is at most 1e-14, its scale is zero. This tests nonlinear co-variation between distinct drug groups without increasing measurement cost. It does not identify causal drug interactions or an orthogonal biological ANOVA decomposition.

**Mean/contrast:** retain the same linear kernel. Within each 2/3-value group of base-standardized paid inputs, separate the group mean and mean-centered contrast vector. Replace its Gaussian component by d_j/2 times [exp(-(mean difference)^2/2) + exp(-squared contrast distance/(2*(d_j-1)))]. This tests whether baseline response level and within-group pattern benefit from separate similarity measures. The decomposition is of standardized assay values, not a biological mechanistic assertion.

## Containment and comparisons
Use exactly 119 original Lib1 samples, 59 whole patients, 24 original unclipped AUC targets, five original patient outer folds and three original patient inner folds. Rebuild R13 acquisition and base ridge (lambda=0.01), scalers, every kernel center/energy and residual matrix inside each fitting slice. Each orientation purchases exactly 64 distinct physical treatment wells, 32 per plate. Both orientations are separate training rows with half patient mass. At inference use only the selected orientation. Average A/B LOSSES, never their prediction vectors.

Each arm independently selects one common configuration from identity plus fractions {0.1,0.3,0.6} x residual ridge {0.1,1,10}, using pooled equal-patient/equal-target inner held-patient error. Rebuild and score unchanged additive and S2 controls in the same run. No extra fractions, favorable target splicing, output clipping or response-based sample exclusions. No protected Lib2 or original workbook is opened. No original-outer-OOF amplitude optimum is used.

All candidate predictions are saved and hashed before opening historical reference predictions. The exact additive and S2 replay must match their recorded MSEs within 1e-12, and the R13 control within 1e-12. Reproduction is a control check, not a second independent experiment.

## Unchanged promotion interpretation
A new arm is eligible to replace the newer additive control only if MSE is lower, at least 30/59 patients and 3/5 folds improve, and p90 patient expected RMSE is nonworse. Apply the same clauses versus S2. It must additionally pass EVERY original R13 and R18 criterion: at least 5% lower MSE, at least 40/59 patient wins, at least four favorable folds, nonworse p90 and both candidate orientation means below that reference's expected MSE. Compare to both historical references using authenticated aligned saved arrays or the established private R18 receipt. Incomplete gate coverage is not promotion.

Report both arms including failures, target regressions and ties. Bootstrap intervals from 10,000 paired whole-patient resamples (seed 20261002) are descriptive, not search-corrected confidence guarantees. Full outcome reuse remains disclosed.

## Verification, privacy and deployment
Before real fitting: compare the fast pair formula with explicit pair enumeration, check PSD, train/query centering, permutation and batching invariance, zero-input degeneracy and nonfinite rejection on fictional arrays. After fitting: recompute per-patient/target scores and every gate separately; check saved dual coefficients against direct weighted kernel-ridge algebra; check all selected wells and masking invariance. No source response re-read is needed for score checks.

These global kernels require all 64 input values. Missing-data behavior is all-output withholding, not selective head abstention. Nonlinear model archives contain training feature arrays and remain private. A new runtime adapter would require separate validation before deployment. A lower development score alone does not authorize a silent change to the accepted Kaggle entry.

Prior art reviewed: Durrande et al., ANOVA kernels and RKHS of zero mean functions, DOI 10.1016/j.jmva.2012.08.016, arXiv:1106.3571. Sums and products of group kernels are established mathematics. This study uses independently written code and makes no novelty claim for that theorem.

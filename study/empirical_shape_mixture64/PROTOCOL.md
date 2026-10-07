# Empirical smooth-curve mixture at the original 64-well budget

## Objective and hypothesis
The retained research MSE is 0.001042745722096212. The objective remains <=0.000521372861048106 with p90 patient RMSE <=0.037419695944064885, all 24 unchanged endpoints, and 64 physical treatment wells. This objective has not been achieved.

Direct and balanced-context TabPFN and exact-contribution TabPFN completed with worse errors. Nonlinear mask augmentation also completed without beating the retained model. This new experiment tests a distinct hypothesis: responding and nonresponding historical curves may be better represented as a mixture of smooth shapes than one Gaussian population or a direct predictor. It is an empirical statistical model, not a biological mechanism or an original Bayesian method claim.

A repository-wide commit search for prototype/archetype/sigmoid/Hill/logistic curve families found no matching completed branch. The historical search is not guaranteed complete. The prior full-curve conditional model used a single Gaussian covariance; here nonlinear posterior component weights distinguish this arm. A matched single-Gaussian arm is a declared mechanistic control, not a rediscovery claim.

## Fixed population and physical contract
Authenticated Lib1 TRAIN CSV only: 119 organoid samples, 59 whole patients, 24 exact normalized log-dose AUCs. Five original whole-patient outer folds. The existing R13 planner is rebuilt using only the fitting patients; each alternative layout has 64 distinct eligible native doses, 32 physical cells per plate. No change to eligible doses, 2/3-dose target counts, the sixteen upgrades, outputs or normalizations. A and B prediction vectors are never averaged; only their losses are averaged.

The full 416 historical TRAIN values are available solely to fit the distribution of complete curves on training patients. At prediction each target's own purchased 2/3 values are used. The other purchased values are not secretly replaced by full historical data. Across all 24 outputs the observation plan still contains only the same 64 wells. No controls, genotype, patient identity, external biological responses or Protected22/Lib2 inputs are used. No patient data are transmitted.

## Model fixed before candidate evaluation
For each target and each fitting organoid, average its two historical plates for smooth-shape estimation. Fit a constant or a member of a fixed sigmoid dictionary to that mean curve. Dictionary: 25 centers from -0.25 to 1.25, slopes {2,4,8,16}, on the full target's normalized log-dose span [0,1]. Each shape is intercept + amplitude*sigmoid(slope*(coordinate-center)); amplitude can be positive or negative, no clipping of measured values. Intercept/amplitude solve penalized least squares with mean squared residual plus 0.001*amplitude^2. Choose the lowest penalized TRAIN-curve fitting error, constant first for deterministic ties. These are fitting parameters, not choices made using held-out-patient error.

Repeat each smooth template across the two plates. Add the fitting patient-weighted mean residual at each dose/plate to represent systematic shape discrepancies. Component weights assign equal total mass to every fitting patient, divided among their organoids.

Estimate a common within-component residual covariance per target from the raw fitting curves minus their templates, centered by the systematic residual. Multiply by D/(D-4), where D is the target's full number of physical cells, as a fixed degrees-of-freedom adjustment. Shrink covariance 50% toward its diagonal and add 0.0001*I in raw viability-squared units. This is a regularized discrepancy model, not an estimate or proof of an irreducible noise floor. No scale or shrinkage tuning follows outcomes.

PRIMARY arm: finite Gaussian mixture with those smooth historical component means and common discrepancy covariance. Condition on the acquired physical indices for each A/B layout. Compute posterior component weights with a Gaussian likelihood and equal-patient prior. Each component's exact scalar AUC is a linear functional of its full curve; use the Gaussian conditional mean of that linear functional and then average across posterior components. Integrating unpurchased values is prediction, not free measurement.

CONTROL arm: replace the mixture by the one Gaussian with exactly the same mean and covariance (component covariance plus common discrepancy covariance), and condition identically. This separates nonlinear mixture weights from matched moments. Both arms are reported separately irrespective of direction. No target/fold/arm selection, no post-outcome blending, no existing-kernel fallback or parameter sweep.

## Evaluation and gates
No outcome-selected hyperparameters, hence no inner model search. Every template, mean, covariance, mixture weight and physical plan excludes the entire outer test patient and all their organoids. The full-grid loader's endpoint-identity check is not a fitting step. Raw AUC endpoints and all patients remain in the denominator. Equal-patient/equal-target MSE; p90 of patient RMSE; per-fold and target breadth. Saved operating and retained arrays are comparators only.

An arm is eligible for a further fresh end-to-end replay only if it beats BOTH retained64 and operating64 on mean, >=30/59 patients, all five outer folds and nonworse p90, with the original physical contract. The half-error flag additionally tests the stated absolute threshold and retained p90. Preserve R13/R18 gates before any promotion. No automatic promotion or Kaggle entry update. All five folds finish before overall scores are inspected; no early stopping on losses.

Prespecified descriptive bootstrap: 100000 whole-patient draws, seed 202610072102. This is repeated adaptive development on previously inspected Lib1, not independent biological validation or selection-adjusted inference.

## Tests and audit
Before freezing run synthetic tests for Gaussian conditioning, one-component equivalence, exact all-observed endpoint reconstruction, mixture normalization, matched moments, sample order/patient-duplication invariance, finite covariance, missing-input rejection and curve shape fitting. Save numeric component states and selected physical plans privately. Independently recompute posterior predictions with a separately written Cholesky/log-sum-exp implementation and re-evaluate all patient-level aggregates. Rebuild outer fold 0 after changing only its training-ineligible labels and all its historical curves, keeping the actual purchased query values unchanged; fitted states and predictions must be invariant. Poison every unpurchased query cell. Record hashes, versions, timings and failure receipts. No executable model pickle, patient-array publication, silent retry or outcome-driven version change.

## Established sources
Huson and Kinnersley, Bayesian fitting of a logistic dose-response curve with numerically derived priors, Pharmaceutical Statistics (2009), DOI 10.1002/pst.348. Its work supports the general use of logistic curve priors, not this particular model or DosePilot accuracy.
Rasmussen and Williams, Gaussian Processes for Machine Learning (2006), https://gaussianprocess.org/gpml/ . Gaussian conditioning is established mathematics.
Cawley and Talbot, On Over-fitting in Model Selection and Subsequent Selection Bias in Performance Evaluation (2010), https://www.jmlr.org/beta/papers/v11/cawley10a.html .

# Pooled cross-drug sparse-curve reconstruction, 64 wells

**Status:** Prepared implementation and fixed candidate specification. Synthetic tests are complete. No biological evaluation, desktop run, public freeze commit, model promotion or Kaggle update has occurred in this session.

**Family ID:** `pooled_cross_drug_curve64_v1`

## 1. Question and success criterion

Can sharing a nonlinear mapping from sparse dose-response observations to response-area residuals across drugs improve the original 64-well task more than fitting the existing multi-output residual kernel?

The concrete target remains patient-balanced MSE **<= 0.000521372861048106**, half the retained research value **0.001042745722096212**, with nonworse p90 patient RMSE. A smaller gain is not a 2x achievement. Eligibility for promotion additionally requires lower MSE, at least 30/59 patient wins and all five favorable outer folds against both retained research and operating comparators, plus the original R13/R18 checks and a separate fresh numerical replay. Those historical gates are not replaced by this runner.

The novel research question here is the representation and sharing structure, not a claim of inventing multitask learning or random Fourier features. This family has not been shown to outperform DosePilot. A live duplicate/ownership check is required before its first biological run because other agents may advance the repository after this package was prepared.

## 2. Fixed physical and data contract

Use only the authenticated Lib1 TRAIN CSV: 119 organoid samples, 59 whole patients, 24 unchanged normalized log-dose AUC targets. Select the original R13 plan inside each fitting partition: 64 distinct native doses, eight targets with two doses and sixteen with three. One alternative layout purchases 32 p1 and 32 p2 wells. The other layout is a separately costed alternative. Average their **losses**, never their prediction vectors.

The original eligible native-dose catalog is unchanged. No new treatment or control measurement is required. Full historical curves may enter the existing training loader and target construction, but query inference sees exactly the selected 64 finite paid readings. The four omitted quadrature-support doses identified by the catalog audit are not added by this experiment.

No Protected22/Lib2 response, biological workbook, external patient source, network service, credentials, or model API is used. The implementation refuses biological execution outside Windows D:. It does not create another account, submit to Kaggle or modify the operating repository.

## 3. Candidate representation

Retain the original own-drug ridge base, penalty 0.01, fitting-only acquisition, centering and scaling. For each patient sample, target drug and alternative layout construct a 15-column row from purchased values and metadata:

1. Up to three log-dose positions normalized by the fixed target integration interval.
2. Up to three observed viability values.
3. Three presence indicators.
4. Three plate signs, -1 for p1 and +1 for p2.
5. Own-drug base AUC prediction, mean purchased viability, and observed log-dose span.

The nonexistent third slot of a two-dose target is structurally padded with zero and accompanied by a zero presence bit. This does not impute a missing purchased reading: any nonfinite paid measurement causes an error. Positions outside the integration interval remain outside [0,1]; no clipping or target redefinition is allowed.

Fit the residual `observed AUC - own-drug base prediction`. The base prediction and residual used during fitting are in-sample within that fitting partition, as in the incumbent sequential residual method. This introduces no held-out-patient label path but can create a training/inference mismatch; it is a declared modeling limitation, not corrected by pretending those base predictions are cross-fitted.

Rows from all 24 target drugs share a representation. Each target receives a private deviation from the shared mapping. Flattening 24 targets into more rows does **not** increase the independent patient count beyond 59. All splitting and weighting remain patient-based.

## 4. Fixed nonlinear map and objective

Use fitting-patient-weighted feature means and scales, with standard-deviation floor 0.05. Add an intercept, the 15 standardized linear features, and 64 random Fourier features:

`phi(z) = [1, z, sqrt(2/64) * cos(z @ omega + phase)]`

Generate `omega ~ Normal(0,1)/sqrt(15)` and `phase ~ Uniform(0,2*pi)` once from seed **202610071328**. The seed and feature count are not searched. This is a finite random-feature model, not an exact RBF Gaussian process.

For target t, predict residual `phi @ (a + b_t)`. Fit:

`sum_i w_i * (r_i - phi_i @ (a + b_task(i)))^2 + alpha*(||a||^2 + sum_t ||b_t||^2)`.

Every whole patient has the same total weight, shared equally over that patient's organoids, targets and the two alternative layouts. Solve the shared/private ridge system exactly through a block Schur complement. Synthetic tests compare it to an independent dense solve and verify its normal equations.

Offer only **three** alpha values: **0.001, 0.01, 0.1**. Shared and private penalties are equal by specification. No separate target, orientation, seed, feature-count or bandwidth sweep follows an outcome.

## 5. Thirteen-option selection menu

The first ten options are the existing bandwidth-0.7 residual family: identity, then fractions {0.1,0.3,0.6} crossed with ridge {0.1,1,10}. The last three are the pooled-curve corrections above. A pooled correction replaces the incumbent cross-drug correction; the two are not stacked together.

Choose one global option for all targets and both layouts using three whole-patient inner folds inside each of the five original whole-patient outer folds. Regenerate acquisition, base fitting, feature normalization, shared/private fitting and kernel fitting inside every inner fitting partition. Ties select the earliest menu entry. Never train on predictions recycled from the full global outer-OOF matrix.

The first ten options must independently reconstruct operating MSE **0.0010582750420801538** within 1e-12. The retained research predictions are only a comparator; their patient, target and fold alignment must be checked before scoring.

Report primary patient-balanced MSE, p90 patient RMSE, all five fold errors, patient breadth, target regressions and the prespecified 100,000-resample whole-patient paired bootstrap (seed 202610071328). The bootstrap is descriptive and selection-unadjusted.

## 6. Integrity and attempt management

`run_trial.py freeze` verifies the current expected source/input hashes and creates an exclusive local freeze file binding the package, menu and existing dependencies. Its status explicitly says it is a **local** freeze, not a public commit. Review ownership and preserve that receipt before `run_trial.py run` opens any candidate outcome. Existing output directories are rejected; failures are saved, never silently erased or retried.

At execution, every unpurchased query reading is poisoned independently for A and B. Refit outer fold zero after perturbing only its training-ineligible labels and curve values; predictions using its original paid queries must remain invariant. The runner saves each selected outer model as numerical arrays and JSON metadata in a private NPZ, never executable pickle. A separate saved-model inference expression must reproduce the selected prediction within 1e-12. A successful result would still need the separate fresh training replay and historical reference audits before any promotion.

The current local tests use invented arrays and a synthetic engine test double. They verify mathematics, orchestration, saved-state reconstruction and negative guards, but do not execute or reproduce the pinned original biological engine. No clinical or biological uncertainty guarantee follows from these tests.

## 7. Claim and scheduling boundaries

All biological outcomes would remain repeated adaptive development on the same Lib1 patients, not untouched independent validation. Sharing across related drug tasks may help, fail, or cause negative transfer. Neither a training objective improvement nor a successful synthetic recovery is evidence of a biological improvement.

Continue approved research through 8 October, Africa/Lagos time. Reserve 9 October for final regression, packaging, updating the existing accepted entry and checking it saved. This package does not extend that schedule or replace the existing Calendar reminder.

## 8. Primary method sources

- Evgeniou, Micchelli and Pontil, *Learning Multiple Tasks with Kernel Methods*, JMLR 6 (2005): https://www.jmlr.org/papers/v6/evgeniou05a.html
- Bonilla, Chai and Williams, *Multi-task Gaussian Process Prediction*, NeurIPS 2007: https://proceedings.neurips.cc/paper/2007/hash/66368270ffd51418ec58bd793f2d9b1b-Abstract.html
- Scikit-learn official `RBFSampler` documentation, inspected 7 October 2026: https://scikit-learn.org/stable/modules/generated/sklearn.kernel_approximation.RBFSampler.html

These support established method ingredients. The implementation is a custom finite-feature multitask ridge model, not a reproduction of those papers' empirical results.

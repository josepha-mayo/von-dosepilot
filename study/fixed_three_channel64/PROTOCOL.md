# Fixed equal-weight three-channel estimator, 64 wells

Built with PriorLabs-TabPFN. Model name: TabPFN-von-DosePilot-Three64.

This is one fixed inference-time arithmetic ensemble, NOT a fitted stack. The channels are: (1) the operating 64-well bandwidth-0.7 kernel predictor; (2) the primary full-context direct-AUC TabPFN-v2 predictor; (3) the full-context exact-purchased-contribution plus TabPFN-v2 residual predictor. Use exactly 1/3 weight for each channel for every target, patient, fold and query orientation. There is no fitted intercept, rank correction, calibration, weight search, target-specific choice, or outcome-based fallback.

The ensemble is declared before either TabPFN study has a final RESULT.json and before any of their partial errors have been examined. Producer freezes are pinned; output hashes will be bound only after the outputs actually exist. The component labels and weights cannot change after results. This is an additional estimator to evaluate, not permission to relabel the strongest individual arm or splice results.

All three channels must consume the identical 64 native-dose/plate assignments per alternative A/B query. Verify the direct and exact studies' five physical plans match each other and the authenticated R13 planner reconstructed on the same outer-training rows. The kernel component is the already replayed operating bandwidth-0.7 predictor under that plan, not the separately calibrated research candidate. Retained research64 is only a comparator. No source controls, extra dose or prediction from the other A/B orientation is fused into a query.

Each component was fitted without its outer-test patients; fixed averaging adds no meta-training. This therefore does not reuse outer OOF rows as TRAINING data for a learned stack, the failure mode found in older stacking attempts. It still remains adaptive model development on repeatedly inspected Lib1 and is not independent biological validation. Ensembling can help only to the extent errors differ; no improvement is asserted in advance.

Report the original equal-patient/equal-target MSE, p90, patient/fold breadth and adverse target slices over all 119 samples and 59 whole patients. Score A/B losses separately and average losses. Preserve exactly 24 target outputs and 64 physical treatment measurements per query, 32 per plate. No data imputation is introduced.

Against BOTH operating and retained64 references, eligibility for full fresh producer replay requires lower MSE, >=30 patient wins, all five outer folds favorable and nonworse p90, then the existing R13/R18 audit gates. Half-error additionally requires MSE <=0.000521372861048106 and p90 <=0.037419695944064885. No automatic promotion or entry update. A passing arithmetic ensemble is not yet a deployable product.

Prespecified descriptive bootstrap: 100000 whole-patient resamples, seed 202610071730, not selection-adjusted. Source/input identity hashes and producer outcome hashes are recorded. Final evaluation waits for BOTH frozen producer jobs to complete; no truncation to completed targets or folds. No automatic retries, no model or weight change, no Protected22/Lib2 access. Patient arrays and model states remain private.

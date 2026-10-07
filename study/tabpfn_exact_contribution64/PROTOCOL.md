# Exact purchased-contribution anchor plus local TabPFN, 64 wells

Built with PriorLabs-TabPFN. Research model: TabPFN-von-DosePilot-Exact64. This is a separate fixed arm, not a modification of the running direct-AUC TabPFN trial.

## Hypothesis and mathematical distinction
The endpoint is an exact linear functional of the full two-plate curve: y = Q_observed * x_observed + Q_missing * x_missing. Every purchased observation's contribution is already known. Rather than ask a pretrained regressor to relearn that term, subtract it from the fitting target and add it back exactly after predicting the missing contribution. This is a feature-dependent target transformation, not a new measurement or a guaranteed reduction in MSE. A learned model can still be worse than direct regression because the missing component remains correlated with the purchased values.

The earlier full-curve Gaussian conditioning study was a parametric joint-covariance model; this uses an external pretrained nonlinear tabular prior on the exact unobserved-contribution target. Earlier per-drug latent quadrature and the pooled shared/private ridge model are not reused as prediction models. No claim of inventing Bayesian conditioning, quadrature or residual learning is made.

## Freeze timing
This candidate is specified while the two direct-AUC TabPFN arms are running. Only progress counts and runtime messages from that trial have been inspected during this design; its partial biological errors were not opened or used to choose this transformation. Both trials must finish all original patient folds irrespective of their outcomes. No per-target/fold model selection or blending will follow these results.

## Fixed task and inputs
Authenticated Lib1 TRAIN CSV only, 119 samples from 59 whole patients, 24 unchanged raw normalized log-dose AUCs. Original R13 acquisition is rebuilt within each of five whole-patient outer-training partitions. Exactly 64 distinct eligible native doses and 32 physical cells per plate per alternative A/B layout. The original eligible catalog is unchanged.

Use the already verified full-grid metadata map only to recover exact trapezoidal integration coefficients and the mapping from the eligible 164 native coordinates to the historical 208 native coordinates. The source CSV has 416 historical physical treatment values, but only the selected 64 eligible values enter inference. No excluded support dose is purchased. Full-grid responses verify endpoint identity but never become query features or fitting values for a held-out patient. No Protected22/Lib2, controls, genotype, patient ID, public sensitivity label or external clinical input is available at inference.

For each target and each source layout, compute known = paid64 @ Q_observed. Fit residual labels y-known separately for the A and B training views. At inference output known_query + predicted_residual. The same patient-separated full context as the primary direct-AUC trial is used: all outer-training organoids and both alternative views. This is unweighted context training; patients with more organoids contribute more context rows. Test metrics remain equal-patient. No balanced-context arm is added here.

## Fixed pretrained configuration
Official V2 checkpoint SHA256 2ab5a07d5c41dfe6db9aa7ae106fc6de898326c2765be66505a07e2868c10736; compatible tabpfn 8.2.0 runtime; explicit ModelVersion.V2. The local checkpoint and Prior Labs 1.1 attribution/license are unchanged. For each target: its own purchased columns first, remaining columns in original order, plus the known layout bit. Exactly two estimators, no autoscaling, fit_preprocessors mode, one preprocessing worker. Seed 202610071519 + 1000*fold + 10*target, matching the primary direct-AUC arm. Raw values are not clipped or normalized externally. Local CPU inference is capped at one numerical thread to coexist with the already running trial. No model API, downloads, purchases, accounts, browser or patient-data upload; outbound connections and telemetry are disabled.

## Evaluation and protection
One fixed model per target; no hyperparameter search or inner outcome selection. All acquisition and training exclude the test patient and all their organoids. Average A/B losses, never their predictions. MSE and p90 are equal-patient/equal-target. Promotion eligibility requires lower mean, >=30 patient wins, all five folds improved, and nonworse p90 versus both retained64 and operating64, then independent fresh replay and preserved R13/R18 gates. Half-error additionally requires MSE <=0.000521372861048106 and nonworse retained p90 0.037419695944064885. No automatic promotion or Kaggle update.

Prespecified descriptive bootstrap: 100000 patient resamples, seed 202610071519. Repeated adaptive development, not selection-corrected inference or independent biological validation. The direct-AUC arm may be compared after BOTH complete, but cannot be spliced, blended or used to change this candidate.

Before freeze run synthetic decomposition, endpoint mapping, paid-input, zero-residual, patient isolation and local checkpoint tests. Verify exact endpoint reconstruction using the frozen TRAIN loader. During evaluation poison unpurchased values and refit first fold/target after perturbing only its evaluation labels. Save each target's predicted missing contribution and exact known contribution for independent sum and metric checking; preserve context inputs privately for fresh checkpoint replay. Existing output directories are rejected. Record failures without changing settings or erasing partial artifacts.

## Primary source and attribution
Official checkpoint/license: https://huggingface.co/Prior-Labs/TabPFN-v2-reg
Runtime/version API and offline model-path guidance: https://pypi.org/project/tabpfn/8.2.0/
Hollmann et al., Accurate predictions on small data with a tabular foundation model, Nature (2025), DOI 10.1038/s41586-024-08328-6.
The known-contribution identity is algebra, not evidence that this pretrained prior will improve DosePilot. No biological gain is claimed before execution.

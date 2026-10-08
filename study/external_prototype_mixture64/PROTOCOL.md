# External prototype mixture with a matched Gaussian control, 64 wells

## Status and objective
This is a distinct adaptive follow-up to the completed external-correlation transfer. That earlier model gave MSE 0.001068618046193161 and failed to beat retained64. This follow-up is NOT claimed to have been proposed before seeing that result. It asks whether collapsing the external response distribution to its covariance discarded useful nonlinear structure.

The half-error objective remains MSE <=0.000521372861048106 at the original 64-well budget with nonworse retained p90 0.037419695944064885. Neither collecting external curves nor constructing prototypes meets that objective.

## Source and rights boundaries
Use exactly the previously audited NCI HTS384 public CSV (SHA256 4088c00b6eea513c4d5add4e7052b53f66a13c4c541c42ef853f8658a9db8cba) and its fixed prepared cache (SHA256 53aae154d310256d77ddbc9c9d6ddab461235496e12009a23105620c0181b66c). The 84,702 complete five-dose curves come from 60 cell identifiers and 1,135 compounds, not 84,702 independent patients. Use M_PTC/100, not starting-cell-corrected growth. Maintain the declared equal-cell/equal-compound-within-cell weights. No clipping, new drug subset or exclusion after organoid outcomes.

Cell-line assay, dose span and biological domain differ from organoids. Only relative-dose shape is transferred: no source potency, NSC identity, source response mean or source variance is substituted for local organoid quantities. The source is offered for scientific use by NCI; no archive-wide MIT/CC license or NCI endorsement is asserted. Raw source data, learned prototype arrays and patient data remain local. Any later model distribution requires its own rights review. Original source attribution and retrieval hashes are preserved.

## Fixed source-only compression
Compress source five-point response vectors with MiniBatchKMeans: 256 clusters, random_state 20261008, n_init=1, batch_size=4096, max_iter=100, max_no_improvement=20, reassignment_ratio=0.01, tol=0. Sample weights are multiplied by the number of curves to retain their ratios and numerical scale. The run is CPU-limited to one numerical thread.

After assigning all source curves to centers, recompute each centroid and cluster mass using exact original source weights. Empty clusters are dropped, not replaced based on evaluation performance. Store the original full-source mean and covariance separately. The centroid mean must reproduce the full-source weighted mean, and full covariance minus between-centroid covariance must be positive semidefinite within numerical tolerance. Source compression reads no DosePilot labels, but is not biological validation. No cluster-count or seed search is permitted.

## Matched-moment construction
For each target and fitting partition, reconstruct the same paired-mean/contrast covariance model as the first external-correlation trial, with 50% imported relative-dose correlation, 10% diagonal shrinkage and 1e-6 variance floor. Its fitting means, per-dose scales and paired-plate contrast come exclusively from local fitting organoid patients. The resulting full physical mean and covariance define the Gaussian control.

Construct component means from two equally weighted populations: historical fitting organoid mean curves (equal patient mass divided among organoids) and the external weighted centroids. Interpolate external centroids to the target's relative log-dose positions, center by the full external source mean and rescale each coordinate by local fitting standard deviation divided by the full external interpolated standard deviation. Both populations therefore share the local mean.

Shrink the component deviations from that mean by sqrt(0.5), duplicate them across both physical plates, and add the fitting per-plate mean. Let B be their weighted between-component covariance. Set their shared residual covariance to C_control - B. The construction retains exactly the same overall physical mean and covariance as the Gaussian control. Positive definiteness and first-two-moment identity must be verified without tuning. Compression remainder and diagonal regularization stay in the common residual covariance rather than being lost.

PRIMARY arm: compute Gaussian-likelihood posterior weights over these component means from the purchased own-target cells, then average each component's conditional exact AUC mean. CONTROL arm: the single Gaussian with those same overall moments. Its base and selected residual-kernel procedure must reproduce the preceding external-correlation MSE 0.001068618046193161 within 1e-12. Thus any difference tests higher-order mixture structure, not extra measurement, a different mean, variance or regularization strength. The operating own-drug procedure is a separate reproduction control, not a fallback for selectively reporting failed targets.

For each arm use the unchanged bandwidth-0.7 additive residual kernel with the original ten options: identity; spectral fraction {0.1,0.3,0.6} crossed with ridge {0.1,1,10}. Each arm separately selects one global option in three whole-patient inner folds. No target/orientation-specific selection, post-outcome arm mixture, or outer-target splice.

## Task and evaluation
Authenticated Lib1 TRAIN: 119 organoids from 59 whole patients, 24 original normalized log-dose AUCs, original eligible concentration catalog, original R13 64-distinct-dose allocation with 32 physical cells per plate per A/B alternative. Rebuild acquisition, local covariance, component populations, scales and residual fitting in every inner/outer training split. Do not use outer OOF rows as fitting features. Full historical curves are available only for fitting patients; queries consume only their selected 64 measurements. Average A/B losses, never their predictions. No new standard-control/genotype inputs or Protected22/Lib2 access.

Run the original five patient-held-out outer folds to completion. Each new arm independently requires lower MSE, >=30/59 patient wins, 5/5 favorable folds and nonworse p90 against both operating and retained64 before eligibility for a separate fresh end-to-end replay. Preserve R13/R18 gates before promotion. Half-error has the separate absolute threshold above. No automatic model promotion or Kaggle update. Bootstrap: 100000 whole-patient samples, seed 202610080028, descriptive and selection-unadjusted.

## Integrity
Tests cover weighted compression, covariance decomposition, exact matched moments, independent log-sum-exp/Cholesky posterior calculation, all-observed reconstruction, one-component equivalence, patient weighting, missing inputs and the complete 24-output saved-state path. Pin code, source-bank hash and runtime before the first organoid candidate fit. Perturb outer fold zero's training-ineligible labels and full curves, with its original purchased query values preserved, and verify unchanged learned states and predictions. Poison every unpurchased query cell. Save numeric states and independently replay all 15 outer models using separate posterior and kernel calculations. Preserve failures without post-outcome tuning or silent retries.

These are repeated adaptive-development results on already inspected Lib1 patients, not independent biological validation or a claim of clinical utility. A matched control and numerical replay improve interpretability but do not undo data reuse.

## Established sources
NCI official source and schema: https://wiki.nci.nih.gov/spaces/NCIDTPdata/pages/998965250/HTS384+Growth+Inhibition+Data
Official weighted MiniBatchKMeans parameter semantics: https://scikit-learn.org/stable/modules/generated/sklearn.cluster.MiniBatchKMeans.html
Gaussian conditioning background: https://gaussianprocess.org/gpml/
The mixture construction and moment matching are explicitly specified algebra, not a claim to invent these statistical ingredients.

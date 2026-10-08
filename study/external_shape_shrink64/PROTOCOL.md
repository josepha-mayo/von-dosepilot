# External relative-dose correlation prior, original 64-well DosePilot task

## Objective and distinct hypothesis
The requested half-error target remains MSE <=0.000521372861048106, with retained p90 <=0.037419695944064885, all 24 original endpoints and 64 purchased treatment wells. It is NOT achieved by obtaining new data or passing software checks.

This trial introduces a genuinely external, curve-specific data source instead of more transformations or masks of the same organoid patients. It tests whether the relative-dose correlation structure estimated from an independent cell-line screen regularizes organoid curve reconstruction. This is an application of covariance shrinkage and Gaussian conditioning, not a new algorithm claim. Generic TabPFN, internally estimated Gaussian/mixture priors, alternative physical replication and spatial-control transport have already failed; those completed menus are not rerun.

## External source audited before any candidate outcome
Official NCI HTS384 September 2026 public concentration/response CSV, downloaded anonymously from its linked version-3 attachment. SHA256 4088c00b6eea513c4d5add4e7052b53f66a13c4c541c42ef853f8658a9db8cba; 38,336,989 bytes. This file has 446,805 rows forming 89,361 curve groups. The fixed parser retains 84,702 complete five-concentration molar curves from 60 cell identifiers, 1,135 compounds and 65 experiment batches; 4,659 incomplete groups are excluded. These are NOT 84,702 independent patients. Source weighting gives equal total mass to each cell identifier, each compound within a cell, and each experiment/range within that cell-compound pair. No biological-response clipping or cherry-picked drug list.

Use M_PTC / 100 (treated/control signal ratio), never M_GIPRCNT (growth corrected for starting cells). This unit conversion does NOT establish assay equivalence with the organoid viability endpoint. The HTS384 source uses established cell lines, 72-hour exposure and ATP luminescence. No NSC-to-DosePilot drug potency match is asserted. Relative log concentration is normalized to [0,1] within each five-point four-log source series. Linear interpolation between those five source positions is an assumed shape model, not additional measured source experiments.

The official NCI data index offers these public data to the scientific community. No archive-specific open-source license was found on the downloaded index, and the NCI text-reuse policy is not treated as a blanket dataset license. This work uses the source locally for scientific analysis. Do not redistribute the CSV or relabel it MIT/CC. Publish the retrieval path, hashes, parsing code and aggregate audit only; keep fitted source-dependent arrays local pending any later release-rights review. No NCI endorsement is claimed.

The project master/source registry and public commit history were searched for NCI-60/HTS384 prior use; none was found beyond the newly documented lead. Completeness of unpublished historical work is not asserted. No previously reserved external validation set is reassigned. Established NCI cell lines are distinct by study provenance from the Lib1 organoid donors, not a newly obtained independent confirmation set for DosePilot. No private clinical data or accounts are accessed.

## Fixed transfer construction
Compute the external weighted covariance of the five raw PTC-ratio values. For each DosePilot target, interpolate this covariance to that target's full normalized log-dose positions, then normalize it to a correlation matrix. This imports only relative curve dependence, NOT source response means, response variances, compound labels, potencies or outcomes for an evaluation patient.

Within each fitting organoid partition and target, decompose the historical paired plates into average curve mu=(p1+p2)/2 and contrast delta=(p1-p2)/2. Estimate means, covariance(mu), and covariance(delta) using equal-patient weights. Both the source and no-source arms assume mu and delta have zero cross-covariance; this is a modeling assumption, not a demonstrated biological property.

PRIMARY external arm: covariance(mu) is mixed 50/50 with the external correlation matrix rescaled by that fitting target's own per-dose standard deviations. CONTROL no-external arm: retain the empirical covariance(mu). In both arms, shrink the resulting mu covariance and the unchanged delta covariance 10% toward their diagonals and add 1e-6 to each diagonal. No strength/scale sweep or outcome-driven change. Recombine mu and delta into the full physical two-plate covariance, condition on only the selected physical cells, and map the conditional mean through the ORIGINAL exact AUC quadrature.

The original operating own-drug ridge is a separate reproduction control. Every base is followed by the unchanged bandwidth-0.7 cross-drug residual kernel. Within each arm, select one of the exact existing ten options (identity; fraction {0.1,0.3,0.6} x ridge {0.1,1,10}) by three fully rebuilt whole-patient inner folds. A separate single global choice is made for each arm. Both new arms are reported independently: no outer fold, target, orientation or arm splicing, and no post-outcome ensemble.

## Original task contract
Authenticated Lib1 TRAIN CSV only: 119 organoids, 59 whole patients, 24 unchanged normalized log-dose AUCs. The original R13 planner is rebuilt using fitting rows only in every inner/outer split. Exactly 64 distinct eligible native doses, 32 physical wells per plate per alternative A/B layout, with eight two-dose and sixteen three-dose outputs. No expansion from the original eligible 164 native positions to excluded historical nodes. All 416 historical TRAIN measurements are used only to fit training-patient distributions; at inference the same original 64 paid measurements are all that is available. Average A/B LOSSES, never their prediction vectors. No standard-control/genotype feature or extra resource.

Five original whole-patient outer folds. Every organoid mean, variance, covariance, plan, input scaling and residual fit excludes all organoids of the evaluated patient. External covariance is fixed independently and shared across all folds. No global outer OOF arrays are used for training. Saved operating and retained research predictions are comparators only.

## Gates and audit
The operating reproduction control must recover MSE 0.0010582750420801538 within 1e-12. Each new arm independently requires lower MSE, >=30/59 patient wins, 5/5 favorable outer folds and nonworse p90 versus BOTH operating and retained64 to qualify for a separate fresh end-to-end replay. Retain R13/R18 gates before any possible promotion. Half-error additionally requires the stated absolute target. No automatic promotion or Kaggle edit. Always finish and report all five folds irrespective of direction.

Prespecified descriptive patient bootstrap: 100000 draws, seed 202610080008. Intervals are selection-unadjusted because the same Lib1 population has been repeatedly inspected. No independent biological validation or clinical utility claim.

Synthetic tests check external covariance weights and interpolation, scale invariance, PSD preservation, no-external-arm invariance to changed source correlation, exact Gaussian conditional arithmetic, full-observation identity, patient weighting and malformed inputs. On real data poison all unpurchased queries; rebuild fold zero after altering its training-ineligible full curves, paid-feature source rows and labels while preserving the actual purchased query values. Saved states and predictions must be unchanged. Save numeric models and plans privately for independent Cholesky/kernel replay. Pin code, runtime, source and private-input hashes before fitting. Preserve failed runs; do not change settings after outcome.

## Primary sources checked 8 October 2026
NCI data index: https://dctd.cancer.gov/data-tools-biospecimens/data
Official HTS384 schema and download: https://wiki.nci.nih.gov/spaces/NCIDTPdata/pages/998965250/HTS384+Growth+Inhibition+Data
Kunkel et al., HTS384 NCI60: The Next Phase of the NCI60 Screen, Cancer Research (2024), DOI 10.1158/0008-5472.CAN-23-3031.
NCI text-reuse policy, not an asserted dataset-wide license: https://www.cancer.gov/policies/copyright-reuse
Official covariance shrinkage background: https://scikit-learn.org/stable/modules/covariance.html
Gaussian conditioning background: https://gaussianprocess.org/gpml/

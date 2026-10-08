# Exact-chemical, partially overlapping absolute-dose correlation prior

## What changed, and what did not
The just-completed generic external prototype model failed: MSE 0.0010729912368558343 versus retained64 0.001042745722096212. This trial is an explicitly adaptive follow-up, not a previously unseen holdout. The objective remains MSE <=0.000521372861048106, p90 <=0.037419695944064885, all 24 original targets, exactly 64 eligible treatment wells, 32 per plate. No achieved improvement is claimed.

A new public identity audit verified 20 of the 24 compounds against NCI NSC source substances via PubChem standardized CIDs. Synonyms alone were not enough: require a DTP.NCI substance/sourceid lookup returning exactly the requested standardized CID. Three names had no validated source match; TAS-102 remains a combination and is not replaced with an ingredient. The audit transmits public chemical names/IDs only, not any patient data.

The strict full-dose-span metadata check found ZERO targets with complete NCI concentration coverage: the external experiments generally use higher doses. A full-span drug-matched trial would therefore reproduce its generic fallback and was not run. This protocol explicitly tests PARTIAL coverage. It does not relabel extrapolated responses as measured data or loosen a failed model gate.

## Source-only bank, fixed rules
Use the already authenticated HTS384 source cache (84702 curves, 60 cell identifiers, 1135 compounds). M_PTC/100 is used, not M_GIPRCNT. NCI LCONC is log10 molar concentration, so DosePilot nM becomes log10(nM)-9. Matching a chemical and concentration does not establish assay equivalence or transferable potency.

For each chemically verified target, enumerate contiguous subsets of its full historical dose grid with at least two nodes. Retain subsets covered without extrapolation by source curves from at least 20 cell identifiers. Select the subset with the greatest node count; ties choose the lowest starting index. These are metadata/coverage criteria, not performance selection. Interpolate the selected source curves only within their measured five-dose ranges. Weight cell identifiers equally, then NSCs within each cell and experiments/ranges within cell/NSC. Estimate the correlation of these covered positions. Degenerate source variance uses the generic fallback. Unsupported compounds likewise use the fallback.

## Explicit completion assumption outside source support
Let Rg be the original pooled relative-dose correlation and Rs the chemically/dose-matched covered correlation. Set P=0.9*Rg+0.1*I and S=0.9*Rs+0.1*I. For covered indices C and uncovered U, use A=P[U,C] P[C,C]^-1 and D=P[U,U]-A P[C,U]. Assemble Q[C,C]=S, Q[U,C]=A S, Q[U,U]=D+A S A^T, and normalize its diagonal to one. The covered marginal is chemically informed; uncovered dependence comes from the declared pooled Gaussian conditional assumption. This is NOT observed external data in the uncovered region. The construction preserves positive definiteness and recovers P when Rs equals Rg[C,C]. The 0.1 regularization is fixed, not tuned.

CONTROL: P, the regularized pooled correlation. PRIMARY: Q, the partial chemically aligned completion. At unsupported targets they are exactly equal. This comparison isolates chemical/absolute-dose information from identical source-correlation regularization. The prior unregularized correlation trial is historical context, not asserted to be numerically identical to this new regularized control.

## Local fitting, acquisition and prediction
Reuse the existing paired-mean/plate-contrast Gaussian reconstruction: local fitting-only means, variances and contrast covariance; blend local mean-curve covariance 50/50 with the supplied correlation rescaled to local standard deviations; unchanged 10% diagonal shrinkage and 1e-6 floors. No external response mean, amplitude or biological potency is substituted for the local target.

Original R13 64-distinct-native-dose plan is rebuilt inside each fitting split. Both source arms use that same plan. The own-drug bandwidth-0.7 operating procedure is a separate reproduction control. Each arm chooses one global residual option from the original ten using three fully nested whole-patient inner folds, then refits on outer-training patients and scores the original five outer patient folds. No arm/target/orientation/fold splicing or post-outcome ensemble. The full 416 historical values are training-only; inference consumes only the same 64 eligible values. A/B LOSSES are averaged, never prediction vectors. No additional controls, genotype or Protected22/Lib2 response.

## Gates and verification
Each new arm separately needs lower mean MSE, >=30 patient wins, all 5 folds improved and nonworse p90 against BOTH retained64 and operating64 before eligibility for a separate fresh end-to-end replay. Preserve R13/R18 gates before any promotion. Half-error uses the absolute threshold above and retained p90. Automatic promotion and Kaggle edits are disabled. Report both arms regardless of outcome.

Freeze code, public-identity receipt, source-bank hashes and numerical versions before fitting. Tests verify nM/molar conversion, no-response-extrapolation selection, covariance completion identities, PSD preservation, unsupported-target identity, weighting, independent Gaussian prediction/state replay and outer-test isolation. Poison unpurchased inputs; rebuild outer fold zero after altering its training-ineligible curves/labels, preserving paid queries. Independently replay 15 numeric outer models and metrics. Bootstrap: 100000 whole-patient draws, seed 202610080050, descriptive and selection-unadjusted.

Raw source responses, patient arrays and learned source-dependent covariance arrays remain local. NCI scientific-use availability is not recast as MIT/CC licensing or NCI endorsement. All Lib1 outcomes remain repeatedly inspected adaptive development, not independent biological validation.

## Primary documentation
NCI official HTS384 schema, including log10-molar LCONC and treated/control PTC: https://wiki.nci.nih.gov/spaces/NCIDTPdata/pages/998965250/HTS384+Growth+Inhibition+Data
PubChem documented source-substance/CID and synonym APIs: https://pubchem.ncbi.nlm.nih.gov/docs/pug-rest
Gaussian conditioning background: https://gaussianprocess.org/gpml/

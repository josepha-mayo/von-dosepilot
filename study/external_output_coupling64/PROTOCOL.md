# Externally fixed cross-drug output covariance, 64 wells

## Hypothesis and prior failures
The external shape-correlation and nonlinear prototype trials failed; the chemically aligned partial-dose prior also failed (MSE 0.0010612090565783913). Those trials transferred dependence between doses WITHIN each drug. This trial instead asks whether how the SAME external cell lines respond to DIFFERENT verified drugs supplies useful output-task relationships. It is an explicitly adaptive follow-up, not a new independent validation population or a parameter retest of the failed within-drug model.

The numerical objective remains MSE <=0.000521372861048106, with p90 <=0.037419695944064885, all 24 original outputs, exactly 64 purchased eligible wells (32/32). No improvement is claimed by finding source matches.

## Source-only cross-drug prior
Reuse the audited NCI HTS384 curves and exact PubChem/NSC chemical mappings. For each of the 20 verified compounds, use precisely its covered absolute-concentration interval from the frozen metadata rule. Compute the trapezoidal mean treated/control response over that interval from each source five-dose curve, without extrapolation. Within a cell/compound, average available experiment/range summaries equally; average NSCs only when exact standardized chemical identity was separately verified. The four unmatched outputs remain independent in the prior. TAS-102 is not replaced by an ingredient.

Use only the common cell-line intersection with measured summaries for all 20 drugs. No response imputation or response-based exclusion. Require at least 20 common cell identifiers before starting the model trial. The source-only audit found 33 such cells. These are 33 established cell lines, not organoid donors or independent clinical validation cases. Interpolate only inside measured dose ranges; intervals can differ by drug and are NOT asserted equal to the original organoid AUC intervals.

Calculate the 20x20 Pearson correlation across the common source cells and shrink it 50% to the identity. Embed it into a 24x24 matrix C, with unit diagonal and zero off-diagonal links for unmatched outputs. Source response means and variance scales are not imported. The matrix is fixed once from external data. Assay/domain differences and the fact that FULL-response correlation need not equal residual correlation are explicit risks, not erased by exact compound matching.

## Predictor and matched control
Fit the original own-drug ridge base at lambda0.01 using the original R13 64-well acquisition. Its selected doses, normalization and fitting all exclude the evaluation patient. Fit the same bandwidth0.7 additive input kernel on the residuals. The PRIMARY residual model uses the separable task covariance K_input(x,x') * C[j,k]. The CONTROL uses C=I with the exact same objective. Each arm offers identity/no correction plus kernel penalties {0.1,1,10}, selected by three whole-patient inner folds independently per arm. No output-specific choices or learned weights from outer OOF arrays.

For weighted kernel eigendecomposition sqrt(W)Ksqrt(W)=U diag(e) U^T and C=V diag(c) V^T, coefficients are sqrt(W) U [(U^T sqrt(W) residual V)/(e_i+lambda/c_j)] V^T. This is an established matrix-valued kernel/ridge construction. The independent control reduces to ordinary weighted scalar-output KRR. With noise-free block designs and vanishing regularization, cross-task transfer can cancel; this study therefore tests a finite-regularization prior, not a universal advantage from correlated outputs.

The existing ten-option spectral bandwidth0.7 procedure is a third, separately regenerated OPERATING reference. It must match 0.0010582750420801538 within1e-12. It is not an automatic fallback used to select which outer results to publish. The source prior, independent control and reference are all reported.

## Validation, invariants and gates
119 Lib1 samples, 59 whole patients, original five outer folds. Rebuild planner, base model, scaling, kernel and residual option selection entirely inside all fitting splits. No Protected22/Lib2, new controls, genotype, patient identity or extra treatment observations at inference. A and B are separate physical layouts; average losses, never their prediction vectors.

An arm must beat BOTH retained64 and operating64 on MSE, >=30 patient wins, all5 favorable folds and p90 before eligibility for a separate fresh end-to-end replay; preserve R13/R18 gates before promotion. Half-error requires the absolute objective above. No automatic model or submission replacement. Bootstrap100000 whole-patient draws, seed202610080106, descriptive and selection-unadjusted.

Synthetic tests compare the eigen-solver against an independent full Kronecker solve, check C=I equivalence, output permutation covariance, zero residuals, invalid matrices, source units/weighting and complete-case source assembly. Save numeric outer models, independently replay predictions and all metrics, and check outerfold0 label/curve mutation plus unpurchased-query poisoning. Freeze all source/code hashes and versions before outcomes. No outcome-driven retries.

Raw source arrays, cell-line response matrices and learned source covariance arrays remain local pending separate release-rights review. NCI scientific-use availability is not relabelled MIT/CC or endorsement. All local performance remains repeated adaptive Lib1 development, not independent biological validation.

## Primary references
Bonilla, Chai and Williams, Multi-task Gaussian Process Prediction, NeurIPS2007: https://papers.neurips.cc/paper_files/paper/2007/hash/66368270ffd51418ec58bd793f2d9b1b-Abstract.html
Official multi-output kernel documentation: https://gpflow.github.io/GPflow/2.9.0/notebooks/advanced/multioutput.html
Official source schema: https://wiki.nci.nih.gov/spaces/NCIDTPdata/pages/998965250/HTS384+Growth+Inhibition+Data
PubChem source-substance mapping: https://pubchem.ncbi.nlm.nih.gov/docs/pug-rest

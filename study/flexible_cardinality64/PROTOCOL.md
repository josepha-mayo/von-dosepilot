# Flexible cardinality under the unchanged 64-treatment budget

## Purpose
Seek a structural gain by changing what is measured, rather than tuning another kernel parameter. The current allocator forces every drug to receive two or three doses, with exactly sixteen third-dose upgrades. This study allows fitting-only allocation of one to six or two to six native doses per drug, while keeping 64 distinct treatment wells, 32 per source plate, all 24 outputs and the original patient population. It changes the acquisition policy, not the total budget or target denominator.

Prior work checked: the latent_curve_quadrature experiment at cd4fba0 still required eight two-dose/sixteen three-dose groups and fitted a PPCA quadrature model. The seven-point budget curve changed total wells by buying additional third doses. The paired-noise and output-whitening studies change noise modelling. None of those is this fixed-total-budget multiple-choice cardinality allocation. This is an application of optimal experimental design and dynamic programming, not a claim of a new optimization algorithm. Background: Krause, Singh and Guestrin, JMLR 9, 2008, https://jmlr.org/papers/v9/krause08a.html . The present objective is not their mutual-information objective and inherits no submodularity guarantee from that paper.

## Frozen models
Three allocation policies, each crossed with the same ten existing bandwidth-0.7 residual options, total 30 choices:
1. Unmodified incumbent R13 two/three-dose allocation.
2. Best fitting-only subset at each cardinality 2..min(6, available native doses), then exact dynamic programming chooses cardinalities summing to 64.
3. Same, allowing cardinalities 1..min(6, available native doses).

For each target/cardinality enumerate all native subsets. Use the incumbent standardized patient-weighted ridge posterior-variance surrogate with allocation alpha 0.1, symmetric historical A/B augmentation, and lexicographic native-id ties. Optimize the sum of 24 target surrogates subject to exactly 64 chosen native doses. A target never disappears. For odd-sized groups alternate their starting source plate in target-id order; even groups start on p1. Since 64 is even the number of odd groups is even, giving 32 p1 and 32 p2 measurements. Alternative B is the exact plate complement. No A/B prediction averaging.

The predictor remains own-drug ridge at 0.01 plus the same global-linear/within-drug-Gaussian additive residual kernel with bandwidth 0.7. Kernel group sizes follow actual purchased cardinality, never an unseen feature. Output spectral fraction options {0.1,0.3,0.6} crossed with residual ridge {0.1,1,10}, plus identity. No new continuous tuning, no target-specific residual option selection.

## Evaluation
119 Lib1 samples, 59 whole patients, 24 fixed log-dose AUC targets. Original five outer and three inner whole-patient folds. Allocation, standardization, kernels and selection are rebuilt inside each fitting partition. Select one global allocation/residual option by patient-balanced inner OOF MSE. Earliest index wins numerical ties. Evaluate all outer patients exactly once with the selected rule. Saved global OOF predictions are comparators only, never meta-training inputs.

Incumbent replay must recover MSE 0.0010582750420801538 within 1e-12. The retained 64-well scientific candidate remains 0.001042745722096212, p90 0.037419695944064885. Eligibility for a further replay requires lower MSE, >=30/59 patient wins, all five folds improved and p90 nonworse versus BOTH references. Half-error target is 0.000521372861048106, explicitly an aspirational target, not a promised result. Bootstrap 100000 whole-patient draws, seed 202610071213, descriptive and selection-unadjusted. No automatic promotion or entry update.

## Integrity
Synthetic tests cover dynamic programming against brute force, infeasibility, parity/physical budget, target ownership, kernel PSD, incumbent-kernel equivalence, and nonfinite inputs. Real-data checks poison unpurchased values and perturb only held-out fold 0 labels before rebuilding that fold. Freeze code, protocol and input hashes before candidate outcomes. Save fold selections, patient-isolated predictions, environment, aggregate results and rejected cases. Private arrays stay on D:. No Protected22/Lib2, clinical claim, or independent-validation claim.

A separate post-hoc diagnostic of the already-seen incumbent error distribution motivated investigating acquisition: the worst six targets account for 34.34% of error, so a gain cannot be manufactured by fixing only one target. Historical plate AUC disagreement is recorded as a noise proxy, not an irreducible bound. This entire study is adaptive development on previously inspected Lib1 data.

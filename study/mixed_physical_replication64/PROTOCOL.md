# Mixed replication versus dose diversity at 64 physical treatment wells

## Explicit task-design distinction
The user goal remains a genuine halving of prediction error at the same measurement budget. This study holds the 64 PHYSICAL treatment wells, 32 per plate, the original eligible dose universe, all 24 original endpoints, and the same patients fixed. Unlike the retained single-well policy it permits a target to buy the SAME native dose on both source plates, paying for both cells. Therefore it can use fewer than 64 distinct native concentrations. This is a disclosed acquisition-design extension, not an assertion that the original 64-distinct-native-dose validator has passed. No original validator or reference plan is modified, and no automatic submission/model replacement is permitted.

Earlier R9 and the matched paired-native control bought all measurements as pairs and were worse than R13; they are NOT new baselines invented here. This study differs by allowing a selective mixture of replication and diversity with 2/3 physical cells per target. A matched distinct-native physical-design arm separates free plate-pattern choice from native replication. A completed-commit search found no prior mixed same-budget physical subset planner, but unpublished historical completeness is not asserted.

## Fixed planner
For each FITTING partition and each target, use the existing equal-patient, half-A/B covariance surrogate with planning ridge 0.1 and input scale floor 0.05. Each original patient has equal total weight, divided over its organoids and the two alternative views. For a size-2 physical subset require one cell from each plate. For a size-3 subset require two p1 cells and one p2 cell before the declared complementary flip. Never select the same (native dose,plate) cell twice.

Enumerate every eligible physical subset satisfying those counts, score Cyy-Cxy[S]^T(Cxx[S,S]+0.1I)^-1 Cxy[S], and choose the best size-2 and size-3 subsets. Lexicographic physical-coordinate order breaks exact ties. Upgrade exactly sixteen targets by their largest fitting-only proxy reduction. Flip the orientation start for every second upgraded target in target-ID order, yielding exactly 32 cells from each plate. The other eight targets receive two physical cells each. B complements A at every slot. Technical replicates are paid observations, not independent patients.

Separately evaluate three arms:
1. ORIGINAL benchmark: unmodified R13 planner and bandwidth-0.7 predictor.
2. DISTINCT-PHYSICAL control: the above balanced physical enumeration, but require distinct native doses within every target.
3. MIXED-REPLICATION primary: the same enumeration with same-native cross-plate pairs permitted.

All arms use 64 individual raw observations, own-drug ridge 0.01, and the unchanged bandwidth-0.7 additive residual family. For each arm select one global residual option from the existing ten options: identity, or spectral fraction {0.1,0.3,0.6} crossed with ridge {0.1,1,10}. Do not select between arms or splice predictions after observing outer errors. The planning proxy is a regularized training criterion, not a proven test-risk estimate.

## Evaluation
Authenticated Lib1 TRAIN only: 119 organoids, 59 whole patients, 24 raw normalized log-dose AUCs. Five original outer patient folds, three regenerated inner patient folds. Acquisition, scaling, predictor and residual selection are rebuilt inside each fitting partition, excluding all rows from the held patient. No outer OOF result becomes training data. No new controls, genotype, clinical outcomes, excluded native concentrations, protected/Lib2 responses or external measurements. A/B prediction vectors are never averaged; average their separately costed losses only.

ORIGINAL must reproduce operating MSE 0.0010582750420801538 within 1e-12. Scientific comparator remains 0.001042745722096212 and p90 0.037419695944064885. A same-physical-budget gain requires strictly lower MSE, at least 30 patient wins, all five folds improved, and nonworse p90 versus both comparators. Half-error is separately MSE <=0.000521372861048106 with retained p90 nonworse. Any replication result remains a new design needing explicit contract review plus independent fresh replay and all R13/R18 gates, not automatic promotion under the old distinct-native contract.

Descriptive whole-patient bootstrap: 100000 draws, seed 202610072250. The data remain repeatedly inspected adaptive development, not independent biological validation or selection-adjusted inference. Complete all five folds and report all arms, no outcome-driven parameter retries.

## Integrity
Synthetic tests compare batched proxy calculations with explicit weighted refits, verify candidate enumeration is complete, paid cell uniqueness even when native IDs repeat, exact 64/32/32 accounting, per-target counts, missing-input rejection and patient weighting. Recompute saved numeric models independently. Poison every unpurchased query cell. Rebuild fold zero after altering only its training-ineligible labels and measurements, using the original query values; fitted states and predictions must be invariant. Record every selected native repetition and source plate. Hash sources and inputs before the first candidate outcome.

## Primary references checked 7 October 2026
Binois, Huang, Gramacy and Ludkovski, Replication or Exploration? Sequential Design for Stochastic Simulation Experiments, Technometrics 61(1), 2019, DOI 10.1080/00401706.2018.1469433; https://arxiv.org/abs/1710.03206 . Their results motivate assessing replication in noisy design but do not establish benefit for organoid assays or this particular planner.
Holland-Letz and Kopp-Schneider, Optimal experimental designs for dose-response studies with continuous endpoints, Archives of Toxicology, DOI 10.1007/s00204-014-1335-2. Different dose levels and replication weights are established experimental-design variables. This project does not claim an original optimal-design theorem or a proven optimal 64-well panel.

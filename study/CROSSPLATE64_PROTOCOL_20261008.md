# Cross-plate matched-dose allocation at fixed 64 physical wells
# Frozen study proposal, 8 October 2026

## Hypothesis
Current 64-well complementary plate design gives 64 distinct native concentrations, but the target is an equal mean of two fully measured plate AUCs. The one-plate complete-curve oracle diagnostic gives equal-patient MSE 0.0007521757809186084, which exceeds the desired 0.000521372861048106. This is evidence of plate variability, **not** a universal lower bound. A small amount of *cross-plate replication at the same dose* might reduce noise more than the information lost from fewer distinct doses.

## Three prespecified measurement arms
- **k=0:** existing 64 distinct native doses, 32/32 plates.
- **k=4:** 60 distinct native doses, four paired concentrations across plates, 64 physical wells, 32/32 plates.
- **k=8:** 56 distinct native doses, eight paired concentrations across plates, 64 physical wells, 32/32 plates.

Start with the fitting-only R13 best 2/3-dose, 64-well plan. For each 3-dose target, an alternative duplicates its unique minority-plate native concentration on the opposite majority plate by replacing one of the original two majority-plate concentrations. Fitting rows only select which 3-dose targets and which majority-plate dose to forgo using regularized own-target covariance proxy, evaluating both A/B layouts. No other physical slots change, the 24 target identities are unchanged, every per-plate coordinate is unique, and all candidate measurements are from authorized Lib1 TRAIN native observations. The original 64-distinct-dose coverage requirement intentionally changes, even though cost and plate counts do not. That trade-off is disclosed and must receive separate study review.

## Predictor and evaluation
For each measurement arm, use unchanged own-drug ridge 0.01, standardized 64-coordinate input, and 0.7-bandwidth additive drug-group residual kernel with exactly 10 existing spectral options. Select one spectral option for each arm in 3 inner whole-patient folds inside each of 5 outer whole-patient folds. Replan the physical layout, fit ridge/kernel, and choose parameters solely on fitting patients. Score the unchanged 24 raw log-dose AUC targets on the held patients, with equal patient/target weighting. A/B are two **alternative** deployments; average their squared losses, never the predictions, and never use the union of either layout at inference.

Compare k=4 and k=8 to k=0 regenerated controls, the operating 64-well bandwidth0.7 reference MSE 0.0010582750420801538, and the retained best scientific 64-well reference MSE 0.001042745722096212. Report patient wins, fold wins, p90, and orientation scores. "2x better" requires MSE <= 0.000521372861048106 **and** nonworse p90.

No Protected22, Lib2, new downloaded responses, target/fold cherry-picking, same-budget averaging or Kaggle submission modification. All evaluation is repeated adaptive development on 119 samples / 59 patients. Entire result is quarantined from shared master until scientifically verified. Rejected results remain documented.

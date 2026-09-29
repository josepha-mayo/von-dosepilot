# Method and evidence boundary

The retained procedure is R13. Within each training split, a covariance criterion selects two source-native doses for all 24 drugs and sixteen third-dose upgrades, at alpha=0.1. Two complementary assignments each use 64 physical treatment wells and 32 wells per plate. A response-independent layout choice avoids selecting the more favorable outcome after measurement.

Each head uses only its own drug's two or three measured feature values, across many patient/sample training rows. The predictors are not curves fitted from just two training observations. One common ridge penalty from 0.01, 0.1, 1 and 10 is selected inside three inner whole-patient folds; five outer whole-patient folds provide the development comparison. Fitting means/scales and acquisition stay within fitting splits. Intercepts are unpenalized. Scales have the original 0.05 floor.

The endpoint is the original unclipped discrete normalized log-dose trapezoid, averaged across the two source plates. Purchased values can contribute to that target. This is reconstruction of a measured summary, not proof of recovery of noiseless biological truth. Expected-layout scoring averages A/B LOSSES, not predictions.

The original independent attempt failed during import before scoring. Protected records were not removed and the failed result was not repaired. Cross-library dose and target-support limitations remain. The prototype is research-only and makes no clinical or realized-cost claim.

The core claims and primary references are detailed in the separately staged technical report. Precedents include response-profile learning (10.1093/bioinformatics/btag293), Xi et al. (2018), https://proceedings.mlr.press/v80/xi18a.html , and Longi et al. (2020), https://proceedings.mlr.press/v124/longi20a.html . These motivate existing concepts, not a head-to-head comparison or invention of ridge regression/Gaussian conditioning.

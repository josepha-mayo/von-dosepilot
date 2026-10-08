# von DosePilot: measured accuracy gain and remaining 64-well gap

**Result:** The new 128-well research tier scores 0.0005102658031862283 MSE, a 2.0435-fold reduction versus the retained 64-well MSE 0.001042745722096212. It requires 128, not 64, treatment wells. **The original same-budget 2x goal remains unmet.**

## Cost and accuracy

| Procedure | Treatment wells | Added wells vs64 | Patient-balanced MSE | p90 patient RMSE | MSE reduction factor vs retained 64 |
|---|---:|---:|---:|---:|---:|
| Retained scientific model |64|0|0.001042745722|0.037419696|1.000x|
| New research tier |80|16|0.000832125987|0.035733567|1.2531x|
| New research tier |96|32|0.000690967423|0.031992347|1.5091x|
| New research tier |112|48|0.000582520011|0.029874389|1.7901x|
| New research tier |128|64|0.000510265803|0.028122766|2.0435x|

The 128-well tier improves 59/59 patient-average errors, 5/5 outer-fold errors and 24/24 target-average errors relative to retained 64. This does not mean every individual sample-target prediction improves. Against the recorded 72-well research MSE 0.0009326007417880046, the 128-well tier is 1.8277x, not 2x. These are different measurement budgets.

The 2.0435x ratio is a development point estimate. A descriptive, selection-unadjusted whole-patient bootstrap gives 95% interval [1.9368,2.1600]. This is not independent confirmation of a 2x generalization claim.

All comparisons preserve 119 Lib1 samples, 59 whole patients, 24 original raw AUCs and patient-separated model selection. A/B are scored as alternative measured layouts; their prediction vectors are never combined into a free ensemble. The 128-well tier uses 64 wells from each source plate. Treatment counts do not establish monetary, material or elapsed-time savings.

## Same-budget attempts and protection of the incumbent

The finite-AUC anchored/smooth-prior trial and cross-fitted richer-teacher-to 64-well-student trial were fully run and rejected. Their primary MSEs were 0.001058106984 and 0.001059005279, respectively. Neither replaced the retained 64 model or changed the Kaggle entry.

## Verification and runnable artifact

Independent saved-model checks reconstructed 34,272 finite-AUC predictions, 28,560 cost-tier predictions and 28,560 student predictions, each with maximum difference 2.22e-16. Whole-patient weighting, physical budgets and excluded-patient mutation checks passed. Teacher fitting/soft-label groups were audited for nested separation. These are numerical integrity checks, not independent biological validation.

A separately named all-training 128-well research model is saved privately at:

`D:\von-dosepilot-data\accuracy_tiers_20261008_run1\deployment128_private`

Its source inference CLI is `study/predict_research_tier.py`. The model uses the predeclared mode of outer training-selected spectral options: fraction 0.1, kernel ridge10. A fictional-data smoke test and valid A/valid B, missing, 64-only, duplicate, unpurchased, nonfinite and wrong-layout checks passed. The model refuses incomplete inputs instead of silently pretending 128 measurements cost 64. Model arrays contain training coordinates and must not be published as aggregate-only evidence.

The private model is research-only, not clinically validated. All-training fitting is not another validation result. The retained 64 model, public submission and original scientific score remain unchanged.

## Frozen sources

- Finite-AUC experiment: a4e9899; D:/von-dosepilot-finite-auc64-20261008.
- Accuracy tiers: fa5b154; D:/von-dosepilot-accuracy-tiers-20261008.
- Privileged student:18ff3e2; D:/von-dosepilot-privileged-student64-20261008.

Private128 model SHA256: `4026a4b2c74975713b9c465000a9793243b08a932cb9d968da6e110344172e37`.

The companion aggregate JSON contains precise metrics, experiment paths, result hashes and verification receipts. No individual assay responses or trained kernel-coordinate arrays are included in that JSON.

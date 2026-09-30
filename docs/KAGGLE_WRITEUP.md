**Submission category: Model & Algorithm**

# von DosePilot: 24 response summaries from 64 traceable wells

**Measurement-aware drug-screen reconstruction under a fixed treatment-well budget.**

**Team:** von DosePilot  
**Author:** Joseph Ayanda

## Project Summary

DosePilot addresses a practical bottleneck in dose-response experiments: when treatment wells are limited, should the assay repeat measurements for precision or spend those wells on broader dose coverage? The project treats that choice as part of the predictive method rather than as an invisible preprocessing decision.

On a retrospective colorectal-cancer organoid task, DosePilot reconstructs 24 fixed drug-response summaries from exactly 64 identified treatment wells. The complete selected source curves contain **416 eligible target-treatment measurements per sample (208 per plate)**, so the evaluated 64-well policy uses **15.38% of that treatment-measurement count, an 84.62% reduction**. This is a retrospective measurement-budget comparison, not a measured 84.62% reduction in money, materials, or elapsed laboratory time. Acquisition planning, scaling and model selection stay inside whole-patient training folds. The retained R13 procedure uses broader dose coverage and 24 drug-specific sparse prediction heads. It achieved patient-balanced MSE **0.0011448587**, 33.49% lower than an earlier paired-well procedure and 34.13% lower than a matched paired-native control. A separately optimized interpolation acquisition policy reached **0.0024168103**, while R13 was 52.63% lower and improved all 59 patient means in that comparison.

DosePilot also turns the research method into an inspectable workflow: it binds every required value to a sample, run, drug, concentration, plate and physical well; rejects incompatible inventories; abstains when required inputs are missing; and recovers the same committed acquisition plan after an export failure. The complete historical R9/R13 result can now be reproduced from the exact public source workbook without the old private input bundle. The evidence remains retrospective development on conventional organoid plates, not prospective organ-on-chip or clinical validation.

## Why it matters

Sparse drug screens force a practical choice: spend another well repeating a measurement, or use that well to cover another concentration. DosePilot makes that tradeoff explicit and carries the chosen measurement identities all the way from inventory to prediction.

The system checks sample, drug, concentration, plate and physical-well identity, commits one 64-well layout before responses are supplied, and returns 24 drug-response summaries when the required measurements are complete. Missing measurements remain visible, incompatible concentrations are rejected, and an interrupted export can recover the same committed plan instead of selecting a new one.

## Main result

We evaluated DosePilot retrospectively on **119 patient-derived organoid samples from 59 patients**, predicting **24 fixed drug-response summaries** under the same **64-treatment-well budget**.

The retained broader-coverage procedure achieved patient-balanced MSE **0.0011448587**, compared with **0.0017214230** for our earlier paired-measurement procedure: a **33.49% reduction**. **53 of 59 patients** and **all five outer-fold averages** improved. A matched paired-native control was also worse at the same well count.

A stricter post-submission control separately optimized a piecewise-linear log-dose interpolation acquisition policy under the same 64-treatment-well budget. Its patient-balanced MSE was **0.0024168103**; R13 was **52.63% lower**, with lower patient-mean error for **59/59 patients** and lower mean error in **5/5 outer folds**. This is another comparison on the repeatedly reused development cohort, not independent confirmation.

### Separate external CRC confirmation

We then froze a new sparse-reconstruction task on an **independent public metastatic-CRC organoid study** before accessing its FORECAST-1 confirmation responses. The model/design was fitted only on the study's community cohort. The external task used eight single agents and a fixed **21-measurement** budget: two concentrations for every drug plus five third-dose upgrades. A piecewise-linear interpolation comparator optimized its own acquisition policy under the identical measurement count.

The prefrozen complete-case rule retained 13 of 19 FORECAST-1 PDTO lines. On those 13 distinct patients, learned sparse reconstruction reached patient-balanced MSE **0.0021715** versus **0.0038552** for optimized interpolation, **43.67% lower**. It improved **10/13 patient means**, was nonworse on **7/8 target MSEs**, and improved the five-drug subset shared with the original DosePilot development task. The prespecified paired-patient bootstrap interval for learned-minus-interpolation MSE was **[-0.002809, -0.000581]**.

We also froze a deliberately strict four-part support gate before opening FORECAST-1. Three parts passed, but the gate as a whole **failed** because it required at least 12 strict patient wins out of the original 19 source patients; six source lines were incomplete and the learned procedure won 10 of the 13 complete patients. We did not relax the gate after seeing the result. This experiment supports transfer of the sparse acquisition/reconstruction **design pattern**, not direct validation of the original fitted 24-drug R13 heads or a clinical claim. Full protocol, source identities and aggregate audit are in `docs/EXTERNAL_CRC_CONFIRMATION.md` and `evidence/external_crc_confirmation_20260930.json`.

## Practical value and organ-on-chip path

The immediate value is experimental decision support under a hard measurement budget: DosePilot makes the acquisition policy explicit, auditable and executable before response values enter the workflow. That matters whenever dose-response experiments cannot measure every desirable concentration or replicate.

For organ-on-chip work, the same software pattern can support dose-response planning and measurement provenance, but the present evidence does **not** validate microfluidic devices. A real OoC deployment must first encode channel topology, shared-flow coupling, tissue dependence, device-level replication and any different dose-support constraints, then evaluate the complete acquisition-and-prediction procedure prospectively. DosePilot exposes that boundary rather than treating ordinary organoid-plate evidence as chip validation.

## What is technically distinctive

DosePilot combines:
- explicit physical-well accounting instead of abstract feature counts;
- patient-contained acquisition planning, scaling and model selection;
- 24 block-sparse drug-specific prediction heads;
- strict measurement identity checks at runtime;
- explicit abstention when required values are missing;
- recovery of an already committed layout after export failure;
- a dose-aware operator prototype that exposes unsupported concentration/target requests instead of silently substituting measurements.

## Reliability and evidence boundary

The main result is intentionally not presented as a universal win. R13 is repeated adaptive development evidence; six drug-average errors and six patient averages regress versus R9. Later challengers, including nonlinear heads, alternative allocation rules, per-target regularization, calibration and cross-drug context, were retained as negative results when they failed promotion. The original independent Lib2 attempt failed before scoring, and the remaining protected cohort has not been reopened.

The public source-to-results replay verifies reproducibility of the historical result, not independence. The separate Tan et al. FORECAST-1 experiment adds an external patient cohort for a newly frozen eight-drug sparse-reconstruction task, but its prespecified four-part support gate did not fully pass and it does not directly validate the original 24 fitted heads. No clinical effectiveness, calibrated uncertainty, realized reagent savings or prospective OoC performance is claimed.

## Public assets

**Code:** https://github.com/josepha-mayo/von-dosepilot

**Technical report PDF:** https://github.com/josepha-mayo/von-dosepilot/blob/master/docs/DosePilot_Technical_Report_Public.pdf

**Demo video:** https://youtu.be/QeOGJIgx378

Run the demo:

```bash
python -m pip install -r requirements.txt
python run_demo.py --output demo_run_001
```

The operating demo uses fictional measurements and model parameters while exercising the same workflow behaviors.

## Reproducibility

The historical source workbook is now pinned to an exact public artifact: Mendeley Data v3 `Data S4.xlsx` is listed at **15,886,254 bytes** with SHA-256 `3847aa93b2a84c7d5d0b04c26494f39f35963fc41e96eae97d8a180fbc33d81c`, exactly matching DosePilot's frozen source identity. The dataset is listed as CC BY 4.0. `python study/acquire_public_source.py --check-only` verifies that live metadata anonymously, and the acquisition path has downloaded the same exact bytes locally.

The public source-to-results route is now executable without the old private input bundle. `study/prepare_compact_source.py` reconstructs the exact 49,504-row Lib1 TRAIN curve CSV from the verified public workbook using a patient-free fixed catalog; `study/reproduce_compact.py` then rebuilds the historical models and predictions in a fresh environment. All four locked R9/R13 metrics matched within absolute MSE tolerance `1e-12`. Full commands and receipts are in `docs/PUBLIC_REPRODUCTION.md` and `evidence/r33_public_pipeline.json`. This is reproducibility of retrospective development results, **not independent validation or a new biological score**.

## AI assistance

ChatGPT assisted with research synthesis, implementation, numerical checking, documentation, and release preparation. Focused OpenCode reviews used Muse Spark 1.3 in later verified sessions. The DosePilot runtime itself uses no language-model API.

## Primary references

1. Kryeziu et al., *Cell Reports Medicine* (2026), DOI: 10.1016/j.xcrm.2026.102840.
2. Abdel-Rehim et al., *Bioinformatics* (2026), DOI: 10.1093/bioinformatics/btag293.
3. Xi, Briol & Girolami, Bayesian Quadrature for Multiple Related Integrals, PMLR 80 (2018).
4. Longi et al., Sensor Placement for Spatial Gaussian Processes with Integral Observations, PMLR 124 (2020).
5. Tan et al., *Cell Reports Medicine* (2023), DOI: 10.1016/j.xcrm.2023.101335. Separate external CRC organoid cohort used only for the frozen post-submission sparse-reconstruction confirmation described above.

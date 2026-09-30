**Submission category: Model & Algorithm**

# von DosePilot: 24 response summaries from 64 traceable wells

**Measurement-aware drug-screen reconstruction under a fixed treatment-well budget.**

**Team:** von DosePilot  
**Author:** Joseph Ayanda

## Why it matters

Sparse drug screens force a practical choice: spend another well repeating a measurement, or use that well to cover another concentration. DosePilot makes that tradeoff explicit and carries the chosen measurement identities all the way from inventory to prediction.

The system checks sample, drug, concentration, plate and physical-well identity, commits one 64-well layout before responses are supplied, and returns 24 drug-response summaries when the required measurements are complete. Missing measurements remain visible, incompatible concentrations are rejected, and an interrupted export can recover the same committed plan instead of selecting a new one.

## Main result

We evaluated DosePilot retrospectively on **119 patient-derived organoid samples from 59 patients**, predicting **24 fixed drug-response summaries** under the same **64-treatment-well budget**.

The retained broader-coverage procedure achieved patient-balanced MSE **0.0011448587**, compared with **0.0017214230** for our earlier paired-measurement procedure: a **33.49% reduction**. **53 of 59 patients** and **all five outer-fold averages** improved. A matched paired-native control was also worse at the same well count.

A stricter post-submission control separately optimized a piecewise-linear log-dose interpolation acquisition policy under the same 64-treatment-well budget. Its patient-balanced MSE was **0.0024168103**; R13 was **52.63% lower**, with lower patient-mean error for **59/59 patients** and lower mean error in **5/5 outer folds**. This is another comparison on the repeatedly reused development cohort, not independent confirmation.

## What is technically distinctive

DosePilot combines:
- explicit physical-well accounting instead of abstract feature counts;
- patient-contained acquisition planning, scaling and model selection;
- 24 block-sparse drug-specific prediction heads;
- strict measurement identity checks at runtime;
- explicit abstention when required values are missing;
- recovery of an already committed layout after export failure;
- a dose-aware operator prototype that exposes unsupported concentration/target requests instead of silently substituting measurements.

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

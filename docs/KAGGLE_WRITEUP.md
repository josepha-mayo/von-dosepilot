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

**Technical report:** https://github.com/josepha-mayo/von-dosepilot/blob/master/docs/DosePilot_Technical_Report.md

**Demo video:** https://youtu.be/QeOGJIgx378

Run the demo:

```bash
python -m pip install -r requirements.txt
python run_demo.py --output demo_run_001
```

The operating demo uses fictional measurements and model parameters while exercising the same workflow behaviors.

## AI assistance

ChatGPT assisted with research synthesis, implementation, numerical checking, documentation, and release preparation. Focused OpenCode reviews used Muse Spark 1.3 in later verified sessions. The DosePilot runtime itself uses no language-model API.

## Primary references

1. Kryeziu et al., *Cell Reports Medicine* (2026), DOI: 10.1016/j.xcrm.2026.102840.
2. Abdel-Rehim et al., *Bioinformatics* (2026), DOI: 10.1093/bioinformatics/btag293.
3. Xi, Briol & Girolami, Bayesian Quadrature for Multiple Related Integrals, PMLR 80 (2018).
4. Longi et al., Sensor Placement for Spatial Gaussian Processes with Integral Observations, PMLR 124 (2020).

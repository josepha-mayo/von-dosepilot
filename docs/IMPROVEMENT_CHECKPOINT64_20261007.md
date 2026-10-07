# DosePilot 64-well improvement checkpoint, 7 October 2026

Two distinct model hypotheses were completed on JOSEPH-DESKTOP, with project files on D:. Both keep the original 64-treatment-well budget (32 per plate) and all 24 outputs. Neither changes the accepted Kaggle entry, the operating model, or the retained research candidate.

## Results

| Procedure | Patient-balanced development MSE | p90 patient RMSE | Decision |
|---|---:|---:|---|
| Operating bandwidth-0.7 baseline | 0.001058275042 | 0.037894285309 | Unchanged |
| Retained 64-well research candidate | 0.001042745722 | 0.037419695944 | Unchanged |
| Joint own-drug/kernel fitting menu | 0.001058275042 | 0.037894285309 | Rejected |
| Plate-contrast output whitening menu | 0.001057685406 | 0.037870616427 | Rejected |

Joint fitting's seven synthetic tests establish equivalence with an independent summed-kernel solve, valid normal equations, and nonworse penalized training objective. But all five inner selections preferred an existing sequential option, so there was no held-patient improvement.

Output whitening uses only historical fitting-patient plate AUC contrasts to regularize the shared response modes. It is distinct from input-coordinate paired-noise conditioning. Seven synthetic tests passed. MSE was 0.0557% lower than the operating baseline, with 26/59 patient wins and 2/5 improved folds, but it did not beat the retained research candidate. Its descriptive interval against the operating baseline crosses zero. It is not a promoted submission improvement.

## Integrity

The two protocols and code were committed before their respective outcome runs: joint fitting at 6bab05bb2ff03ae2d69705aa92899ed191571b2e, output whitening at f7fd6c9ee9f09fda38acc080b615fdd95edb0d9d. Source bytes were checked against the committed Git objects. This records workflow lineage, not independent attestation of historical data exposure.

Fourteen synthetic tests passed in total. Both procedures reconstructed the existing 64-well baseline. Changing outer fold 0's evaluation labels changed its rebuilt candidate predictions by exactly 0.0; the whitening check also changed that fold's plate AUCs. Poisoning every unpurchased query value left candidate predictions unchanged. The independently implemented saved-array metric check differed from recorded candidate MSE/p90/fold metrics by at most 6.94e-18. This is numerical integrity, not independent biological validation or a fresh end-to-end replay of the retained 49-stage research candidate.

All experiments remain repeated adaptive Lib1 development: 119 organoid samples from 59 whole patients. No Protected22/Lib2 response was accessed. No patient-level rows or prediction arrays are published. No A/B prediction averaging, target/fold splicing, extra measurement, or relaxed promotion gate was used.

## Submission schedule and handoff

Continue improvements through 8 October, Nigeria time. On 9 October stop opening model families, freeze the strongest verified package, run final regression/reproducibility checks, update the existing accepted writeup, and verify the saved Kaggle entry. A GitHub commit or prepared ZIP is not proof of a Kaggle update.

The reported 7 October submission-update ZIP/report/writeup remain prepared artifacts; this research checkpoint does not claim they have been published into the accepted entry. Keep the 64-well operating demo, 64-well research candidate, and separate 72-well exploration clearly distinguished.

Research branch: dosepilot-joint-kernel-20261007.
Workspace: D:\von-dosepilot-joint-kernel-20261007.
Private outcome folders: D:\von-dosepilot-data\joint_own_drug_kernel64_20261007_run1 and D:\von-dosepilot-data\contrast_whitened_residual64_20261007_run1.

Aggregate receipts: evidence/joint_own_drug_kernel64_20261007.json, evidence/contrast_whitened_residual64_20261007.json, evidence/improvement_checkpoint64_20261007.json.

Method background: Rasmussen and Williams, Gaussian Processes for Machine Learning, Chapter 2, https://gaussianprocess.org/gpml/chapters/RW2.pdf . Nested evaluation background: https://scikit-learn.org/stable/auto_examples/model_selection/plot_nested_cross_validation_iris.html . These support the method background, not the DosePilot numerical results.

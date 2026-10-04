# Reviewer start here: von DosePilot

**Submission category: Model & Algorithm**

DosePilot is a measurement-aware drug-response reconstruction method: commit a physical assay layout before responses arrive, consume **64 identified treatment measurements**, then reconstruct **24 fixed normalized log-dose AUC summaries** with explicit identity, missing-data, and provenance rules.

**Live fictional-data demo:** https://von-dosepilot.netlify.app  
**Prepared Kaggle writeup:** [docs/KAGGLE_WRITEUP.md](docs/KAGGLE_WRITEUP.md)  
**Current technical report:** [CURRENT_TECHNICAL_REPORT.md](CURRENT_TECHNICAL_REPORT.md)

This page is a navigation aid. It creates no new accuracy or biological-validation claim.

## 90-second review path

### 1. What problem is being solved?

The retrospective source profile contains **416 treatment measurements per sample** across the two identified source plates. One frozen DosePilot deployment uses **64 measurements, 32 per plate**, or **15.38% of that treatment-measurement count**.

That is a **6.5x measurement-count compression**. It is not claimed to be a 6.5x reduction in real laboratory cost, time, controls, or organ-on-chip resources.

Exact target and measurement definitions: [TARGET_DEFINITIONS.md](TARGET_DEFINITIONS.md).

### 2. What is the current result?

On the original Lib1 development population of **119 organoid samples grouped into 59 whole patients**, with 24 fixed targets:

| Complete procedure | Patient-balanced MSE |
|---|---:|
| R13 own-drug reconstruction | 0.001144858681 |
| S2 spectral residual | 0.001070143945 |
| Previous additive drug-group kernel | 0.001060552730 |
| **Current bandwidth-0.7 additive** | **0.001058275042** |

Against the previous additive model, the current frozen estimator improves **38/59 patient means**, **5/5 outer-fold means**, and p90 patient RMSE.

It is not uniformly better: **10/24 target-average errors regress**.

For each fixed bandwidth, the residual spectral option is selected inside inner patient folds. Bandwidth 0.7 itself was selected from the prefrozen `{1.0, 0.7, 1.4}` menu after comparing reused outer-fold development results. Its displayed MSE is therefore a **post-selection development point estimate**, not an unbiased nested estimate of a bandwidth-selecting procedure.

Compact audit with all 24 target deltas: [docs/FINALIST_AUDIT.md](docs/FINALIST_AUDIT.md).

### 3. Is the 64-well claim real?

Yes, under the reported retrospective evaluation contract:

- A is one alternative **64-well** deployment, 32 p1 + 32 p2.
- B is a separate alternative **64-well** deployment, also 32 + 32.
- A prediction uses only A's 64 purchased values.
- B prediction uses only B's 64 purchased values.
- Historical scoring computes A and B losses separately, then averages the **losses**.
- A/B prediction vectors are never combined into a 128-well predictor.
- The reported expected loss is the estimand for a **uniform 1:1 choice between A and B**; a prospective test must preserve that assignment rule or prespecify and report a different estimand.

Exact frozen schedules and audit: [docs/FROZEN_OOC_EXECUTION_MANIFEST.md](docs/FROZEN_OOC_EXECUTION_MANIFEST.md).

### 4. What exactly are the 24 outputs?

Each target is the arithmetic mean of two source-plate normalized trapezoidal AUCs over **log concentration**, using the supplied **unclipped normalized viability** curve.

The output is not IC50, not a drug rank, and not a clinical-response label.

The complete public table lists, for every drug:

- full source dose grid;
- fixed AUC integration interval;
- exact dose-only quadrature;
- frozen predictor doses;
- A/B source-plate assignment.

See [docs/TARGET_DEFINITIONS.md](docs/TARGET_DEFINITIONS.md).

### 5. What fails?

The project deliberately preserves negative results and failure modes.

- bandwidth 1.4: rejected;
- residual-alignment reweighting: rejected;
- multioutput acquisition sweep: rejected;
- iterated additive correction: rejected;
- A/B consistency regularization: rejected;
- within-drug Mahalanobis geometry: rejected;
- phenotype-space kernel mixing: rejected.

Synthetic measurement stress testing also found a real weakness: coherent **±5% single-plate scaling** increases MSE much more than small independent per-well noise. That is why the prospective validation contract requires a prespecified plate-calibration/QC rule.

See [docs/SIMULATED_ASSAY_ROBUSTNESS.md](docs/SIMULATED_ASSAY_ROBUSTNESS.md).

### 6. What is demonstrated versus prospective?

**Demonstrated retrospective development evidence**
- patient-grouped nested evaluation on Lib1;
- current MSE and paired patient/fold comparisons;
- public-input numerical reproduction;
- exact runtime/evidence checks.

**Demonstrated software execution**
- identity-bound 64-well workflow;
- missing-input withholding;
- durable commit/recover/predict lifecycle;
- response-free organ-on-chip constraint compiler;
- frozen A/B schedule.

**Prospective only**
- device-specific organ-on-chip execution;
- actual laboratory resource saving;
- new independent biological confirmation;
- clinical utility.

Prospective contract: [docs/PROSPECTIVE_OOC_VALIDATION_CONTRACT.md](docs/PROSPECTIVE_OOC_VALIDATION_CONTRACT.md).

## Fast reproducibility checks

These commands require no protected cohort responses.

### Endpoint and 64-well contract

    python study/audits/verify_target_definitions.py --root .
    python study/audits/verify_frozen_ooc_schedule.py --root evidence --repo .

### Central evidence package

    python study/audits/verify_evidence_consistency.py --root .

### Full response-free release preflight

    python study/audits/release_preflight_current.py --output release_preflight.json

The current additive runner preserves the historical frozen-schedule preflight and adds endpoint-definition, Kaggle-link-portability and current-quickstart checks. The bound public receipt records **14/14 stages and 157 response-free tests passed**; three runner-contract tests passed separately.

### Public TRAIN reconstruction and current-model replay

Follow [docs/PUBLIC_REPRODUCTION.md](docs/PUBLIC_REPRODUCTION.md), then:

    python study/hybrid_residual/reproduce_bandwidth.py       --curves reconstructed_train/train_curves.csv       --output bandwidth_replay       --fit-final

The public replay does not take old predictions or the old private metadata kit as inputs.

## Evidence integrity

Useful machine-readable anchors:

- [evidence/EVIDENCE_INDEX.json](evidence/EVIDENCE_INDEX.json)
- [evidence/bandwidth_successor_20261003.json](evidence/bandwidth_successor_20261003.json)
- [evidence/finalist_audit_manifest_20261003.json](evidence/finalist_audit_manifest_20261003.json)
- [evidence/target_definitions_release_20261003.json](evidence/target_definitions_release_20261003.json)
- [evidence/frozen_ooc_execution_schedule_20261003.json](evidence/frozen_ooc_execution_schedule_20261003.json)
- [evidence/bandwidth_robustness_20261003.json](evidence/bandwidth_robustness_20261003.json)

## Important limitations

The headline accuracy result is **repeated adaptive development on the same 59-patient population**. Whole-patient splitting controls within-run leakage, but it does not turn repeatedly inspected development folds into untouched confirmation.

Protected22/Lib2 is exposed and its full primary was not estimable; it is not presented as confirmation of the current model.

The frozen bandwidth estimator is therefore the **current development incumbent**, not an independently validated clinical model and not an official competition score.

---

Official challenge pages state that the preliminary submission is reviewed from the Kaggle writeup, public repository, demo video, and technical report rather than a single prediction leaderboard. This repository is organized so each major claim above points to an executable or machine-checkable artifact.

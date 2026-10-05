**Submission category: Model & Algorithm**

# von DosePilot: 24 response summaries from 64 traceable wells

**Measurement-aware drug-screen reconstruction under a fixed treatment-well budget.**

**Team:** von DosePilot  
**Author:** Joseph Ayanda

**Repository edition updated 4 October 2026.** This file is the prepared writeup, not proof that the live Kaggle entry has been edited. The accepted entry already exists; no duplicate submission is intended.

## Demo video and code

- **Live fictional-data demo:** https://von-dosepilot.netlify.app
- **Downloadable state-bound evidence record:** https://github.com/josepha-mayo/von-dosepilot/blob/master/docs/LIVE_DEMO_TRACE_EXPORT.md
- **Offline downloaded-file verifier:** https://github.com/josepha-mayo/von-dosepilot/blob/master/docs/VERIFY_DOWNLOADED_TRACE.md
- **One-command finalist-package preflight:** https://github.com/josepha-mayo/von-dosepilot/blob/master/docs/FINALIST_PACKAGE_PREFLIGHT.md
- **Clean isolated finalist-package execution:** https://github.com/josepha-mayo/von-dosepilot/blob/master/docs/CLEAN_FINALIST_PACKAGE_EXECUTION.md — all 8 package checks passed, including the nested canonical 14-stage/173-test preflight, from a `git archive` source reconstruction and new environment on one existing host; not a network clone, clean-new-machine certification, or independent biological validation.
- **Current finalist-rubric evidence map:** https://github.com/josepha-mayo/von-dosepilot/blob/master/docs/FINALIST_RUBRIC_EVIDENCE_CURRENT.md — reconciles verified evidence under the recorded 30/30/20/10/10 criteria without assigning a self-score, estimating finalist probability, or claiming this repository text changed the accepted Kaggle entry.
- **Demo video:** https://youtu.be/QeOGJIgx378
- **Public code:** https://github.com/josepha-mayo/von-dosepilot
- **90-second reviewer path:** https://github.com/josepha-mayo/von-dosepilot/blob/master/00_REVIEWER_START_HERE.md
- **Current ten-page technical report:** https://github.com/josepha-mayo/von-dosepilot/blob/master/docs/DosePilot_Technical_Report_Current.pdf
- **Exact definitions of all 24 outputs:** https://github.com/josepha-mayo/von-dosepilot/blob/master/docs/TARGET_DEFINITIONS.md
- **Historical submitted technical report:** https://github.com/josepha-mayo/von-dosepilot/blob/master/docs/DosePilot_Technical_Report_Public.pdf
**Current judge/audit package:** [finalist audit](https://github.com/josepha-mayo/von-dosepilot/blob/master/docs/FINALIST_AUDIT.md) · [bandwidth-0.7 successor](https://github.com/josepha-mayo/von-dosepilot/blob/master/docs/BANDWIDTH_SUCCESSOR.md) · [nested bandwidth selection](https://github.com/josepha-mayo/von-dosepilot/blob/master/docs/NESTED_BANDWIDTH_EVALUATION.md) · [closed co-optimized interpolation control](https://github.com/josepha-mayo/von-dosepilot/blob/master/docs/COOPTIMIZED_CALIBRATED_CONTROL_NEGATIVE.md) · [simulated assay robustness](https://github.com/josepha-mayo/von-dosepilot/blob/master/docs/SIMULATED_ASSAY_ROBUSTNESS.md) · [frozen 64-row OoC treatment schedule](https://github.com/josepha-mayo/von-dosepilot/blob/master/docs/FROZEN_OOC_EXECUTION_MANIFEST.md) · [prospective OoC validation contract](https://github.com/josepha-mayo/von-dosepilot/blob/master/docs/PROSPECTIVE_OOC_VALIDATION_CONTRACT.md) · [current-model lifecycle](https://github.com/josepha-mayo/von-dosepilot/blob/master/docs/BANDWIDTH_LIFECYCLE.md)

**Evidence history:** [structured-kernel results and recovery](https://github.com/josepha-mayo/von-dosepilot/blob/master/docs/STRUCTURED_KERNELS_AND_RECOVERY.md) · [historical durable lifecycle and acquisition](https://github.com/josepha-mayo/von-dosepilot/blob/master/docs/DURABLE_LIFECYCLE_AND_ACQUISITION.md) · [S2 spectral successor](https://github.com/josepha-mayo/von-dosepilot/blob/master/docs/SPECTRAL_SUCCESSOR.md) · [Protected22 execution, missingness and exposure disclosure](https://github.com/josepha-mayo/von-dosepilot/blob/master/docs/PROTECTED22_RESULT.md)

## Project Summary

DosePilot targets a practical bottleneck in dose-response screening: when assay measurements are limited, which wells should be measured, and how much of the full response profile can those measurements support? It is a measurement-aware reconstruction method that commits a physical assay layout before responses arrive, consumes exactly 64 identified treatment wells per deployment, and reconstructs 24 fixed drug-response summaries with explicit missing-data and provenance rules. The retrospective Lib1 source contains 416 eligible treatment measurements per sample, so the frozen 64-well schedule uses 15.38% of that measurement count without claiming the same percentage of real laboratory cost or time.

The current model keeps the same 64-well acquisition and own-drug ridge baseline, then adds a cross-drug additive residual kernel. A prefrozen bandwidth study changed only the Gaussian drug-group lengthscale from 1.0 to 0.7. For each fixed bandwidth, nested patient-grouped evaluation selects the residual spectral option inside inner folds. Bandwidth 0.7 itself was then selected from the prefrozen `{1.0, 0.7, 1.4}` menu after comparing reused outer-fold development results. Its MSE **0.0010582750** is therefore a post-selection development point estimate: 7.56% below the retained R13 baseline and 0.215% below the previous additive model. It improves **38/59 patient means and all 5/5 outer folds versus additive**, while p90 RMSE also improves. Ten of 24 target-average errors still regress.

A subsequent prefrozen replay selected bandwidth **0.7 wholly inside all 5/5 outer training sets** while jointly selecting the existing residual-spectral option. The nested procedure's held-patient predictions were exactly identical to fixed 0.7 across all 59 patient losses, five fold means, 24 target means and both orientations. This rules out a foldwise bandwidth splice within the opened three-bandwidth menu; it is still repeated development on the same exposed folds, not independent validation or correction for the wider historical campaign. See the [nested selection record](https://github.com/josepha-mayo/von-dosepilot/blob/master/docs/NESTED_BANDWIDTH_EVALUATION.md).

DosePilot is built for auditability as much as point accuracy: public-input replay reproduces the result, the runtime binds sample/run/drug/dose/plate/well identities, and a live fictional demo shows commit-recover-predict behavior. A response-free organ-on-chip compiler and frozen treatment-plan handoff provide a concrete path to a future device-specific prospective study. The current accuracy evidence remains repeated adaptive development, **not independent confirmation** or clinical validation.

## Problem and contribution

A sparse screen is not merely a matrix with fewer columns. Selecting a different concentration, averaging two technical measurements, or replacing a missing input can change what was physically purchased and what the predictor means.

DosePilot makes the acquisition/reconstruction tradeoff executable. The intended research user supplies a supported inventory and model, receives one committed physical layout, measures those wells, and obtains supported response summaries or explicit abstentions. The method is task-specific linear reconstruction with careful experimental accounting, not a claim of new general regression theory, clinical treatment selection or universal superiority.

## Method and implementation

The development population contains **119 organoid samples grouped into 59 whole patients**. The targets are 24 fixed normalized log-dose AUCs of the supplied unclipped viability curves, averaged across two identified source plates. Repeated samples from one patient never cross a fitting/validation split.

R13 assigns two native doses to every drug and sixteen third-dose upgrades, for **64 distinct physical treatment wells**. Acquisition uses fitting-only covariance scores. Each drug-specific ridge head sees only its own two or three purchased measurements. A common regularization penalty is selected inside three patient-grouped inner folds; five patient-grouped outer folds evaluate the complete procedure.

S2 starts from those R13 predictions and fits a regularized cross-drug correction to the training residuals. The additive family instead sums 24 Gaussian components, one over each drug's purchased coordinates, plus the linear component. The current successor changes only the Gaussian group lengthscale multiplier from 1.0 to **0.7**; the linear component, acquisition, base model and ten residual spectral options stay fixed. Each fitting slice selects one common spectral option inside the same three inner whole-patient folds. No successor uses additional measurements. Because these corrections couple outputs through shared fitting, all 64 values are required for the primary prediction; one missing value withholds all 24 primary outputs.

Two complementary plate layouts, A and B, each cost 64 wells, 32 per plate. Their historical squared losses are averaged to estimate the expected loss under a **uniform 1:1 assignment** to one alternative independently of outcomes. Their prediction vectors are never averaged into an unbudgeted 128-well ensemble. A prospective test must preserve that assignment rule or prespecify and report a different estimand. Controls are outside the stated treatment-well budget.

The measured endpoint includes purchased observations, so this is reconstruction of a measured response summary, not proof that a noiseless biological curve has been recovered. Repeated method development on the same patients limits confirmatory interpretation even with correct within-run split containment.

## Results and validation

### Original 24-target development task

| Complete procedure | Patient-balanced MSE |
|---|---:|
| Earlier paired-measurement procedure, R9 | 0.0017214230 |
| Matched paired-native control | 0.0017379326 |
| Retained broader-coverage procedure, R13 | **0.0011448587** |
| Archived lower-point reference, R18 | 0.0011414048 |
| S2 spectral residual successor | **0.0010701439** |
| Previous additive drug-group kernel | 0.0010605527 |
| **Bandwidth-0.7 additive successor** | **0.0010582750** |
| Residual-alignment reweighting challenger | 0.0010608378 |
| Co-optimized calibrated interpolation control | 0.0014389065 |
| Interpolation with independently optimized acquisition | 0.0024168103 |

Against R9, R13 improves 53/59 patient means and all five outer-fold means. Six patient means and six drug-average errors nevertheless regress. Against the separately optimized interpolation policy, R13 has 52.63% lower error and improves 59/59 patient means. All of these are repeated development comparisons, not separate independent cohorts.

The previous additive model improves 45/59 patient means versus S2, 49/59 versus R13 and 47/59 versus R18. The bandwidth-0.7 successor then improves **38/59 patient means versus additive**, all five outer-fold means, and p90 RMSE (0.037894 versus 0.038073). Its two orientation-wide MSEs are **0.0011047522** and **0.0010117979**. The descriptive paired-patient interval for bandwidth-0.7 minus additive mean loss is [-4.159e-6, -4.157e-7]. These intervals are descriptive and not selection-corrected.

Bandwidth 1.4 was rejected. Residual-alignment reweighting also remained 0.0269% worse than additive, with 24/59 patient wins, 2/5 favorable folds, worse p90; structured-kernel, consistency and acquisition challengers were rejected as well. The promoted bandwidth-0.7 model still regresses on ten target-average errors versus additive, so it is not described as uniformly superior.

A later one-shot, strictly prefrozen co-optimized calibrated-interpolation control also failed decisively on the identical 119-sample, 59-patient, 24-target and exact-64-well task: MSE **0.0014389065** versus **0.0010582750** for bandwidth 0.7 (35.97% worse), **3/59** patient wins, **0/5** favorable folds and **22/24** target regressions. A separate no-refit audit passed. The family is closed with no retry, calibration grid, rescue or splice. This is retained repeated-development evidence, not independent validation. See the [complete negative-result record](https://github.com/josepha-mayo/von-dosepilot/blob/master/docs/COOPTIMIZED_CALIBRATED_CONTROL_NEGATIVE.md) and [aggregate receipt](https://github.com/josepha-mayo/von-dosepilot/blob/master/evidence/cooptimized_calibrated_control_20261004.json).

### Separately sourced external assessments

**FORECAST-1:** an adapted eight-drug task used 21 dose-level readouts, with fitting restricted to its community cohort. The prespecified completeness rule retained 13 of 19 confirmation patients. Learned reconstruction reached MSE 0.0021715 versus 0.0038552 for independently optimized interpolation, winning 10/13 patient means. The original support gate failed because it required at least 12 wins against the original 19-patient denominator. It was not relaxed. A later training-calibrated interpolation audit narrowed the advantage to 24.42%, with 9/13 patient wins and a descriptive paired interval crossing zero. A separate six-drug analysis of the same FORECAST source is not another independent confirmation. See [the external record](https://github.com/josepha-mayo/von-dosepilot/blob/master/docs/EXTERNAL_CRC_CONFIRMATION.md) and [stronger-control audit](https://github.com/josepha-mayo/von-dosepilot/blob/master/docs/CALIBRATED_CONTROL_AUDIT.md).

**Matched tumor-CAF coculture:** an adapted four-drug task used 11 replicate-averaged dose-level readouts, trained on 13 monoculture cases and evaluated on 15 different matched-coculture cases. Learned MSE was 0.0029697 versus 0.0052366 for optimized interpolation, 43.29% lower. It won 10/15 organoid means, was nonworse on 3/4 drug MSEs, and reduced p90 RMSE from 0.10986 to 0.06666. All four original gate components passed. A later response-free audit of the published pseudonymous patient-case key established no overlap between the frozen case sets. A prespecified monoculture diagnostic also favored reconstruction. This supports an adapted design under a stromal context change, not direct validation of the original R13 fitted heads. See [the study](https://github.com/josepha-mayo/von-dosepilot/blob/master/docs/STROMA_CONTEXT_CONFIRMATION.md) and [identity audit](https://github.com/josepha-mayo/von-dosepilot/blob/master/docs/STROMA_PATIENT_IDENTITY_AUDIT.md).

**eLife retrospective stress test:** a separate five-drug, 12-organoid task used 13 of 54 target-support dose-level readouts. Learned MSE was 0.0041734 versus 0.0060423 for interpolation. The fixed gate failed: only 7/12 organoid losses improved and the paired interval crossed zero. Source values had been visible during structural inspection, so this is not blind confirmation. See [the full stress-test record](https://github.com/josepha-mayo/von-dosepilot/blob/master/docs/ELIFE_SPARSE_STRESS.md).

### Latest approved 22-head transfer: primary not estimable

The 1 October execution projected the original final R13 model, without refitting, to the 22 heads supported at exact Lib2 concentrations. Gedatolisib and Palbociclib were excluded in the approved protocol before this run because of previously identified support gaps. Candidate and TRAIN-calibrated interpolation each used **58 physical treatment wells per alternative**.

All **19,642** authorized endpoint-support cells in the planned **61-PDO / 31-patient** frame were processed. Five required responses were nonnumeric. Consequently the frozen full-cohort primary is **NOT_ESTIMABLE**, and confirmation did not pass. No missing value was imputed and no primary denominator was reduced.

The prespecified complete-patient secondary population contains **54 PDOs from 29 patients**. On that population only, R13 expected MSE is **0.0017349427**, versus **0.0022689547** for calibrated interpolation: **23.54% lower**, with **26/29** patient wins and **16/22** nonworse target MSEs. These estimates cannot replace the unavailable full primary or establish performance for missing patients.

A newer live project receipt, discovered after this run, records earlier access to 15 PDOs from 9 of the same patients before a different exact22 importer stopped. The coordinator should have reconciled that record before relying on the preaccess handoff. This execution therefore cannot be presented as untouched-cohort confirmation. The original failure remains preserved and all 61/31 records are now treated as exposed. See [the complete disclosure and verification](https://github.com/josepha-mayo/von-dosepilot/blob/master/docs/PROTECTED22_RESULT.md), [the earlier failed attempt](https://github.com/josepha-mayo/von-dosepilot/blob/master/docs/LIB2_EXACT22_INCOMPLETE.md), and [current access status](https://github.com/josepha-mayo/von-dosepilot/blob/master/evidence/PROTECTED22_ACCESS_STATUS.json).

## Operating demonstration and organ-on-chip path

The public demo uses **fictional measurements and parameters** without publishing patient data. The durable CLI now has an explicit bandwidth-0.7 path matching the current development incumbent. It rejects additive-1.0 artifacts and wrong bandwidth metadata rather than silently adapting them. The lifecycle exposes commit→recover→predict commands, validates a caller-declared 64-well inventory, exact plan identities and 32/32 plate balance, and records hash-bound create-exclusive state before user-facing exports. It automatically rejects changed previously recorded measurements and can recover a failed export. An optional, explicitly labelled historical own-drug baseline can return 23 unaffected estimates when one reading is missing; the bandwidth-0.7 primary itself requires all 64 readings and returns no primary outputs when incomplete. The live demo's inspector can download the exact state-bound six-field JSON record it displays: plan, measurement and result digests remain null until that evidence exists, and the export contains no raw readings or model outputs. Ten current-model tests and a six-call fictional workflow passed; 65 durable-runtime tests pass in total. These local POSIX records are not signed, WORM or administrator-immutable. Runtime behavior is not another biological accuracy test.

The current bandwidth model's exact A/B treatment schedule is also published as two 64-row prospective manifests: the same 64 drug+dose identities, 32 source treatments per plate, with complementary A/B plate assignment. The release verifier checks that the public 64-row map exactly matches those plans; five tamper tests cover display drift, paired-hash A/B manipulation, transport artifacts and claim-boundary promotion. Nine device/protocol binding fields remain explicitly TBD until a real platform is chosen. See [the frozen schedule](https://github.com/josepha-mayo/von-dosepilot/blob/master/docs/FROZEN_OOC_EXECUTION_MANIFEST.md).

A response-free organ-on-chip constraint compiler separately represents device/run, channel, reservoir, shared-flow circuit, compartment, exact exposure, timepoint and controls. It returns a deterministic manifest compatible with the declared constraints or an explicit incompatibility. Its included fixture is synthetic. The compiler does not establish real hardware feasibility or measured OoC performance. A prospective deployment still requires a reviewed device inventory, assay-specific constraints and experimental evaluation. See [the compiler and limits](https://github.com/josepha-mayo/von-dosepilot/blob/master/docs/OOC_FEASIBILITY.md).

## Reproducibility, rights and practical limits

Run the operating demo:

```bash
python -m pip install -r requirements.txt
python study/durable_runtime/run_bandwidth_lifecycle_demo.py --output bandwidth_lifecycle_demo_001
```

No GPU, paid model service or language-model API is required by the DosePilot runtime. The current successor can be replayed from the same public-derived TRAIN route with:

```bash
python study/hybrid_residual/reproduce_bandwidth.py --curves reconstructed_train/train_curves.csv --output bandwidth_replay --fit-final
```

A fresh replay reproduced bandwidth-0.7 MSE 0.001058275042, additive MSE 0.001060552730 and R13 MSE 0.001144858681 without historical prediction inputs. The exact public Mendeley Data v3 `Data S4.xlsx` is hash-pinned. Its 15,886,254 bytes match SHA-256 `3847aa93b2a84c7d5d0b04c26494f39f35963fc41e96eae97d8a180fbc33d81c`. The public route reconstructs all 49,504 historical Lib1 TRAIN measurements and reproduces all four locked R9/R13 metrics within `1e-12`. Commands and receipts are in [PUBLIC_REPRODUCTION.md](https://github.com/josepha-mayo/von-dosepilot/blob/master/docs/PUBLIC_REPRODUCTION.md).

The new saved-array verifier adds eight synthetic tests and checks 83 comparisons without a second source read or refit. Actual Protected22 saved-array verification still requires the author's hash-bound result and prediction files; that addendum is not a standalone public source-to-results distribution. This limit is separate from the working public Lib1 reproduction route.

Original code and fictional fixtures are MIT-licensed. External papers and datasets retain their own rights; see [NOTICE](https://github.com/josepha-mayo/von-dosepilot/blob/master/NOTICE.md) and the individual study documentation. No patient-level arrays or fitted biological model weights are distributed in the new public addendum. The source paper's clinical findings are not validation of DosePilot.

No prospective laboratory cost saving, clinical treatment benefit, calibrated uncertainty, winning probability, official rank improvement or full24 external validation is claimed. The contribution is an inspectable measurement-budget method and usable research workflow with explicit scope, failures and reproductions.

## AI assistance

ChatGPT assisted with research synthesis, implementation, numerical checking, documentation and release preparation. Prior completed OpenCode reviews used Muse Spark 1.3. The eight-session batch requested on 1 October did not launch because the laptop's available memory fell below the configured guard; it is not counted as completed review. The runtime itself uses no language-model API.

## Primary references

1. Kryeziu et al., *Cell Reports Medicine* (2026), DOI: 10.1016/j.xcrm.2026.102840.
2. Abdel-Rehim et al., *Bioinformatics* (2026), DOI: 10.1093/bioinformatics/btag293.
3. Xi, Briol & Girolami, Bayesian Quadrature for Multiple Related Integrals, PMLR 80 (2018).
4. Longi et al., Sensor Placement for Spatial Gaussian Processes with Integral Observations, PMLR 124 (2020).
5. Tan et al., *Cell Reports Medicine* (2023), DOI: 10.1016/j.xcrm.2023.101335.
6. Farin et al., *Cancer Discovery* (2023), DOI: 10.1158/2159-8290.CD-23-0050; Mendeley Data DOI: 10.17632/fypp6xhkjy.1.
7. Verissimo et al., *eLife* (2016), DOI: 10.7554/eLife.18489.

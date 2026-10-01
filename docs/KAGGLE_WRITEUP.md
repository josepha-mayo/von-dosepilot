**Submission category: Model & Algorithm**

# von DosePilot: 24 response summaries from 64 traceable wells

**Measurement-aware drug-screen reconstruction under a fixed treatment-well budget.**

**Team:** von DosePilot  
**Author:** Joseph Ayanda

**Repository edition updated 1 October 2026.** This file is the prepared writeup, not proof that the live Kaggle entry has been edited. The accepted entry already exists; no duplicate submission is intended.

## Demo video and code

**Demo video:** https://youtu.be/QeOGJIgx378  
**Public code:** https://github.com/josepha-mayo/von-dosepilot  
**Historical technical report:** https://github.com/josepha-mayo/von-dosepilot/blob/master/docs/DosePilot_Technical_Report_Public.pdf  
**Current result addendum:** [Protected22 execution, missingness and exposure disclosure](PROTECTED22_RESULT.md)

## Project Summary

DosePilot addresses a practical decision in dose-response experiments: when treatment wells are limited, should a screen repeat measurements for precision or spend those wells on broader concentration coverage? The project treats acquisition as part of the predictive method, with every observation tied to its real sample, run, drug, concentration, plate and physical well.

On a retrospective colorectal-cancer organoid task, the retained R13 procedure reconstructs 24 fixed drug-response summaries from exactly 64 treatment wells. Its complete source curves contain 416 eligible treatment measurements per sample. The 64-well policy therefore uses 15.38% of that retrospective measurement count, not necessarily 15.38% of laboratory cost or time. Whole-patient nested evaluation gave patient-balanced MSE 0.0011448587: 33.49% lower than the earlier paired-measurement procedure and 34.13% lower than a matched paired-native control. Planning, scaling and model selection remain inside each fitting split.

The operating software commits a layout before responses arrive, rejects incompatible measurements, withholds only affected outputs when required values are missing, and recovers the same layout after an export failure. The historical result has a public source-to-results reproduction route without the earlier private input bundle or a language-model API.

Evidence is deliberately separated by strength. The original result is repeatedly reused development evidence. A separately sourced matched-CAF experiment passed its fixed support gate for an adapted design. FORECAST-1 and eLife assessments did not fully pass their gates. The latest approved 22-head transfer execution produced useful conditional evidence but no estimable full-cohort primary; previously recorded cross-session exposure also prevents an untouched-confirmation claim. These limits remain visible beside the positive results.

## Problem and contribution

A sparse screen is not merely a matrix with fewer columns. Selecting a different concentration, averaging two technical measurements, or replacing a missing input can change what was physically purchased and what the predictor means.

DosePilot makes the acquisition/reconstruction tradeoff executable. The intended research user supplies a supported inventory and model, receives one committed physical layout, measures those wells, and obtains supported response summaries or explicit abstentions. The method is task-specific linear reconstruction with careful experimental accounting, not a claim of new general regression theory, clinical treatment selection or universal superiority.

## Method and implementation

The development population contains **119 organoid samples grouped into 59 whole patients**. The targets are 24 fixed normalized log-dose AUCs of the supplied unclipped viability curves, averaged across two identified source plates. Repeated samples from one patient never cross a fitting/validation split.

R13 assigns two native doses to every drug and sixteen third-dose upgrades, for **64 distinct physical treatment wells**. Acquisition uses fitting-only covariance scores. Each drug-specific ridge head sees only its own two or three purchased measurements. A common regularization penalty is selected inside three patient-grouped inner folds; five patient-grouped outer folds evaluate the complete procedure.

Two complementary plate layouts, A and B, each cost 64 wells, 32 per plate. Their historical squared losses are averaged to estimate the expected loss of choosing one alternative independently of outcomes. Their prediction vectors are never averaged into an unbudgeted 128-well ensemble. Controls are outside the stated treatment-well budget.

The measured endpoint includes purchased observations, so this is reconstruction of a measured response summary, not proof that a noiseless biological curve has been recovered. Repeated method development on the same patients limits confirmatory interpretation even with correct within-run split containment.

## Results and validation

### Original 24-target development task

| Complete procedure | Patient-balanced MSE |
|---|---:|
| Earlier paired-measurement procedure, R9 | 0.0017214230 |
| Matched paired-native control | 0.0017379326 |
| Retained broader-coverage procedure, R13 | **0.0011448587** |
| Interpolation with independently optimized acquisition | 0.0024168103 |

Against R9, R13 improves 53/59 patient means and all five outer-fold means. Six patient means and six drug-average errors nevertheless regress. Against the separately optimized interpolation policy, R13 has 52.63% lower error and improves 59/59 patient means. All of these are repeated development comparisons, not separate independent cohorts.

### Separately sourced external assessments

**FORECAST-1:** an adapted eight-drug task used 21 dose-level readouts, with fitting restricted to its community cohort. The prespecified completeness rule retained 13 of 19 confirmation patients. Learned reconstruction reached MSE 0.0021715 versus 0.0038552 for independently optimized interpolation, winning 10/13 patient means. The original support gate failed because it required at least 12 wins against the original 19-patient denominator. It was not relaxed. A later training-calibrated interpolation audit narrowed the advantage to 24.42%, with 9/13 patient wins and a descriptive paired interval crossing zero. A separate six-drug analysis of the same FORECAST source is not another independent confirmation. See [the external record](EXTERNAL_CRC_CONFIRMATION.md) and [stronger-control audit](CALIBRATED_CONTROL_AUDIT.md).

**Matched tumor-CAF coculture:** an adapted four-drug task used 11 replicate-averaged dose-level readouts, trained on 13 monoculture cases and evaluated on 15 different matched-coculture cases. Learned MSE was 0.0029697 versus 0.0052366 for optimized interpolation, 43.29% lower. It won 10/15 organoid means, was nonworse on 3/4 drug MSEs, and reduced p90 RMSE from 0.10986 to 0.06666. All four original gate components passed. A later response-free audit of the published pseudonymous patient-case key established no overlap between the frozen case sets. A prespecified monoculture diagnostic also favored reconstruction. This supports an adapted design under a stromal context change, not direct validation of the original R13 fitted heads. See [the study](STROMA_CONTEXT_CONFIRMATION.md) and [identity audit](STROMA_PATIENT_IDENTITY_AUDIT.md).

**eLife retrospective stress test:** a separate five-drug, 12-organoid task used 13 of 54 target-support dose-level readouts. Learned MSE was 0.0041734 versus 0.0060423 for interpolation. The fixed gate failed: only 7/12 organoid losses improved and the paired interval crossed zero. Source values had been visible during structural inspection, so this is not blind confirmation. See [the full stress-test record](ELIFE_SPARSE_STRESS.md).

### Latest approved 22-head transfer: primary not estimable

The 1 October execution projected the original final R13 model, without refitting, to the 22 heads supported at exact Lib2 concentrations. Gedatolisib and Palbociclib were excluded in the approved protocol before this run because of previously identified support gaps. Candidate and TRAIN-calibrated interpolation each used **58 physical treatment wells per alternative**.

All **19,642** authorized endpoint-support cells in the planned **61-PDO / 31-patient** frame were processed. Five required responses were nonnumeric. Consequently the frozen full-cohort primary is **NOT_ESTIMABLE**, and confirmation did not pass. No missing value was imputed and no primary denominator was reduced.

The prespecified complete-patient secondary population contains **54 PDOs from 29 patients**. On that population only, R13 expected MSE is **0.0017349427**, versus **0.0022689547** for calibrated interpolation: **23.54% lower**, with **26/29** patient wins and **16/22** nonworse target MSEs. These estimates cannot replace the unavailable full primary or establish performance for missing patients.

A newer live project receipt, discovered after this run, records earlier access to 15 PDOs from 9 of the same patients before a different exact22 importer stopped. The coordinator should have reconciled that record before relying on the preaccess handoff. This execution therefore cannot be presented as untouched-cohort confirmation. The original failure remains preserved and all 61/31 records are now treated as exposed. See [the complete disclosure and verification](PROTECTED22_RESULT.md), [the earlier failed attempt](LIB2_EXACT22_INCOMPLETE.md), and [current access status](../evidence/PROTECTED22_ACCESS_STATUS.json).

## Operating demonstration and organ-on-chip path

The public demo uses **fictional measurements and parameters** to exercise the workflow without publishing patient data. It shows inventory validation, committing a plan, predictions from complete inputs, affected-head abstention, rejection of wrong concentrations and recovery after an export failure. Runtime behavior is not presented as another biological accuracy test.

A response-free organ-on-chip constraint compiler separately represents device/run, channel, reservoir, shared-flow circuit, compartment, exact exposure, timepoint and controls. It returns a deterministic manifest compatible with the declared constraints or an explicit incompatibility. Its included fixture is synthetic. The compiler does not establish real hardware feasibility or measured OoC performance. A prospective deployment still requires a reviewed device inventory, assay-specific constraints and experimental evaluation. See [the compiler and limits](OOC_FEASIBILITY.md).

## Reproducibility, rights and practical limits

Run the operating demo:

```bash
python -m pip install -r requirements.txt
python run_demo.py --output demo_run_001
```

No GPU, paid model service or language-model API is required by the DosePilot runtime. The exact public Mendeley Data v3 `Data S4.xlsx` is hash-pinned. Its 15,886,254 bytes match SHA-256 `3847aa93b2a84c7d5d0b04c26494f39f35963fc41e96eae97d8a180fbc33d81c`. The public route reconstructs all 49,504 historical Lib1 TRAIN measurements and reproduces all four locked R9/R13 metrics within `1e-12`. Commands and receipts are in [PUBLIC_REPRODUCTION.md](PUBLIC_REPRODUCTION.md).

The new saved-array verifier adds eight synthetic tests and checks 83 comparisons without a second source read or refit. Actual Protected22 saved-array verification still requires the author's hash-bound result and prediction files; that addendum is not a standalone public source-to-results distribution. This limit is separate from the working public Lib1 reproduction route.

Original code and fictional fixtures are MIT-licensed. External papers and datasets retain their own rights; see [NOTICE](../NOTICE.md) and the individual study documentation. No patient-level arrays or fitted biological model weights are distributed in the new public addendum. The source paper's clinical findings are not validation of DosePilot.

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

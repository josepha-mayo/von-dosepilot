# von DosePilot

## 24 response summaries from 64 traceable treatment wells

Joseph Ayanda | Model & Algorithm | Current public report | 3 October 2026

> A measurement-aware reconstruction system that commits the physical assay layout before responses arrive, checks every purchased drug-dose-plate identity, and returns 24 fixed research summaries or an explicit abstention.

| Current verified development result | Value |
|---|---:|
| Patient-balanced full-24 MSE | 0.001058275042 |
| Improvement versus original R13 | 7.56% |
| Patient wins versus R13 | 49 / 59 |
| Favorable outer folds versus R13 | 5 / 5 |
| Physical treatment wells | 64 per deployment |

The current bandwidth-0.7 additive successor is the strongest verified model on the original Lib1 development task. It is repeated adaptive development evidence, not independent confirmation, an official competition score, or a clinical result.

Repository: https://github.com/josepha-mayo/von-dosepilot

Live fictional-data demonstration: https://von-dosepilot.netlify.app

<!-- pagebreak -->

# Executive summary

## The decision DosePilot makes

Sparse screening is not just prediction with fewer columns. Every feature corresponds to a drug, an exact native dose, a source plate, and a physical treatment well. DosePilot chooses which 64 treatment wells to acquire from a 416-measurement source panel, commits that choice before seeing a new sample's responses, and reconstructs 24 fixed normalized log-dose AUC summaries.

The acquisition and evaluation contract is intentionally strict:

- 119 organoid samples are grouped into 59 whole patients.
- The endpoint is fixed for all 24 drugs.
- Each deployment uses exactly 64 distinct treatment wells, 32 per source plate.
- All samples from a patient stay on the same side of every inner and outer fold.
- Alternative layouts A and B are scored separately; their losses are averaged.
- A/B prediction vectors are never averaged into a hidden 128-well ensemble.
- Planning, scaling, model fitting, and hyperparameter selection occur inside fitting splits.

## What is currently demonstrated

The bandwidth-0.7 additive successor reaches patient-balanced MSE 0.001058275042, 7.56% below original R13 and 7.28% below archived R18. Against its immediate additive predecessor, the gain is smaller - 0.215% - but broad: 38/59 patient means improve, all five outer folds improve, and p90 patient RMSE falls from 0.038073112 to 0.037894285. The same physical plans are used.

Public-input replay rebuilds the result from the hash-bound public source route. A separate runtime checks model kind, bandwidth, plan, construction anchor, sample/run/drug/dose/plate/well identity, and missingness. The response-free release preflight passes 12 stages and 148 tests.

## What is not demonstrated

No current fitted model has an untouched external confirmation. The original Protected22 full primary is not estimable because five required cells are unavailable, and prior exposure prevents an untouched-cohort claim. External FORECAST-1 and eLife adaptations failed their complete preset gates. A matched-CAF design adaptation passed its own gate but does not validate the current fitted 24-output weights.

No prospective organ-on-chip experiment, clinical benefit, calibrated uncertainty, financial saving, elapsed-time saving, or competition rank is claimed.

<!-- pagebreak -->

# Study, endpoint, and physical budget

## Public source and development frame

The biological source is the colorectal-cancer patient-derived organoid study of Kryeziu et al. The exact public Mendeley Data v3 Data S4 workbook is 15,886,254 bytes with SHA-256 3847aa93b2a84c7d5d0b04c26494f39f35963fc41e96eae97d8a180fbc33d81c. The project reconstructs an exact historical TRAIN CSV from that workbook using only public input metadata.

The frozen development frame contains 119 Lib1 organoid samples from 59 whole patients and 49,504 selected normalized-viability measurements. Recurrent lesions and repeated samples from the same patient remain in one grouping unit. The source contains 119 selected raw records, distinct from the paper's filtered count of 117.

## Fixed response target

Each target is the average of two identified plate-specific discrete trapezoidal areas under the supplied viability curve on a fixed log-dose interval:

```text
y(i,j) = 0.5 * [T_j(v_i,j,p1) + T_j(v_i,j,p2)]
```

T_j uses the declared native dose support and fixed boundary interpolation. Supplied normalized viability values are not clipped to [0,1]. The endpoint is not IC50, a drug rank, or clinical response. Purchased measurements can contribute to the measured reference; this is reconstruction of a measured summary, not recovery of a noiseless biological truth.

## Sixty-four wells means sixty-four physical measurements

The complete selected source curves contain 416 eligible target-treatment measurements per sample, 208 per plate. The frozen policy selects two native doses for every one of 24 drugs and awards a third-dose upgrade to 16 drugs:

```text
24 x 2 + 16 x 1 = 64 treatment wells
```

That is 15.38% of the source treatment-measurement count. It does not imply an 84.62% reduction in money, material, labor, or elapsed time. Vehicle and viability controls remain separate resources outside this treatment-well count.

Two complementary layouts map the same 64 drug-dose identities across p1 and p2. Each is a complete 64-well alternative, not half of a joint 128-well design.

| Frozen schedule property | A | B |
|---|---:|---:|
| Distinct treatment rows | 64 | 64 |
| Source-plate p1 rows | 32 | 32 |
| Source-plate p2 rows | 32 | 32 |
| Two-dose targets | 8 | 8 |
| Three-dose targets | 16 | 16 |

<!-- pagebreak -->

# Model and evaluation

## Stage 1: training-contained acquisition

For each drug, the allocator compares native two-dose and three-dose subsets using fitting-only moments and fixed planning penalty alpha = 0.1. It retains the best subset of each size, then allocates the 16 third-dose upgrades with largest estimated reduction in regularized reconstruction variance.

```text
subset criterion = Var(y) - c^T (G + alpha I)^(-1) c
```

G is the standardized purchased-feature covariance and c is feature-target covariance. This is a training criterion, not a guarantee of future error. Acquisition, means, and scales are recomputed in every fitting slice.

## Stage 2: own-drug ridge baseline

Each of 24 ridge heads sees only its own drug's two or three purchased measurements across many training samples. Intercepts are unpenalized and feature standard deviations retain the historical 0.05 floor. One shared ridge penalty is selected inside three patient-grouped inner folds.

## Stage 3: additive residual correction

The current model fits a cross-drug correction to residuals from the own-drug baseline. Its kernel is the sum of 24 drug-group Gaussian components plus an unchanged linear component. For group j with d_j purchased coordinates:

```text
k_j(z,z') = d_j * exp(-||z_j-z'_j||^2 / (2*d_j*0.7^2))
```

The bandwidth successor changes only the global Gaussian group lengthscale multiplier from 1.0 to 0.7. It does not change a purchased well, the base model, the linear kernel, the ten residual spectral options, or the patient folds. The wider prefrozen 1.4 alternative failed and was retained as a negative result.

## Nested whole-patient evaluation

Five outer folds estimate development performance; three inner patient folds choose one residual spectral option. Patient balance gives each patient's collection of samples equal total mass. The complete procedure is evaluated on all 24 targets.

The internal promotion rule requires improvement against both R13 and archived R18 of at least 5% MSE, at least 40/59 patient wins, at least 4/5 favorable folds, nonworse p90, and each orientation-wide error below both references. Incumbent-facing successors must also beat the immediate predecessor on mean, patient breadth, all five folds, and tail behavior. This rule is model-selection discipline, not an official judging formula.

# Same-task development results

## Selection path

| Complete procedure | Patient-balanced MSE | Status |
|---|---:|---|
| R9 earlier paired-well method | 0.001721423005 | historical baseline |
| Matched paired-native control | 0.001737932638 | historical control |
| Separately optimized interpolation | 0.002416810289 | matched-budget control |
| R13 own-drug reconstruction | 0.001144858681 | original retained baseline |
| R18 exploratory candidate | 0.001141404811 | unpromoted |
| S2 spectral residual | 0.001070143945 | superseded improvement |
| Additive group kernel, bandwidth 1.0 | 0.001060552730 | direct predecessor |
| Bandwidth-0.7 additive successor | 0.001058275042 | current incumbent |

The current model is 7.56% below R13, 7.28% below R18, 0.215% below the immediate additive predecessor, and 56.21% below the separately optimized interpolation control. These comparisons use the same 119 samples, 59 patients, 24 targets, and 64-well treatment budget.

## Breadth and tail

| Comparison | Relative MSE gain | Patient wins | Favorable folds | Tail result |
|---|---:|---:|---:|---|
| Current vs R13 | 7.56% | 49 / 59 | 5 / 5 | passes historical screen |
| Current vs R18 | 7.28% | 47 / 59 | 5 / 5 | passes historical screen |
| Current vs additive 1.0 | 0.215% | 38 / 59 | 5 / 5 | p90 improves |

Orientation-wide MSEs are 0.001104752162 and 0.001011797922. The p90 of patient expected RMSE is 0.037894285, versus 0.038073112 for additive 1.0.

## Adverse slices remain visible

Fourteen of 24 target-average errors are nonworse versus the additive predecessor; ten regress: Afatinib, Bemcentinib, Encorafenib, Idasanutlin, LCL161, Lapatinib, Regorafenib, SN-38, Trametinib, and Volasertib. Ten of 59 patient means regress versus R13. No claim of uniform improvement is made.

The descriptive paired-patient interval for current-minus-additive mean loss is [-4.159e-6, -4.157e-7]. It is not selection-corrected because the same development population has been reused across research rounds.

<!-- pagebreak -->

# Negative results and external evidence

## Bounded challengers were rejected

| Challenger | MSE | Decision reason |
|---|---:|---|
| Bandwidth 1.4 | 0.001063709359 | 18/59 patient wins; 0/5 folds |
| Residual-alignment weighting | 0.0010608378 | worse mean and p90; 2/5 folds |
| Multioutput acquisition sweep | 0.0010665434 | 21/59 wins; worse p90 |
| Iterated additive, two cycles | 0.0010693535 | incumbent screen failed |
| A/B consistency regularization | 0.00108007+ | incumbent screen failed |
| Additive linear plus Matern 3/2 | 0.001146185234 | 0.116% worse than control |

These failures matter: the project did not promote the literal lowest decimal from every exploratory branch, did not splice targets using outer-fold outcomes, and did not retune rejected families to erase adverse evidence.

## Protected22: full primary not estimable

The approved missingness-reporting execution processed all 19,642 planned cells for 61 PDOs, 31 whole patients, and 22 targets. Of these, 19,637 were numeric and five required cells were unavailable. The frozen full-cohort primary is therefore NOT_ESTIMABLE. No imputation, cohort shrinkage, target dropping, or concentration substitution was used.

A prespecified complete-patient conditional diagnostic contains 54 PDOs from 29 patients. On that conditional population, unchanged R13 MSE is 0.001734942672 versus 0.002268954667 for calibrated interpolation, with 26/29 patient wins and 16/22 target means nonworse. This is not the primary. A prior run had already exposed 15 PDOs from nine patients, so neither execution is untouched confirmation. All original Lib2 records are treated as exposed and closed to further tuning.

## Separate external adaptations

The matched-CAF Farin adaptation is the strongest separate design evidence: 15 confirmation patient cases were disjoint from 13 development cases under the published patient-case key. The adapted method reached MSE 0.0029697 versus 0.0052366, 43.29% lower, with 10/15 case wins and 3/4 target means improving. It passed its own four-part gate.

This result uses a different cohort, endpoint panel, and adapted design. It does not directly validate the current bandwidth model's fitted parameters. FORECAST-1 and public eLife adaptations did not fully pass their preset gates and remain reported as failures.

# Scientist workflow and evidence integrity

## Commit, measure, predict, recover

The current runtime is a two-stage research workflow:

1. The scientist supplies a supported inventory and explicit construction trust anchor.
2. DosePilot validates exactly 64 distinct treatment identities and a 32/32 plate split.
3. The plan is committed before response values are accepted.
4. Measured values are checked against sample, run, drug, exact dose, unit, source plate, and well.
5. Complete inputs produce 24 current-model summaries.
6. One missing purchased value withholds all 24 coupled primary outputs.
7. An explicitly acknowledged recovery path may expose 23 older own-drug baseline estimates, clearly labeled as a different model.
8. Changed recorded readings, changed recommitments, and silent old-model substitution are rejected.

The ledger records model, plan, construction, commitment, measurement, and source hashes. Create-exclusive local files and same-frame process locks reduce accidental overwrite and concurrent forks. They are not signed, WORM, administrator-immutable, or proof that a wet-lab event occurred.

## Verified software behavior

| Check | Verified result |
|---|---:|
| Current-model training-record runtime comparisons | 238 |
| Maximum direct-matrix prediction difference | 2.22e-16 |
| Single-missing-position withholding checks | 64 / 64 |
| Durable-runtime tests | 65 |
| Current-model adapter tests within that suite | 10 |
| Acquisition tests | 9 |
| Full response-free release preflight | 12 stages / 148 tests |

The fictional lifecycle demonstration makes six CLI calls and verifies plan commitment, incomplete-primary rejection, explicit baseline recovery, changed-reading rejection, complete prediction, and exact export recovery. It uses seeded fictional parameters and measurements, not patient data.

## Synthetic failure envelope

Post hoc perturbation without refitting found small effects from independent z-space noise and much larger effects from coherent single-plate scale drift. At 0.01 z-units, mean MSE rose about 0.06%; at 0.05, about 1.38%; at 0.10, about 5.58%. A coherent plus or minus 5% single-plate shift raised MSE by roughly 14.5% to 16.8%.

These are software stress tests, not estimates of real assay coefficient of variation. Their operational implication is narrow: prospective work should predefine plate calibration and QC rather than inventing corrections after outcomes.

<!-- pagebreak -->

# Prospective organ-on-chip handoff

## What is frozen today

The current all-TRAIN construction pins model kind dosepilot.additive_kernel_bandwidth.v1, bandwidth multiplier 0.7, and acquisition plan SHA-256 25b14b67b2e5ab82394f1409ed72f68ae264278095c280df9e552d4f1bdff2ca.

For each orientation, the repository contains a normalized 64-row treatment plan and a binding template. The verifier checks exact drug, dose, source-plate assignment, A/B complementarity, 24-target coverage, the 8 two-dose and 16 three-dose targets, separate control policy, and exact parity with the public website schedule.

## What remains deliberately unresolved

The prospective templates retain explicit placeholders for device identity, chip compartment, circuit, reservoir, channel, dosing route, exposure duration, readout timepoint, and readout type. These fields must be fixed, reviewed, and hashed before collecting prospective responses.

The existing response-free organ-on-chip compiler checks declared logical compatibility. Both A and B pass when supplied with an invented one-independent-circuit-per-treatment witness, producing 64 treatment actions plus separate vehicle and viability control resources. This proves consistency of the encoded constraints, not device availability, tissue compatibility, flow adequacy, or biological performance.

## Prespecified prospective question

The appropriate next biological test is not another adaptive retrospective sweep. It is a patient-separated, preregistered comparison in which the device-specific execution contract, missingness rule, output denominator, comparator, and success gate are frozen before responses are collected.

The current schedule is therefore a handoff, not a completed chip experiment:

- freeze the real device and control inventory;
- run the constraint compiler;
- commit the exact schedule and hashes;
- collect one orientation under declared QC;
- preserve all missing outputs and adverse slices;
- evaluate the fixed 24-output primary without rescue.

# Reproduction, rights, and limitations

## Public biological reproduction

The public route authenticates the exact Mendeley Data S4 workbook, reconstructs the fixed 119-sample / 59-patient Lib1 TRAIN population from input metadata, and decodes exactly 49,504 selected viability values. It records zero Lib2 numerical-response conversions and zero raw-signal conversions. Broader-study bytes can still exist in workbook internals and are not reinterpreted as selected response access.

The reconstructed TRAIN CSV matches the historical SHA-256 b192dc242362d74c4faa941752792336c7610d9bd403cccbf1cee7a8a1fc7c94. A fresh isolated environment rebuilds plans, fits, and outputs. The current bandwidth replay uses no historical predictions and no old private metadata kit.

```text
python study/hybrid_residual/reproduce_bandwidth.py \
  --curves reconstructed_train/train_curves.csv \
  --output bandwidth_replay \
  --fit-final
```

Final all-TRAIN construction is deployment preparation, not another validation estimate. Generated kernel archives contain fitted training feature vectors and remain private.

## Rights and release boundary

Original code, documentation, and fictional fixtures are MIT-licensed. External papers, source workbooks, and datasets retain their own licenses. The Kryeziu Mendeley Data v3 deposit is listed as CC BY 4.0; this does not relicense every external source used elsewhere in the project. The public repository excludes biological workbooks, private patient arrays, fitted biological weights, and patient-level predictions.

## Evidence hierarchy

1. Same-task development: bandwidth-0.7 benchmark on the reused Lib1 population.
2. Separate adapted-design evidence: matched-CAF pass; FORECAST-1 and eLife failed gates.
3. Failed external primary: Protected22 NOT_ESTIMABLE and fully exposed.
4. Reproducibility evidence: public-source reconstruction and exact replay.
5. Engineering evidence: identity-bound runtime, frozen schedule, compiler, and response-free tests.
6. Prospective evidence: not yet available.

The project does not claim calibrated uncertainty, clinical treatment benefit, prospective organ-on-chip performance, scientist adoption, realized cost or time savings, an official leaderboard score, finalist status, or a guaranteed competition outcome.

# References and verification map

## Primary literature

1. Kryeziu et al. (2026). Patient-derived organoids from metastatic colorectal cancer mirror tumor heterogeneity and predict patient survival and drug sensitivity. Cell Reports Medicine, 102840. DOI: 10.1016/j.xcrm.2026.102840. Public dataset DOI: 10.17632/hr94h42xdc.3.
2. Abdel-Rehim et al. (2026). Drug response profile-based machine learning enables strategic cell line and compound selection for drug development. Bioinformatics, btag293. DOI: 10.1093/bioinformatics/btag293.
3. Xi, Briol and Girolami (2018). Bayesian Quadrature for Multiple Related Integrals. PMLR 80:5373-5382.
4. Longi et al. (2020). Sensor Placement for Spatial Gaussian Processes with Integral Observations. PMLR 124:1009-1018.
5. Farin et al. (2023). Colorectal-cancer organoid and matched-CAF study. Cancer Discovery. DOI: 10.1158/2159-8290.CD-23-0050. Dataset DOI: 10.17632/fypp6xhkjy.1.
6. Tan et al. (2023). FORECAST colorectal-cancer organoid study. Cell Reports Medicine. DOI: 10.1016/j.xcrm.2023.101335.
7. Verissimo et al. (2016). Targeting mutant RAS in patient-derived colorectal-cancer organoids. eLife 5:e18489. DOI: 10.7554/eLife.18489.

## Public verification map

| Claim family | Public artifact |
|---|---|
| Current result and adverse slices | docs/BANDWIDTH_SUCCESSOR.md; evidence/bandwidth_successor_20261003.json |
| All 24 target deltas and selection history | docs/FINALIST_AUDIT.md |
| Public source-to-results route | docs/PUBLIC_REPRODUCTION.md; evidence/r33_public_pipeline.json |
| Protected22 failure and exposure | docs/PROTECTED22_RESULT.md; evidence/PROTECTED22_ACCESS_STATUS.json |
| External adapted-design evidence | docs/STROMA_CONTEXT_CONFIRMATION.md; docs/EXTERNAL_CRC_CONFIRMATION.md; docs/ELIFE_SPARSE_STRESS.md |
| Current runtime lifecycle | docs/BANDWIDTH_LIFECYCLE.md; evidence/bandwidth_lifecycle_20261003.json |
| Frozen treatment schedule | docs/FROZEN_OOC_EXECUTION_MANIFEST.md; evidence/frozen_ooc_execution_schedule_20261003.json |
| Evidence reconciliation | docs/EVIDENCE_LEDGER.md; evidence/EVIDENCE_INDEX.json |
| Release preflight | evidence/release_preflight_frozen_ooc_final_20261003.json |

Run the response-free public release check from the repository root:

```text
python study/audits/release_preflight.py --output release_preflight.json
```

This current report is an additive public artifact. The historical five-page PDF linked from the already accepted entry remains preserved unchanged. No Kaggle page was modified by creating this report.

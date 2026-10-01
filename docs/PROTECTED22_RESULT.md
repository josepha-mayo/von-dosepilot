# Protected22 study: completed execution, unavailable primary

**1 October 2026 | Joseph Ayanda | von DosePilot**

## Decision first

The approved 61-PDO / 31-patient / 22-target execution completed, but **the frozen full-cohort primary is NOT_ESTIMABLE and confirmation did not pass**. All 19,642 authorized response cells were processed once by this runner. Five were nonnumeric. Nothing was imputed; no sample, patient or target was removed to rescue the primary. The complete-patient estimate below is a prespecified secondary analysis, not a replacement primary.

A further limitation was discovered after execution: a newer project-level receipt documented a prior exact22 access to 15 PDOs from 9 of the same planned patients. The coordinator relied on a stale preaccess handoff before reconciling that live record. **This run cannot be described as untouched-cohort confirmation.** Both execution histories and the earlier failed study remain preserved.

## What was tested

The candidate was the frozen final R13 model projected to 22 exactly supported own-drug heads, without fitting or recalibration. Gedatolisib and Palbociclib were excluded in the approved protocol before this run because of the previously identified transfer-support limitations. Each A/B deployment alternative uses 58 distinct physical treatment wells: 30/28 across the plates, with the complementary alternative using 28/30.

The comparator separately optimizes exact-shared-dose log-linear interpolation acquisition on Lib1 TRAIN, then applies a training-only affine calibration with ridge 0.01. It purchases the same 58 wells per alternative. Expected squared losses, not prediction vectors, are averaged across A and B. Endpoints are fixed measured two-plate normalized log-dose AUCs. These are research summaries, not clinical response predictions.

## Results with the correct denominators

| Quantity | Result |
|---|---:|
| Original primary frame | 61 PDOs / 31 patients / 22 targets |
| Authorized response cells / processed | 19,642 / 19,642 |
| Finite numeric / unavailable response cells | 19,637 / 5 |
| PDOs individually complete for all requirements | 59 of 61 |
| Whole patients complete across all their original PDOs | 29 of 31 |
| PDOs belonging to those 29 complete patients | 54 of 61 |
| Primary MSE and primary gate | Not estimable; no pass |

Patient containment matters: the five otherwise complete PDOs belonging to the two incomplete patients are not silently treated as independent complete patients.

On the **prespecified complete-patient conditional population only**:

| Metric | Unchanged R13 subset | Calibrated interpolation |
|---|---:|---:|
| Equal-patient, equal-target expected MSE | 0.0017349427 | 0.0022689547 |
| p90 patient expected RMSE | 0.04786767 | 0.05580595 |

R13 has **23.54% lower conditional MSE**, with 26/29 patient wins, 3 losses and no ties. It is nonworse on **16/22 targets** in this common 29-patient population. The descriptive paired-patient interval for R13-minus-comparator mean loss is **[-0.00071847, -0.00035836]**. This interval describes the selected complete-patient population; it does not establish performance for the missing patients or restore independent validation.

The frozen success rule required an estimable full primary, lower R13 MSE, at least 19/31 patient wins, at least 17/22 nonworse target MSEs, and nonworse p90. The first requirement fails. Even the conditional target count is 16 rather than 17, but conditional results are not a substitute gate calculation.

## Prespecified target-wise missingness report

Each target-wise estimate uses only patients for whom every original PDO is complete for that target. Five targets have 30/31 complete patients; the other 17 have 31/31. These varying-support estimates must not be averaged into a purported full-cohort primary. The complete table is in `evidence/protected22_targetwise_conditional_20261001.csv`.

The five unavailable cells affect 5-FU, Regorafenib, Encorafenib, LGK974 and Napabucasin across two PDO records. Individual physical-cell identities remain in the private execution archive, not the public report.

## Execution integrity and disclosure

User approval was recorded at 2026-10-01 10:01:15 UTC. The numerical-access marker was written at **10:09:04.963264 UTC**; execution completed at **10:09:14.181349 UTC**. The original runner, protocol, model, transfer payload, metadata audit and test log matched their frozen hashes. NumPy was 2.3.5. Seven existing synthetic tests passed before access.

Preflight found that the model-only transfer JSON omitted three integrity-link fields required by the CLI. Before any numerical response access, a separate launch binding added only the existing contract, cohort and preaccess-audit digests. Every transfer parameter remained identical and the runner was not edited. This launch-wiring repair is recorded separately; it is not a repaired numeric rerun.

A second implementation verified the saved arrays with explicit patient loops and Python `math.fsum`. All **83 comparisons** passed, including conditional target metrics, bootstrap endpoints, patient containment, missingness and null-primary status. Eight additional synthetic verification tests passed. These are coordinator-authored software checks, not external peer review or additional biological samples.

The prior project receipt `evidence/lib2_exact22_incomplete_20260930.json`, already present at parent commit `3c3bc651aae38675025d7908b06a3d0b71a79b82`, describes a different protocol that stopped at the first missing response, after up to 4,703 cells may have been accessed. Today's approved protocol instead explicitly continues and reports missingness. Today's results do not repair or erase that earlier failure. The prior access history was discovered too late to support a claim of untouched data for today's analysis.

## Evidence anchors and reproducibility boundary

- Original preaccess ZIP SHA-256: `7e5e16361f4bdcdb6e0d0be6066274c04178065f363a49bdd35163006282f951`.
- Frozen protocol SHA-256: `a51a76729a3699d898ac647b305ba3b1485d16d5808e5ec17f1d3ee95c82ed95`.
- Frozen runner SHA-256: `883382d41840edca22e3861c9625de03e55cf45e32cb2948cfd0dacf4065d98e`.
- Exact private result SHA-256: `064819376c45459f004ccd120b1e081c98037f34520c5aaa6fe71adb326cb39a`.
- Saved prediction SHA-256: `33c2ef441f93c39c111fb4a8eab3a08ef9fb3379b6913e98689175bf966fa3a5`.

The public verifier checks saved arrays without rereading a source workbook or refitting a model. Its synthetic tests run without patient data. Reproducing the actual numerical verification requires the hash-bound private result and prediction files retained by the author; this public addendum alone is not a standalone source-to-results distribution. The existing public Lib1 reproduction route remains separate and unchanged.

All 61/31 records must now be treated as exposed for future project work. No automatic rerun, new untouched subset, model promotion, clinical benefit, full24 validation, or official competition-score improvement is claimed. The accepted Kaggle entry was not duplicated or replaced by this execution.

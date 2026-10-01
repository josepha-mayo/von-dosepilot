# Evidence ledger: what is independent, and what is not

Reconciled 30 September 2026 from the recorded source identities, protocols and execution receipts. This ledger distinguishes studies, reanalyses, incomplete attempts and software reproductions. It does not certify that every historical access across all sessions has been reconstructed.

| Evidence item | Population and task | Proper interpretation |
|---|---|---|
| Original R13 development | 119 organoid samples from 59 patients; 24 drugs; 64 physical treatment wells | Repeated adaptive development. The retained model and historical MSE are unchanged. |
| R33 and comparison replays | Same original population and algorithms | Reproducibility checks, not new cohorts or independent accuracy gains. |
| First eight-drug FORECAST-1 assessment | Separate Tan et al. study; 64 complete community lines from 63 patients used for fitting; 13 complete FORECAST-1 patients of 19 source patients; 21 dose-level readouts | External assessment of an adapted sparse-reconstruction design. The original support gate failed. It does not directly validate the fitted 24-drug R13 model. |
| Later six-drug FORECAST-1 analysis | Same Tan et al. community and FORECAST-1 source workbooks; different panel, budget and eligible population | A further analysis of the same external cohort. It must not be counted as a second independent confirmation or substituted for the first task's failed gate. |
| Matched-CAF stromal assessment | Separate Farin et al. 30-patient-case biobank; 13 development and 15 patient-case-separated confirmation organoids; four drugs; 11 replicate-averaged dose-level readouts | External design assessment under a stromal context change. The four original support criteria passed. A later response-free primary-source audit established zero patient-case overlap under the paper's T/O/F suffix key; it did not create a new score. |
| Calibrated interpolation audit | Reuses the first eight-drug FORECAST predictions and the matched-CAF predictions | Post-hoc stronger-comparator stress test. No new cohort, untouched validation or independent pass. |
| Protected Lib2 exact-shared-22 attempt | Frozen 61-PDO/31-patient frame; 22 exact-supported R13 heads; 58 readouts per deployment alternative | One-shot attempt stopped on a required nonnumeric response before predictions or efficacy metrics. Status is incomplete, not a model loss or successful validation. The no-retry rule remains binding. |
| Public eLife sparse stress test | Separate Verissimo et al. workbook; 12 patient-derived tumor-organoid sheets; five drugs; 13/54 dose-level readouts | Retrospective external stress test of an adapted own-drug sparse-reconstruction procedure. Learned MSE was 30.93% below interpolation, but the fixed gate failed on organoid wins and bootstrap uncertainty. It is not blind confirmation and does not test the original R13 weights. |

## Why the two FORECAST analyses cannot be counted twice

Both use the identical Table S3 community workbook, SHA-256 `dadea8de4da8b67456dd930f13370058e94097a36e8891bc38b4e77affcd92ea`, and Table S7 FORECAST-1 workbook, SHA-256 `9bc3611ba8d45c4ed31ebf28bae0e5ce91b9349bf09f616eefb158e02ec89d63`.

The first eight-drug run's access receipt records **2026-09-30 13:31:00 UTC**. The later six-drug run's attempt receipt records **14:08:14 UTC**, and its own protocol discloses some pre-protocol raw external-row exposure. A statement that a particular session had not previously calculated an external metric cannot override the earlier project-level assessment of the same source cohort.

The different six-drug denominator and measurement budget answer a different question. Its results may be retained as a supplementary analysis, but not added as an extra independent replication and not used to erase incomplete observations or the original gate failure.

## Protected Lib2 status after the exact22 attempt

The historical full24 Lib2 attempt had already failed during import and left a reserved 61-PDO/31-patient frame. A later exact-shared-22 study froze the unchanged 22 supported R13 heads, a 58-readout equal-budget interpolation comparator and a strict no-retry rule. That study also terminated during required-value import, after up to 4,703 selected response cells may have been accessed and **before any prediction vector or efficacy metric existed**.

The project therefore has **no Lib2 efficacy score**. Do not manufacture one by dropping the affected patient, narrowing the target set after the failure, imputing values, or consuming the remaining records as a rescue. See [the exact22 incomplete-study record](LIB2_EXACT22_INCOMPLETE.md).

## Reporting rules

Use separate labels for physical wells, dose-level readouts and replicate-averaged readouts. Do not pool MSEs across different targets, normalization schemes or source cohorts. Distinguish patient-grouped results from organoid-ID-grouped results. The Farin split is now supported as patient-case-separated by the response-free identity audit; its saved metric still averages organoid rows. State missingness denominators and failed gates alongside successful mean errors.

The calibrated-control results narrow the eight-drug FORECAST advantage to 24.42%, with a descriptive paired interval crossing zero. The stromal learned result remains better than both tested interpolation readouts, but its conservative headline remains 43.29% against the better-performing original control.

The public eLife stress test has 30.93% lower mean error than its optimized interpolation control, but only 7/12 organoid wins and a paired interval crossing zero, so its preset stress gate does not pass. See [the calibrated-control audit](CALIBRATED_CONTROL_AUDIT.md) and [the eLife stress test](ELIFE_SPARSE_STRESS.md).

No item in this ledger establishes clinical treatment benefit, prospective organ-on-chip hardware performance, a competition rank, or direct external validation of the original fitted 24-head R13 model.

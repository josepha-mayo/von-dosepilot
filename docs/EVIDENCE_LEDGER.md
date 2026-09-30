# Evidence ledger: what is independent, and what is not

Reconciled 30 September 2026 from the recorded source identities, protocols and execution receipts. This ledger distinguishes studies, reanalyses and software reproductions. It does not certify that every historical access across all sessions has been reconstructed.

| Evidence item | Population and task | Proper interpretation |
|---|---|---|
| Original R13 development | 119 organoid samples from 59 patients; 24 drugs; 64 physical treatment wells | Repeated adaptive development. The retained model and historical MSE are unchanged. |
| R33 and comparison replays | Same original population and algorithms | Reproducibility checks, not new cohorts or independent accuracy gains. |
| First eight-drug FORECAST-1 assessment | Separate Tan et al. study; 64 complete community lines from 63 patients used for fitting; 13 complete FORECAST-1 patients of 19 source patients; 21 dose-level readouts | External assessment of an adapted sparse-reconstruction design. The original support gate failed. It does not directly validate the fitted 24-drug R13 model. |
| Later six-drug FORECAST-1 analysis | Same Tan et al. community and FORECAST-1 source workbooks; different panel, budget and eligible population | A further analysis of the same external cohort. It must not be counted as a second independent confirmation or substituted for the first task's failed gate. |
| Matched-CAF stromal assessment | Separate Farin et al. data; 13 development organoid IDs and 15 distinct confirmation organoid IDs; four drugs; 11 replicate-averaged dose-level readouts | External design assessment under a stromal context change. The four original support criteria passed. Unique-patient independence is not established for every organoid ID. |
| Calibrated interpolation audit | Reuses the first eight-drug FORECAST predictions and the matched-CAF predictions | Post-hoc stronger-comparator stress test. No new cohort, untouched validation or independent pass. |

## Why the two FORECAST analyses cannot be counted twice

Both use the identical Table S3 community workbook, SHA-256 `dadea8de4da8b67456dd930f13370058e94097a36e8891bc38b4e77affcd92ea`, and Table S7 FORECAST-1 workbook, SHA-256 `9bc3611ba8d45c4ed31ebf28bae0e5ce91b9349bf09f616eefb158e02ec89d63`.

The first eight-drug run's access receipt records **2026-09-30 13:31:00 UTC**. The later six-drug run's attempt receipt records **14:08:14 UTC**, and its own protocol discloses some pre-protocol raw external-row exposure. A statement that a particular session had not previously calculated an external metric cannot override the earlier project-level assessment of the same source cohort.

The different six-drug denominator and measurement budget answer a different question. Its results may be retained as a supplementary analysis, but not added as an extra independent replication and not used to erase incomplete observations or the original gate failure.

## Reporting rules

Use separate labels for physical wells, dose-level readouts and replicate-averaged readouts. Do not pool MSEs across different targets, normalization schemes or source cohorts. Distinguish patient-grouped results from organoid-ID-grouped results. State missingness denominators and failed gates alongside successful mean errors.

The current calibrated-control results narrow the eight-drug FORECAST advantage to 24.42%, with a descriptive paired interval crossing zero. The stromal learned result remains better than both tested interpolation readouts, but its conservative headline remains 43.29% against the better-performing original control. See [the calibrated-control audit](CALIBRATED_CONTROL_AUDIT.md).

No item in this ledger establishes clinical treatment benefit, prospective organ-on-chip hardware performance, a competition rank, or direct external validation of the original R13 fitted weights. Protected Lib2 data were not used by this reconciliation or comparator audit.

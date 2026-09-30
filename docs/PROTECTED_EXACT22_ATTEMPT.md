# Protected same-study transfer attempt: failed closed before scoring

30 September 2026. This record describes a **failed one-shot protected-data study**, not a successful validation result. No efficacy score, prediction vector, competition score, or model promotion came from this attempt.

## Why a 22-head study was frozen

DosePilot's submitted R13 procedure has 24 output heads. Metadata-only support analysis showed that a literal full-24 transfer to the protected Lib2 assay is not scientifically supportable: **Gedatolisib** and **Palbociclib** require target support beyond the available Lib2 dose hull. The study therefore refused extrapolation, nearest-dose substitution, or silently redefined targets.

A distinct transfer task was frozen before new protected response access using the other **22 unchanged R13 heads and weights**. Removing the two unsupported own-drug heads leaves **58 of R13's original treatment actions per alternative deployment**, with no refit. A separately optimized interpolation comparator was selected from Lib1 TRAIN only under the same 58-action/22-target class.

This is not called a 64-well full-24 validation.

## Protected frame and minimal access

The exact protected frame was recovered from the sealed R23 campaign ledger: **61 PDO samples from 31 whole patients**, none belonging to the patients touched by the earlier failed Lib2 import.

The endpoint remained the original unclipped two-plate normalized log-dose AUC for each supported target. Metadata proved that every required target node and every candidate/comparator input could be obtained from **322 selected response cells per PDO, 19,642 total**, so no additional response cell had to be opened merely for prediction.

The study explicitly forbade signal values, bridge data, genotype, clinical outcomes, the two unsupported heads, imputation, sample deletion, target deletion, nearest-dose replacement, clipping, and post-result repair.

## Pre-access checks

Before the first protected viability value was requested:

- the exact source workbook, original R13 model, cohort ledger, plans, protocol, footprint and executable code were hash-bound;
- all **16 final unit tests passed**;
- metadata-only preflight bound all **19,642** required cells while converting **zero** protected response values;
- a full invented-response run exercised the 61 x 22 target pipeline, both 61 x 58 acquisition paths, and scoring logic;
- the attempt was frozen as one-shot, with no automatic retry.

The R13 model SHA-256 remained
`779af6df9e3cbb9c7cf91c604e67b3839a20ee7172559be15dcd3915bea1a471`.

## What actually happened

The one allowed numerical attempt stopped at the **4,703rd selected response cell** because a required viability value was nonnumeric.

Under the frozen rules, that makes the primary study **INCOMPLETE**. The program stopped instead of converting the value, dropping the sample, shrinking the target set, substituting a different dose, or scoring a favorable complete-case subset.

Therefore:

| Item | Result |
|---|---|
| Protected prediction vector | **Not produced** |
| Primary 22-target MSE | **Not produced** |
| Comparator MSE | **Not produced** |
| Patient/target promotion gate | **Not evaluated** |
| Retry | **Not permitted** |
| Validation claim | **None** |

This is a data-quality/access failure, not evidence that R13 won or lost.

## Post-failure access accounting

A metadata-only replay of the frozen row order, without rereading any response value, reconstructed how far the one-shot importer had progressed.

The new attempt may have touched selected cells from **15 samples / 9 patients**. It had not reached 46 other samples. **22 whole patients, containing 45 samples, remain wholly unexposed**, but they are not treated as a fresh validation set: running the same study again on the survivors would be sequential salvage after observing a failure and would violate the one-shot protocol.

The earlier 31-patient frame therefore can no longer be described as untouched.

Patient and sample identities are intentionally omitted from this public record.

## Why preserve a failed experiment?

DosePilot is supposed to make measurement identity and unsupported inputs explicit. This attempt tested that behavior on messy real research data. The system refused a scientifically incomplete endpoint before any performance score existed.

That is useful operational evidence for **fail-closed handling of unsupported or nonnumeric measurements**. It is not predictive-validation evidence, and it does not establish clinical value, organ-on-chip performance, laboratory savings, or competition leadership.

The exact aggregate receipt is [here](../evidence/protected_exact22_failure_20260930.json). Private preservation contains the complete frozen protocol, test logs, source hashes, access markers and post-failure ledger; protected response values and patient identities are not published.

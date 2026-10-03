# von DosePilot

**24 research response summaries from 64 traceable treatment wells.**

Research software by **Joseph Ayanda** for AI4S Open Innovation. DosePilot chooses a fixed measurement layout, checks the identity of purchased observations, and reconstructs dose-response curve areas. Original code and fictional fixtures are MIT-licensed. This is not clinical treatment guidance.

## Start with the complete fictional demonstration

On a supported local POSIX system, install the repository's dependencies and run:

```bash
python -m pip install -r requirements.txt
python study/durable_runtime/run_lifecycle_demo.py --output lifecycle_demo_001
```

This example uses **only seeded fictional model parameters and measurements**. It requires no patient data, GPU or model API. Six actual CLI calls demonstrate: committing the inventory, rejecting an incomplete primary request, explicitly recovering 23 older baseline estimates, refusing a changed recorded reading, completing all 24 primary predictions and restoring a lost export copy.

The new interface is `study/durable_runtime/lifecycle.py`, with **commit**, **recover** and **predict** commands. Its primary model still requires all 64 readings. Recovery never imputes a missing value or labels baseline estimates with the newer model's accuracy. [Commands and operating limits](docs/DURABLE_LIFECYCLE_AND_ACQUISITION.md).

## Current verified development benchmark

All three procedures below use the same **119 Lib1 samples, 59 whole patients, 24 targets and 64 physical treatment wells per deployment, 32 per plate**. Complementary A/B squared losses are averaged, not prediction vectors.

| Complete procedure | Patient-balanced MSE, lower is better |
|---|---:|
| Original own-drug R13 | 0.001144858681 |
| S2 spectral correction | 0.001070143945 |
| **Current additive drug-group kernel** | **0.001060552730** |

The additive model improves **45/59 patient means and all five fold means versus S2** and passes the original R13/R18 internal checks. These are **repeated adaptive development results**, not independent biological confirmation, clinical performance or an official contest score.

The latest model challenger, residual-alignment reweighting, reached MSE 0.001060837753—0.0269% worse than additive—with 24/59 patient wins, 2/5 favorable folds and worse p90. It was rejected without follow-up tuning. The earlier acquisition experiment also failed to beat additive. [Additive evidence](docs/STRUCTURED_KERNELS_AND_RECOVERY.md) · [Residual-alignment receipt](evidence/aligned_additive_20261003.json) · [Acquisition result](docs/DURABLE_LIFECYCLE_AND_ACQUISITION.md#1-new-acquisition-experiment-rejected) · [Spectral method](docs/SPECTRAL_SUCCESSOR.md).

## Reproduce and construct the additive model

Follow [the hash-bound public-workbook workflow](docs/PUBLIC_REPRODUCTION.md) to create the exact Lib1 TRAIN CSV and install `study/requirements.txt`. Then:

```bash
python study/hybrid_residual/reproduce_additive.py --curves reconstructed_train/train_curves.csv --output additive_replay --fit-final
```

The public replay runner is available for reconstructing the additive result and fitting final parameters from the hash-bound public input route. This repository does not currently pin a separate aggregate receipt for a completed public-input additive replay, so runner availability is not presented as a new execution result. Construction would not be another validation result. Generated kernel model archives contain fitted training features and must remain private.

Use the new lifecycle with a **fresh code-bound runtime commitment**, an independently recorded construction SHA-256 and an explicit 64-well inventory. It automatically checks recovery history before complete prediction. The legacy entry points remain available but are not silently migrated into this contract.

## Reliability and measured speed

The new runtime publishes complete JSON records without overwriting existing evidence, serializes cooperating processes working on the same measurement frame and recovers after a worker exits. Its compiled prediction calculation was previously measured at **6.9165 to 3.2947 milliseconds per warm request**, a **2.10x speedup** including identity checks but excluding model loading, file I/O, ledger synchronization and training. It is not an end-to-end CLI speedup claim.

**55 durable-runtime tests pass**, including concurrency, process interruption and automatic recovery-history checks. Nine separate new acquisition tests pass, and an independent arithmetic implementation checked 713 numerical/acquisition comparison groups. These are software checks, not additional biological samples.

Run the response-free release preflight—which checks the evidence index, durable runtime, acquisition, structured kernels, residual-alignment unit tests, organ-on-chip constraint compiler and fictional lifecycle demo—with a fresh output path:

```bash
python study/audits/release_preflight.py --output release_preflight.json
```

The latest aggregate [release-preflight receipt](evidence/release_preflight_20261003.json) records 123 orchestrated response-free tests plus the fictional lifecycle demo; two unit tests for the preflight runner itself passed separately.

Local POSIX synchronization and advisory-lock guarantees depend on the operating system and storage. They do not certify physical power-loss behavior, laboratory execution, hostile filesystem edits or network filesystems. [Full verification and limitations](docs/DURABLE_LIFECYCLE_AND_ACQUISITION.md) · [Source-bound receipt](evidence/lifecycle_acquisition_20261002.json).

## External evidence and submission status

The external studies assess adaptations of the sparse-reconstruction design, **not the current additive model's fitted parameters**. The [matched-CAF study](docs/STROMA_CONTEXT_CONFIRMATION.md) passed its original support gate. [FORECAST-1](docs/EXTERNAL_CRC_CONFIRMATION.md) and [eLife](docs/ELIFE_SPARSE_STRESS.md) did not fully pass theirs. [Protected22](docs/PROTECTED22_RESULT.md) had a non-estimable full primary and prior cross-session exposure; [its access status remains exposed](evidence/PROTECTED22_ACCESS_STATUS.json). No new Lib2 responses were used by this release.

The accepted Kaggle entry and submitted video have **not** been replaced by this repository update. The historical video demonstrates the original operating tool, not every new feature:

**Original demo video:** https://youtu.be/QeOGJIgx378

[Prepared writeup](docs/KAGGLE_WRITEUP.md) · [Historical technical PDF](docs/DosePilot_Technical_Report_Public.pdf) · [Evidence ledger](docs/EVIDENCE_LEDGER.md) · [Declared organ-on-chip compiler](docs/OOC_FEASIBILITY.md) · [Complete earlier README, preserved](README_PRE_LIFECYCLE_20261002.md).

No winning probability, prospective laboratory saving, clinical benefit or fresh external validation is claimed. External datasets and papers retain their own rights; see [NOTICE](NOTICE.md) and [LICENSE](LICENSE). No patient arrays or fitted biological weights are included in public commits.

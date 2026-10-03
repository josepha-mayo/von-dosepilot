# von DosePilot

**24 research response summaries from 64 traceable treatment wells.**

Research software by **Joseph Ayanda** for AI4S Open Innovation. DosePilot chooses a fixed measurement layout, checks the identity of purchased observations, and reconstructs dose-response curve areas. Original code and fictional fixtures are MIT-licensed. This is not clinical treatment guidance.

## Start with the complete fictional demonstration

**Live fictional-data demo:** https://von-dosepilot.netlify.app

**One-page finalist audit:** [64-well contract, current benchmark, all 24 target deltas, selection history](docs/FINALIST_AUDIT.md)  
**Synthetic robustness audit:** [noise, plate-drift, and missing-reading stress tests](docs/SIMULATED_ASSAY_ROBUSTNESS.md)

The deployed static site is also versioned under [`site/`](site/) in this repository. It uses seeded fictional values only and makes no additional biological accuracy claim.

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
| Previous additive drug-group kernel | 0.001060552730 |
| **Current bandwidth-0.7 additive successor** | **0.001058275042** |

The bandwidth successor changes only the drug-group Gaussian lengthscale from 1.0 to **0.7**. It improves **38/59 patient means versus the previous additive model, all 5/5 outer-fold means, and p90 patient RMSE**, while preserving the exact same physical plans. It is **7.56% lower MSE than R13** and **7.28% lower than R18**, with 49/59 and 47/59 patient wins respectively. These are **repeated adaptive development results**, not independent biological confirmation, clinical performance or an official contest score.

The wider 1.4 bandwidth failed, and ten of 24 target means still regress versus the previous additive model. Earlier residual-alignment and acquisition challengers were also rejected and remain public. [Bandwidth successor](docs/BANDWIDTH_SUCCESSOR.md) · [Aggregate receipt](evidence/bandwidth_successor_20261003.json) · [Previous additive evidence](docs/STRUCTURED_KERNELS_AND_RECOVERY.md) · [Residual-alignment receipt](evidence/aligned_additive_20261003.json) · [Acquisition result](docs/DURABLE_LIFECYCLE_AND_ACQUISITION.md#1-new-acquisition-experiment-rejected).

## Reproduce and construct the current successor

Follow [the hash-bound public-workbook workflow](docs/PUBLIC_REPRODUCTION.md) to create the exact Lib1 TRAIN CSV and install `study/requirements.txt`. Then:

```bash
python study/hybrid_residual/reproduce_bandwidth.py --curves reconstructed_train/train_curves.csv --output bandwidth_replay --fit-final
```

The public replay runner has reproduced the bandwidth-successor, previous additive and R13 scores from the hash-bound public-derived TRAIN input without historical predictions. Final construction selected spectral fraction 0.1 and ridge 1.0. Construction is not another validation result. Generated kernel model archives contain fitted training features and must remain private.

The promoted bandwidth-0.7 archive has an identity-checked all-input inference backend, but it is **not yet integrated** into the durable `commit` / `recover` / `predict` CLI. That lifecycle currently targets the previous additive-1.0 model. Do not present a predecessor lifecycle run as operation of the bandwidth successor. The legacy entry points remain available but are not silently migrated into the durable contract.

## Reliability and measured speed

The previous additive-1.0 runtime publishes complete JSON records without overwriting existing evidence, serializes cooperating processes working on the same measurement frame and recovers after a worker exits. Its compiled prediction calculation was measured at **6.9165 to 3.2947 milliseconds per warm request**, a **2.10x speedup** including identity checks but excluding model loading, file I/O, ledger synchronization and training. This speed result does not describe the bandwidth-0.7 backend and is not an end-to-end CLI speedup claim.

**55 durable-runtime tests pass**, including concurrency, process interruption and automatic recovery-history checks. Nine separate new acquisition tests pass, and an independent arithmetic implementation checked 713 numerical/acquisition comparison groups. These are software checks, not additional biological samples.

Run the response-free release preflight—which checks the evidence index, durable runtime, bandwidth successor, acquisition, structured kernels, residual-alignment unit tests, organ-on-chip constraint compiler and fictional lifecycle demo—with a fresh output path:

```bash
python study/audits/release_preflight.py --output release_preflight.json
```

The latest aggregate [bandwidth-release preflight receipt](evidence/release_preflight_bandwidth_20261003.json) records 129 orchestrated response-free tests plus the fictional lifecycle demo; three unit tests for the preflight runner itself passed separately.

Local POSIX synchronization and advisory-lock guarantees depend on the operating system and storage. They do not certify physical power-loss behavior, laboratory execution, hostile filesystem edits or network filesystems. [Full verification and limitations](docs/DURABLE_LIFECYCLE_AND_ACQUISITION.md) · [Source-bound receipt](evidence/lifecycle_acquisition_20261002.json).

## External evidence and submission status

The external studies assess adaptations of the sparse-reconstruction design, **not the current additive model's fitted parameters**. The [matched-CAF study](docs/STROMA_CONTEXT_CONFIRMATION.md) passed its original support gate. [FORECAST-1](docs/EXTERNAL_CRC_CONFIRMATION.md) and [eLife](docs/ELIFE_SPARSE_STRESS.md) did not fully pass theirs. [Protected22](docs/PROTECTED22_RESULT.md) had a non-estimable full primary and prior cross-session exposure; [its access status remains exposed](evidence/PROTECTED22_ACCESS_STATUS.json). No new Lib2 responses were used by this release.

The accepted Kaggle entry and submitted video have **not** been replaced by this repository update. The historical video demonstrates the original operating tool, not every new feature:

**Original demo video:** https://youtu.be/QeOGJIgx378

[Prepared writeup](docs/KAGGLE_WRITEUP.md) · [Historical technical PDF](docs/DosePilot_Technical_Report_Public.pdf) · [Evidence ledger](docs/EVIDENCE_LEDGER.md) · [Declared organ-on-chip compiler](docs/OOC_FEASIBILITY.md) · [Complete earlier README, preserved](README_PRE_LIFECYCLE_20261002.md).

No winning probability, prospective laboratory saving, clinical benefit or fresh external validation is claimed. External datasets and papers retain their own rights; see [NOTICE](NOTICE.md) and [LICENSE](LICENSE). No patient arrays or fitted biological weights are included in public commits.

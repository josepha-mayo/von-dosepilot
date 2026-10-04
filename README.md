# von DosePilot

**24 research response summaries from 64 traceable treatment wells.**

Research software by **Joseph Ayanda** for AI4S Open Innovation. DosePilot chooses a fixed measurement layout, checks the identity of purchased observations, and reconstructs dose-response curve areas. Original code and fictional fixtures are MIT-licensed. This is not clinical treatment guidance.

## Start with the complete fictional demonstration

**Live fictional-data demo:** https://von-dosepilot.netlify.app

**Downloadable state-bound evidence:** expand **Inspect full evidence record** in the live demo, then download the exact digest-only JSON shown there. The [export contract and verification](docs/LIVE_DEMO_TRACE_EXPORT.md) explain what is included and explicitly excluded.

**One-page finalist audit:** [64-well contract, current benchmark, all 24 target deltas, selection history](docs/FINALIST_AUDIT.md)  
**Synthetic robustness audit:** [noise, plate-drift, and missing-reading stress tests](docs/SIMULATED_ASSAY_ROBUSTNESS.md)

**Current-model lifecycle:** [bandwidth-0.7 commit, recover and predict](docs/BANDWIDTH_LIFECYCLE.md)

**Frozen prospective schedule:** [exact 64-treatment A/B manifests with device binding still explicitly unresolved](docs/FROZEN_OOC_EXECUTION_MANIFEST.md)

The deployed static site is also versioned under [`site/`](site/) in this repository. It uses seeded fictional values only and makes no additional biological accuracy claim.

On a supported local POSIX system, install the repository's dependencies and run:

```bash
python -m pip install -r requirements.txt
python study/durable_runtime/run_bandwidth_lifecycle_demo.py --output bandwidth_lifecycle_demo_001
```

This example uses **only seeded fictional model parameters and measurements**. It requires no patient data, GPU or model API. Six actual CLI calls demonstrate: committing the inventory, rejecting an incomplete primary request, explicitly recovering 23 older baseline estimates, refusing a changed recorded reading, completing all 24 primary predictions and restoring a lost export copy.

The current-model interface is `study/durable_runtime/bandwidth_lifecycle.py`, with **commit**, **recover** and **predict** commands. Its primary model requires all 64 readings. Recovery never imputes a missing value or labels historical own-drug estimates with the newer model's accuracy. The previous additive-1.0 lifecycle remains preserved separately. [Current lifecycle](docs/BANDWIDTH_LIFECYCLE.md) · [historical lifecycle and limits](docs/DURABLE_LIFECYCLE_AND_ACQUISITION.md).

## Current verified development benchmark

All four procedures below use the same **119 Lib1 samples, 59 whole patients, 24 targets and 64 physical treatment wells per deployment, 32 per plate**. Complementary A/B squared losses are averaged, not prediction vectors.

| Complete procedure | Patient-balanced MSE, lower is better |
|---|---:|
| Original own-drug R13 | 0.001144858681 |
| S2 spectral correction | 0.001070143945 |
| Previous additive drug-group kernel | 0.001060552730 |
| **Current bandwidth-0.7 additive successor** | **0.001058275042** |

The bandwidth successor changes only the drug-group Gaussian lengthscale from 1.0 to **0.7**. It improves **38/59 patient means versus the previous additive model, all 5/5 outer-fold means, and p90 patient RMSE**, while preserving the exact same physical plans. It is **7.56% lower MSE than R13** and **7.28% lower than R18**, with 49/59 and 47/59 patient wins respectively. These are **repeated adaptive development results**, not independent biological confirmation, clinical performance or an official contest score.

The wider 1.4 bandwidth failed, and ten of 24 target means still regress versus the previous additive model. Earlier residual-alignment and acquisition challengers were also rejected and remain public. [Bandwidth successor](docs/BANDWIDTH_SUCCESSOR.md) · [Aggregate receipt](evidence/bandwidth_successor_20261003.json) · [Previous additive evidence](docs/STRUCTURED_KERNELS_AND_RECOVERY.md) · [Residual-alignment receipt](evidence/aligned_additive_20261003.json) · [Acquisition result](docs/DURABLE_LIFECYCLE_AND_ACQUISITION.md#1-new-acquisition-experiment-rejected).

For each fixed bandwidth, the residual spectral option is selected inside the inner patient folds. Bandwidth 0.7 itself was then selected from the prefrozen `{1.0, 0.7, 1.4}` menu after comparing reused outer-fold development results. The displayed bandwidth-0.7 MSE is therefore a **post-selection development point estimate**, not an unbiased nested estimate of a bandwidth-selecting procedure.

## Reproduce and construct the current successor

Follow [the hash-bound public-workbook workflow](docs/PUBLIC_REPRODUCTION.md) to create the exact Lib1 TRAIN CSV and install `study/requirements.txt`. Then:

```bash
python study/hybrid_residual/reproduce_bandwidth.py --curves reconstructed_train/train_curves.csv --output bandwidth_replay --fit-final
```

The public replay runner has reproduced the bandwidth-successor, previous additive and R13 scores from the hash-bound public-derived TRAIN input without historical predictions. Final construction selected spectral fraction 0.1 and ridge 1.0. Construction is not another validation result. Generated kernel model archives contain fitted training features and must remain private.

The promoted bandwidth-0.7 archive now has a dedicated durable `commit` / `recover` / `predict` CLI. The adapter requires the exact bandwidth model kind and scalar multiplier `0.7`, binds its runtime sources into each receipt, and rejects historical additive-1.0 artifacts. The old lifecycle remains available for old commitments and is never silently migrated. The public repository still excludes fitted biological weights; users construct those privately from the source-bound reproduction route.

## Reliability and measured speed

The bandwidth-0.7 lifecycle publishes complete JSON records without overwriting existing evidence, serializes cooperating processes working on the same measurement frame, rejects a changed recorded value and recovers a lost export. **65 durable-runtime tests pass**, including ten current-model adapter tests and all preserved historical cases. The previous additive-1.0 compiled calculation was measured at **6.9165 to 3.2947 milliseconds per warm request**, a **2.10x speedup** including identity checks but excluding model loading, file I/O, ledger synchronization and training. That speed result does not describe the bandwidth-0.7 backend and is not an end-to-end CLI speedup claim.

Nine separate acquisition tests pass, and an independent arithmetic implementation checked 713 numerical/acquisition comparison groups. These are software checks, not additional biological samples.

Run the response-free release preflight—which checks the evidence index, durable runtime, bandwidth successor, acquisition, structured kernels, residual-alignment unit tests, organ-on-chip constraint compiler, frozen schedule/public-display parity and fictional lifecycle demo—with a fresh output path:

```bash
python -m pip install -r study/requirements.txt
python study/audits/release_preflight_current.py --output release_preflight.json
```

The latest aggregate current-release receipt records **14 completed stages and 173 orchestrated response-free tests**, including seven schedule-tamper tests, exact public-display parity, endpoint-definition checks, Kaggle-link portability, development-search governance, current-quickstart checks, the preserved predecessor demo and the bandwidth-0.7 fictional lifecycle demo. The earlier report-bound 168-test receipt and older 157-test receipt remain immutable historical evidence; their lower totals reflect the test families present when those artifacts were built, not failed tests. Three unit tests for the current preflight runner passed separately. The canonical current receipt and [verification chronology](docs/VERIFICATION_CHRONOLOGY.md) are recorded in [the evidence index](evidence/EVIDENCE_INDEX.json).

Local POSIX synchronization and advisory-lock guarantees depend on the operating system and storage. They do not certify physical power-loss behavior, laboratory execution, hostile filesystem edits or network filesystems. [Full verification and limitations](docs/DURABLE_LIFECYCLE_AND_ACQUISITION.md) · [Source-bound receipt](evidence/lifecycle_acquisition_20261002.json).

## External evidence and submission status

The external studies assess adaptations of the sparse-reconstruction design, **not the current additive model's fitted parameters**. The [matched-CAF study](docs/STROMA_CONTEXT_CONFIRMATION.md) passed its original support gate. [FORECAST-1](docs/EXTERNAL_CRC_CONFIRMATION.md) and [eLife](docs/ELIFE_SPARSE_STRESS.md) did not fully pass theirs. [Protected22](docs/PROTECTED22_RESULT.md) had a non-estimable full primary and prior cross-session exposure; [its access status remains exposed](evidence/PROTECTED22_ACCESS_STATUS.json). No new Lib2 responses were used by this release.

The accepted Kaggle entry and submitted video have **not** been replaced by this repository update. The historical video demonstrates the original operating tool, not every new feature:

**Original demo video:** https://youtu.be/QeOGJIgx378

[Prepared writeup](docs/KAGGLE_WRITEUP.md) · [Historical technical PDF](docs/DosePilot_Technical_Report_Public.pdf) · [Evidence ledger](docs/EVIDENCE_LEDGER.md) · [Declared organ-on-chip compiler](docs/OOC_FEASIBILITY.md) · [Complete earlier README, preserved](README_PRE_LIFECYCLE_20261002.md).

No winning probability, prospective laboratory saving, clinical benefit or fresh external validation is claimed. External datasets and papers retain their own rights; see [NOTICE](NOTICE.md) and [LICENSE](LICENSE). No patient arrays or fitted biological weights are included in public commits.

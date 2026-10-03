# von DosePilot: unified durable workflow and acquisition result

**Joseph Ayanda | 2 October 2026 | Research software**

> **Historical 2 October snapshot.** The bandwidth-0.7 successor became the current repeated-development incumbent on 3 October. The durable lifecycle and 2.10× warm-step measurement documented here still target the previous additive-1.0 model; they are not a runtime claim for the bandwidth successor. See [the current result](BANDWIDTH_SUCCESSOR.md).

## What changes, and what does not

At the time of this snapshot, the additive-1.0 model was the accuracy incumbent at **patient-balanced MSE 0.001060552730112811**. A new, fitting-only dose-selection procedure failed to improve it and is rejected. Neither the accepted Kaggle entry nor the biological model weights were replaced by this release.

The completed engineering change is one explicit runtime interface for **commit, recover and predict**. It combines the previously verified faster additive predictor with durable evidence-file publication, automatic recovery-history checks and per-frame process serialization. Users no longer need to remember a special completion command to prevent previously recorded readings from being rewritten.

The older separate entry points remain unchanged. This new interface requires a fresh, code-bound runtime commitment and is tested for local POSIX filesystems. It does not silently reinterpret old ledger records or turn a repeated assay into a new biological observation.

## 1. New acquisition experiment: rejected

The experiment kept the same **119 Lib1 samples, 59 whole patients, 24 original unclipped targets, 64 distinct physical treatment wells per deployment and 32 wells per plate**. Complementary A/B layouts remain alternatives; their squared losses are averaged, never their prediction vectors.

Inside each fitting slice, the candidate started from the original R13 measurement plan and changed only which concentrations occupy each target's existing two or three positions. It performed one deterministic target-by-target sweep, minimizing a regularized multioutput covariance proxy. A Schur-complement calculation evaluated replacements efficiently. Acquisition, means, scales, kernels and model parameters were rebuilt separately within every fitting fold; no outer-fitted plan was reused to score its inner validation rows.

The two prefrozen arms were a forced use of this new plan and an inner-only selector that could retain the original plan. Both retained the original ten spectral options and the fixed patient folds.

| Procedure | Patient-balanced MSE | p90 patient RMSE | Decision |
|---|---:|---:|---|
| **Current additive model** | **0.001060552730** | **0.038073112** | Retain |
| Forced multioutput acquisition sweep | 0.001066543400 | 0.039398494 | Reject |
| Inner-only old/new plan selector | 0.001060552730 | 0.038073112 | No improvement; retain original |

The forced sweep increases MSE by **0.5649%**, improves only **21/59 patient averages** and two of five fold means, and worsens p90. It changes dose subsets for 8 to 11 targets in the outer fitting plans. The training proxy decreases as designed, but that does not imply better held-patient prediction.

The selector chooses the existing acquisition in every outer fold and reproduces all 59 patient losses exactly. This is a useful rejection by the model-selection procedure, not a new accuracy gain. The forced arm also fails the original R13/R18 patient-breadth requirements. The thresholds were not relaxed.

Nine synthetic tests passed before fitting. A separately written audit checked **713 comparison groups**, including **480 direct full-system evaluations of selected acquisition steps** across 20 fitting contexts. Ten saved selected model artifacts reloaded with maximum prediction difference **2.22e-16**. The audit checks selected steps, not every possible acquisition candidate in the search space.

The run used an authenticated copy of the historical private Lib1 TRAIN kit, not a newly downloaded workbook. Its code, protocol and aggregate results are public; exact numerical replay and the saved-array verifier require the retained input cache and historical R18 artifact. The pre-existing public CSV reconstruction path remains separate. These are repeatedly reused adaptive development results, not independent confirmation.

## 2. One consistent lifecycle, with no silent downgrade

The new `study/durable_runtime/lifecycle.py` interface has three commands:

**Commit** binds a caller-declared inventory to one model, one plan, a sample/run, one A/B alternative, exact drugs and concentrations, physical well labels and separately declared controls. Runtime implementation and source-file hashes are part of the commitment.

**Recover** is explicit and requires `--acknowledge-baseline-only`. With one identified null reading, it returns 23 complete **older own-drug baseline** estimates, withholds the affected head and produces **zero additive-model predictions**. It does not impute or call the global correction with incomplete input.

**Predict** requires all 64 readings. When recovery records exist, it automatically verifies that previously observed values have not changed before generating the complete additive prediction. A changed earlier reading is rejected before a primary result is written. There is no separate optional completion command to remember within this interface.

Recovery and primary results keep distinct labels and evidence records. The primary model's headline accuracy is never attached to fallback estimates. This does not rescue the earlier incomplete Protected22 study, change that study's denominator or authorize missing-value imputation.

## 3. Concurrent workers and interrupted writes

Each lifecycle operation holds a local POSIX advisory lock for its measurement frame while reading history and publishing results. Cooperating workers cannot concurrently create conflicting recovery branches. A second active worker receives `FRAME_BUSY_RETRY_LATER`. Different frames can proceed independently.

Locks are held by the operating system, not by the presence of a marker file. A process killed while holding a lock releases it; the persistent lock filename does not need deletion or imply an active job. The implementation checks that lock files are regular, unlinked to other paths and not symbolic links.

Evidence JSON is staged privately in the destination directory, completely written and synchronized before its final name is created with an exclusive hard link. The destination is never overwritten. Interruptions before publication leave no partial canonical JSON; interruptions after publication leave a complete record from which a missing exported copy can be restored. Pending staging names are not authoritative evidence.

These are local-filesystem, cooperating-process guarantees. They do not prevent a person or a noncooperating legacy program from editing or deleting files. Network filesystems and unsupported operating systems are outside the tested contract. Process-interruption tests do not certify physical power-loss behavior of disks, batteries, operating systems or storage controllers.

## 4. Previously completed speed improvement, now integrated

A prior completed branch had already compiled the fitted additive-kernel correction algebraically, without refitting, quantization or model approximation. This release recovers and integrates that implementation rather than counting its earlier run again.

Nine alternating paired warm timing rounds on the author's Linux laptop measured:

| Prediction implementation | Median time per request |
|---|---:|
| Original additive calculation | 6.9165 ms |
| Compiled additive calculation | 3.2947 ms |

That is **2.0993x faster**, or **52.37% less time**, for the measured warm prediction step, including identity checks. It excludes loading the model, disk I/O, ledger synchronization and training. It is **not** an end-to-end CLI speedup claim.

The same fitted artifact had been checked on 238 existing sample/orientation requests, with maximum prediction difference **2.22e-16**. The implementations are numerically equivalent, not bit-identical: arithmetic ordering changed. Their implementation identities remain distinct in evidence records, so existing results are not silently overwritten.

## 5. Tests and actual-artifact check

The full durable-runtime suite now passes **55 tests**, comprising the earlier 34 engineering cases and 21 new lock/lifecycle cases. The new tests include concurrent conflicting recoveries, death of a lock holder, explicit fallback acknowledgement, missing-input rejection, automatic observation-history enforcement, old-commitment rejection, interruption before/after publication, and exact export restoration.

Together with the nine new acquisition tests, this turn adds **30 new synthetic test cases**. The repeated execution of a test on another machine is not another unique case, and these test counts are not biological sample counts.

A separate end-to-end check used one previously saved complete Lib1 request and the existing final additive model. It verified a fresh commitment, incomplete-primary rejection, 23 baseline-only outputs, automatic refusal to rewrite an observed value, proper completion to 24 primary outputs, and byte-identical restoration of a deleted export copy. The complete primary values differed from the original additive backend by at most **1.11e-16**; the available baseline values matched direct arithmetic exactly in this case. No fitting or original-workbook read was involved. Control reservations in this test were fictional.

## 6. Run the complete fictional demonstration

From a repository checkout on a supported local POSIX system with its NumPy dependency installed:

```bash
python study/durable_runtime/run_lifecycle_demo.py --output lifecycle_demo_001
```

The demo runs six actual CLI invocations. It commits a fictional inventory, rejects an incomplete primary request, produces a separately labelled 23-head baseline recovery, rejects a changed old reading, completes the primary prediction and restores a missing output copy. `SUMMARY.json` and `CLI_TRANSCRIPT.json` record the outcomes. All model parameters and measurements in the example are seeded fictional fixtures. No patient data, network download, GPU or paid API is required.

For real author-side model artifacts, invoke the same entry point with `commit`, `recover` or `predict`. Supply the model directory, an independently recorded construction SHA-256, the ledger directory and commitment path each time. `commit` additionally takes `--inventory` and `--template`; the other commands take `--measurements` and `--output`. Only `recover` accepts and requires `--acknowledge-baseline-only`.

## Evidence and release boundary

The companion receipt `evidence/lifecycle_acquisition_20261002.json` records exact source, protocol, prediction and verification hashes, including the provenance of the earlier timing result. Public code and aggregate evidence contain no patient arrays, fitting-feature kernel archives or biological model weights. The author's private recovery package is separate.

No Lib2 or other external confirmation responses were read. Lib2 remains exposed; its unavailable primary remains unavailable. No existing accepted Kaggle entry, registration or video was changed. No competitor score, winning probability, prospective laboratory saving or clinical benefit is claimed.

The correct numerical benchmark remains **0.001060552730112811**. The progress in this release is a safer and more consistent operational path, an integrated measured prediction-speed improvement, and a fully checked negative acquisition result that protects that benchmark.

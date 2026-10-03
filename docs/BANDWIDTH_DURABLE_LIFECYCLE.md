# Bandwidth-0.7 durable lifecycle

**Joseph Ayanda | 3 October 2026 | engineering/reproducibility evidence**

The current bandwidth-0.7 development model now has its own durable **commit → recover → predict** runtime adapter.

This does **not** change model accuracy, refit the model, or reinterpret any existing additive-1.0 commitment. The predecessor lifecycle remains a separate historical runtime contract.

## Why a separate lifecycle

The verified current model has model kind:

`dosepilot.additive_kernel_bandwidth.v1`

The earlier durable lifecycle was built for:

`dosepilot.additive_kernel.v1`

Those model families share the same physical plan and own-drug baseline, but they are not the same fitted predictor. Reusing an old commitment silently would weaken evidence provenance.

The new adapter therefore uses a new policy:

`dosepilot.bandwidth_durable_complete_lifecycle.v1`

and runtime implementation identifier:

`dosepilot.bandwidth_durable.v1`.

A fresh commitment binds the current construction hash, model hash, plan hash, runtime code hashes, sample/run identity, one A/B orientation, exact 64 treatment wells, and declared controls.

## Commit

After constructing the frozen bandwidth model with the public replay:

```bash
python study/hybrid_residual/reproduce_bandwidth.py \
  --curves reconstructed_train/train_curves.csv \
  --output bandwidth_replay \
  --fit-final
```

record the SHA-256 of `bandwidth_replay/final_model/CONSTRUCTION.json` independently, then:

```bash
python study/durable_runtime/bandwidth_lifecycle.py commit \
  --model-dir bandwidth_replay/final_model \
  --construction-sha256 <trusted-construction-sha256> \
  --ledger-dir bandwidth_ledger \
  --commitment committed_plan.json \
  --inventory inventory.json \
  --template measurements_to_fill.json
```

The inventory must still declare exactly 64 treatment measurements, 32 per source plate, plus separate vehicle and viability controls.

## Predict

With all 64 committed treatment readings present:

```bash
python study/durable_runtime/bandwidth_lifecycle.py predict \
  --model-dir bandwidth_replay/final_model \
  --construction-sha256 <trusted-construction-sha256> \
  --ledger-dir bandwidth_ledger \
  --commitment committed_plan.json \
  --measurements completed_measurements.json \
  --output bandwidth_prediction.json
```

The primary result contains 24 predictions from the bandwidth-0.7 model.

A missing, nonfinite, substituted, duplicated, wrong-dose, wrong-drug, or wrong-plate treatment measurement prevents the primary prediction.

## Explicit baseline-only recovery

If one or more required readings are unavailable, the operator may explicitly request:

```bash
python study/durable_runtime/bandwidth_lifecycle.py recover \
  --model-dir bandwidth_replay/final_model \
  --construction-sha256 <trusted-construction-sha256> \
  --ledger-dir bandwidth_ledger \
  --commitment committed_plan.json \
  --measurements incomplete_measurements.json \
  --output baseline_only.json \
  --acknowledge-baseline-only
```

This does **not** run an incomplete bandwidth model.

It returns zero bandwidth primary outputs. Where a target's older own-drug baseline has all of its own two or three required readings, that older baseline estimate may be exposed under a separate `BASELINE_ONLY` label. The affected target stays withheld.

No missing value is imputed, and no free replacement treatment well is created.

## Completing a recovered frame

When the missing reading later becomes available, the ordinary `predict` command checks existing recovery records automatically before generating the primary bandwidth result.

If any previously observed value was changed or removed, completion is rejected.

This protects against silently rewriting history between a baseline-only recovery and the later complete primary result.

## Verification

Eight new fictional bandwidth-lifecycle tests pass on top of the previous 55 durable-runtime cases:

- model/runtime receipt binding;
- exact complete prediction parity;
- explicit one-missing baseline-only recovery;
- required recovery acknowledgement;
- observation-history enforcement;
- recovery-to-primary completion;
- old additive lifecycle rejection of the bandwidth model;
- wrong model-family rejection.

The complete durable-runtime suite therefore passes **63 tests**.

The constructed final bandwidth model was also checked through the new lifecycle using one already saved Lib1 request and a fresh ledger:

| Check | Result |
|---|---:|
| Complete primary outputs | 24 |
| Maximum difference vs direct bandwidth backend | **0.0** |
| One-missing bandwidth primary outputs | 0 |
| Available older baseline-only outputs | 23 |
| Later complete bandwidth outputs | 24 |

The actual-model check used existing saved training-record values. It did not refit a model, read a new source response, or create independent validation evidence.

## Important boundaries

- The old additive-1.0 lifecycle source remains unchanged.
- Old commitments are not migrated to the bandwidth model.
- The earlier **2.10x compiled prediction speedup applies to additive-1.0**, not to this bandwidth runtime. No bandwidth speed claim is made.
- POSIX advisory locking coordinates cooperating local processes; it does not prevent hostile/manual filesystem edits or certify network filesystems.
- Durable JSON publication improves software evidence handling but does not certify physical power-loss behavior of every storage device.
- Caller-declared inventory identities do not prove a laboratory physically performed the declared measurement.
- This is engineering evidence, not biological validation or clinical software.

Machine-readable verification is in `evidence/bandwidth_lifecycle_20261003.json`.

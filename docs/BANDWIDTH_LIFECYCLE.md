# Bandwidth-0.7 durable lifecycle

The current repeated-development incumbent now has its own explicit
`commit` / `recover` / `predict` path. This closes the earlier mismatch in
which the accuracy headline described bandwidth 0.7 while the durable CLI
could operate only the previous bandwidth-1.0 model.

This is an engineering and reproducibility result. It is not another model
fit, biological cohort, accuracy result, clinical system or laboratory
execution certificate.

## Run the data-free demonstration

```bash
python study/durable_runtime/run_bandwidth_lifecycle_demo.py \
  --output fictional_bandwidth_lifecycle_001
```

The demonstration creates a seeded fictional bandwidth-0.7 model and makes
six real CLI calls. It:

1. commits exactly 64 identified treatment wells, 32 per source plate;
2. withholds all 24 primary outputs when one required value is missing;
3. exposes 23 separately labelled historical own-drug baseline estimates;
4. rejects a change to an already recorded measurement;
5. completes all 24 bandwidth-0.7 outputs when the missing reading arrives;
6. restores a deleted user-facing export byte-identically from the ledger.

The current entry point is:

```bash
python study/durable_runtime/bandwidth_lifecycle.py commit ...
python study/durable_runtime/bandwidth_lifecycle.py recover ...
python study/durable_runtime/bandwidth_lifecycle.py predict ...
```

The model directory must contain a constructed
`dosepilot.additive_kernel_bandwidth.v1` artifact with an exact scalar
`kernel_bandwidth_multiplier` of `0.7`. The construction document, model,
plan, runtime sources, lifecycle sources and external construction trust
anchor are bound into each commitment receipt. A historical additive-1.0
artifact or any other multiplier is rejected rather than silently adapted.

The earlier additive lifecycle remains available for its historical model and
receipts. Existing commitments are not migrated. The current bandwidth path
uses the identity-checked reference kernel implementation; the separately
reported 2.10x compiled warm-step speed result still applies only to the
previous additive-1.0 backend.

## Verified boundary

Ten new bandwidth-lifecycle tests cover direct numerical parity with the
bandwidth backend, wrong-family and wrong-multiplier rejection, all 64
single-missing positions, explicitly labelled recovery, observation-history
enforcement, completion after recovery, byte-identical export restoration and
non-mutation of the old lifecycle. Together with the preserved historical
runtime suite, 65 durable-runtime tests pass.

The local evidence files are create-exclusive, synchronized and private on
the tested POSIX filesystem. They are not signed, WORM, administrator-immutable
or proof that a supplied number physically came from the declared well.
Controls and inventory remain caller-declared. No actual organ-on-chip run,
prospective saving, calibrated assay-QC threshold or clinical benefit is
established.

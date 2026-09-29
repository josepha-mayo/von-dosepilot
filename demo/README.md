# von DosePilot: recover the committed experiment

This example contains wholly invented parameters, identifiers and measurements. It is not an organoid accuracy study. The original R21 predictor file is unchanged.

## Run

Use Python 3.11+ and NumPy. The current container test uses its existing dependencies; a fresh installation is not asserted.

```bash
python run_recovery_demo.py --output new_recovery_demo
```

The first command DELIBERATELY fails to write an output plan after committing it. The recovery command restores that same plan and a blank measurement template from the intact ledger. It does not choose another orientation, change a nonce, read a new measurement or reset the ledger. It then verifies 24 complete predictions and 23 predictions plus one missing-head abstention.

Inspect `COMMANDS.json`, `recovered/RECOVERY_RECEIPT.json`, the two prediction files and `DEMO_RESULT.json`. All files are private/local. No network service or language-model API is called.

## Recover a real, already committed plan

```bash
python recover_plan.py --model PATH_TO_MODEL.json --model-sha256 TRUSTED_SHA256 --ledger PATH_TO_LEDGER --sample-id EXACT_SAMPLE --run-id EXACT_RUN --output NEW_RECOVERY_DIRECTORY
```

The original plan must already exist and verify against the supplied model trust anchor. Wrong identities and corrupt commitments fail; this does not reconstruct an absent or damaged ledger. Recovered templates contain nulls, not guessed or reconstructed observations. A failed export leaves its original commitment available; a new recovery uses a different output directory, never a different experimental layout.

## Limits

This is application-level traceability, not proof of laboratory execution, tamper-proof storage, protection from a dishonest caller resetting identifiers, calibrated uncertainty or clinical validation. No biological weights or patient examples are included. The added extension, tests and report are coordinator-authored. Separate reviewer requests were blocked before execution; no independent review pass is claimed. Code license and public release remain project-owner decisions.

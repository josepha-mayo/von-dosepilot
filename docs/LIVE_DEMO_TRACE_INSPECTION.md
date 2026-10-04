# Inspectable browser trace and digest correction

The live fictional workflow now exposes a keyboard- and touch-accessible **Inspect full evidence record** disclosure. It shows the complete SHA-256 values and explicit `null` fields for evidence that does not yet exist.

## Why this release was necessary

The preceding trace release displayed shortened digests and stored complete values only in hover titles. Its versioned evidence receipt recorded the baseline-result digest with the correct visible prefix and suffix but an incorrect middle segment. The application and its independent digest calculation were correct; the error was in the coordinator-authored receipt and a verifier constant copied from that receipt. Because the executable harness checked its own arithmetic but did not emit the complete computed digests, the receipt/verifier agreement did not expose the discrepancy.

The incorrect predecessor receipt remains immutable. This release corrects the record rather than rewriting history.

## Corrected contract

The independent Node harness now reads the exact public `site/frozen_schedule.js`, reconstructs all canonical browser payloads, and emits the four complete computed digests:

- plan;
- historical baseline result;
- complete measurement record;
- bandwidth-0.7 primary result.

The indexed verifier requires the receipt, executable harness, and live-browser observations to agree on those values. It separately checks that precompletion measurement and primary-result fields are `null`, that baseline recovery contains 23 estimates plus one withheld head, and that complete input produces 24 current-model outputs.

This is fictional software evidence. The records are not signed, externally timestamped, write-once storage, physical provenance, assay-control validation, biological validation, clinical software, or prospective organ-on-chip evidence.

## Reproduce

```bash
node site/test_app_state.js
python3 study/audits/verify_live_demo_withholding.py
python3 -m unittest discover -s study/audits -p 'test_live_demo_withholding.py' -v
```

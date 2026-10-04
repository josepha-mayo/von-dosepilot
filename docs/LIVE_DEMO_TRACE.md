# Browser-local evidence trace preview

The public fictional workflow now shows the same evidence-ordering idea used by the operating implementation without exposing private model artifacts or patient data.

## State contract

| State | Plan commitment | Measurement record | Result record | Visible outputs |
| --- | --- | --- | --- | --- |
| Fresh | withheld | withheld | withheld | 24 withheld slots |
| Committed | SHA-256 present | withheld | withheld | 24 withheld slots |
| One reading missing | same plan SHA-256 | withheld | withheld | 24 withheld slots |
| Baseline recovery | same plan SHA-256 | withheld | baseline-result SHA-256 | 23 historical estimates; Afatinib withheld |
| Complete | same plan SHA-256 | measurement SHA-256 | bandwidth-0.7 result SHA-256 | 24 current-model summaries |

The browser calculates real SHA-256 digests with Web Crypto over canonical, seeded fictional payloads. The plan payload fixes the 64 requested treatments and plate assignments. The measurement payload contains all 64 fictional readings. A result payload binds the plan and, for the current model, the measurement digest plus the displayed outputs.

This is a transparent preview, not a security primitive. The records are not signed, externally timestamped, write-once storage, or proof that a physical plate was constructed as declared. The hashes do not validate assay controls, biological accuracy, clinical utility, or prospective organ-on-chip performance.

## Verification

Run the independent Node harness:

```bash
node site/test_app_state.js
```

The harness reconstructs the canonical payloads separately from the application, recomputes all digests, checks plan stability across committed states, and enforces that measurement and primary-result hashes remain absent before complete input.

Run the indexed receipt verifier and adversarial tests:

```bash
python3 study/audits/verify_live_demo_withholding.py
python3 -m unittest discover -s study/audits -p 'test_live_demo_withholding.py' -v
```

The original withholding receipt remains unchanged as the predecessor. The versioned receipt records the new production deployment and browser observations.

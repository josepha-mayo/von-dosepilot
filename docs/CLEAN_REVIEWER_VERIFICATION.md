# Verification of the clean reviewer quickstart receipt

The clean-clone execution receipt is independently checked by a response-free
verifier:

```bash
python study/audits/verify_clean_reviewer_quickstart.py --root .
python -m unittest discover -s study/audits \
  -p 'test_clean_reviewer_quickstart.py' -v
```

The verifier checks the public source commit and tree, exact requirement-file
hashes, lifecycle and preflight runner hashes, the fictional lifecycle
contract, the 14-stage/173-test preflight result, and all claim boundaries.  It
also checks that the evidence index points to the exact release receipt and
documentation bytes.

The adversarial tests reject receipt-byte tampering, predecessor tampering,
dependency drift, an inflated preflight count, a false clean-new-machine
claim, a false independent-validation claim and a false Kaggle-entry-change
claim.

This remains a software reproducibility check on one host.  It is **not a
clean-new-machine certification**, **not independent biological validation**,
does not reproduce the external workbook, and does not create a new
biological accuracy result, prospective organ-on-chip result or official
competition score.

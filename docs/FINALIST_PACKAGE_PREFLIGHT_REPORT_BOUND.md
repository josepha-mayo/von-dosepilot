# Report-bound finalist-package preflight

The public package has an additive response-free entry point that verifies the
canonical release, the current reviewer route, and the immutable rubric map
bound to the exact current technical report:

```bash
python3 study/audits/finalist_package_preflight_report_bound.py \
  --output finalist_package_preflight_report_bound.json
```

The command preserves the v1 and v2 package runners and their receipts. It
still executes eight checks: the unchanged canonical 14-stage/173-test release
preflight followed by seven standalone package checks. Only the eighth check
changes relative to v2. It verifies
`evidence/finalist_rubric_evidence_r5_20261006.json`, which binds presentation
evidence to the exact current ten-page, 92,307-byte report and its own public
render receipt. It therefore rejects fallback to the r4 current-package rubric
map or any earlier rubric predecessor.

The runner refuses to overwrite an existing output. Its JSON records every
command, exit code, elapsed time and output hash, the nested canonical receipt
hash, the r5 rubric-receipt hash, and exact hashes for the runner, verifier,
tests and this document.

Verify the published receipt independently with:

```bash
python3 study/audits/verify_finalist_package_preflight_report_bound.py --root .
python3 -m unittest discover -s study/audits \
  -p 'test_finalist_package_preflight_report_bound.py' -v
```

## Scope

This is response-free software and release-package verification. The report's
embedded public rendering and exact-tree structural rendering are verified;
raw download success and browser-downloaded-byte equality are not. A pass does
not create a model result, independent biological validation, physical
provenance, assay-control evidence, clinical suitability, prospective
organ-on-chip performance, a Kaggle edit, finalist status, or an official
competition score.

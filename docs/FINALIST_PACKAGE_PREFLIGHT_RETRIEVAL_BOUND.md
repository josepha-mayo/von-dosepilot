# Retrieval-bound finalist-package preflight

The public package has an additive response-free entry point that verifies the
canonical release, the current reviewer route, and the immutable rubric map
bound to both the exact current technical report and its public repository-file
byte retrieval:

```bash
python3 study/audits/finalist_package_preflight_retrieval_bound.py \
  --output finalist_package_preflight_retrieval_bound.json
```

The command preserves the v1, v2, and v3 package runners and their receipts.
It still executes eight checks: the unchanged canonical 14-stage/173-test
release preflight followed by seven standalone package checks. Only the eighth
check changes relative to v3. It verifies
`evidence/finalist_rubric_evidence_r6_20261006.json`, which binds the exact
current ten-page, 92,307-byte report, its render evidence, and the successful
GitHub repository-file retrieval whose decoded bytes match the report's
SHA-256 and Git blob identity.

The retrieval distinction remains explicit and machine-enforced: public
repository-file bytes were retrieved and matched, while anonymous raw-HTTP
access and GitHub's browser **Download** button were not verified. The generic
`raw_download_verified` field therefore remains false.

The runner refuses to overwrite an existing output. Its JSON records every
command, exit code, elapsed time and output hash, the nested canonical receipt
hash, the r6 rubric-receipt hash, and exact hashes for the runner, verifier,
tests and this document.

Verify the published receipt independently with:

```bash
python3 study/audits/verify_finalist_package_preflight_retrieval_bound.py --root .
python3 -m unittest discover -s study/audits \
  -p 'test_finalist_package_preflight_retrieval_bound.py' -v
```

## Scope

This is response-free software and release-package verification. It does not
create a model result, independent biological validation, physical provenance,
assay-control evidence, clinical suitability, prospective organ-on-chip
performance, a Kaggle edit, finalist status, or an official competition score.
It also does not establish anonymous raw-file availability, browser-button
download behavior, future availability, content completeness, accessibility
conformance, authorship, or signed/WORM storage.

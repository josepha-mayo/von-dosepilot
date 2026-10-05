# One-command finalist-package preflight

The public package has one additive response-free entry point for checking the
canonical release plus the reviewer-route and downloaded-trace evidence added
after the immutable 173-test receipt:

```bash
python3 study/audits/finalist_package_preflight_current.py \
  --output finalist_package_preflight.json
```

The command first executes the unchanged current release preflight, which must
pass 14 stages and 173 orchestrated response-free tests. It then runs seven
standalone checks covering the downloaded fictional-demo trace, offline trace
receipt, reviewer routes, trace/evidence discovery, verification chronology,
clean-clone quickstart receipt, and the current immutable v2 finalist-rubric
evidence map. The eighth check therefore cannot silently fall back to the
preserved 4 October rubric-map predecessor.

The runner refuses to overwrite an existing output. Its JSON records every
command, exit code, elapsed time and output hash, together with the nested
canonical receipt hash and exact runner/verifier/test/document hashes.

Verify the published receipt independently with:

```bash
python3 study/audits/verify_finalist_package_preflight_current.py --root .
python3 -m unittest discover -s study/audits \
  -p 'test_finalist_package_preflight_current.py' -v
```

## Scope

This is response-free software and release-package verification. It preserves
the canonical receipt, the v1 package receipt, and the clean execution of that
v1 runner instead of changing their historical meaning. A pass
does not create a model result, independent biological validation, physical
provenance, assay-control evidence, clinical suitability, prospective
organ-on-chip performance, a Kaggle edit, or an official competition score.

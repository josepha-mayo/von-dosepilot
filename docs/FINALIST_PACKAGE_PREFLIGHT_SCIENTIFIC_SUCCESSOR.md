# Scientific-successor finalist-package preflight

Run the additive response-free scientific-successor package check with:

```bash
python3 study/audits/finalist_package_preflight_scientific_successor.py \
  --output finalist_package_preflight_scientific_successor.json
```

The command preserves all v1–v4 package runners and receipts. It executes eight
checks: the unchanged canonical 14-stage/173-test release preflight followed by
seven standalone package checks. Only the eighth check changes relative to v4:
it verifies `evidence/finalist_rubric_evidence_r7_20261006.json`, which binds the
current scientific-successor map and its exact candidate, bootstrap, target,
visual, report, write-up, and reviewer-path artifacts.

The package reports the orientation-specific control-quality rank-1 candidate at
MSE `0.001042745722096212`, 40/59 patient wins, 5/5 favorable folds, and 19/24
target-average wins versus bandwidth-0.7. It retains the immediate-predecessor
qualification and does not replace bandwidth-0.7 as the operational/demo
baseline.

The runner performs no network request and refuses to overwrite an existing
output. Its receipt records each command, exit code, elapsed time and output
hash, the nested canonical receipt hash, the r7 rubric receipt, and exact hashes
for the runner, verifier, tests and this document.

Verify the published receipt with:

```bash
python3 study/audits/verify_finalist_package_preflight_scientific_successor.py --root .
python3 -m unittest discover -s study/audits \
  -p 'test_finalist_package_preflight_scientific_successor.py' -v
```

This is release-package verification for repeated adaptive-development evidence.
It is not independent validation, a new model fit, a Kaggle edit, a Netlify
deployment, finalist confirmation, a clinical claim, or an official score.

# Clean scientific-successor finalist-package execution

This receipt records a fresh-source, fresh-virtual-environment execution of the
additive scientific-successor v5 finalist-package preflight.

## Reproduce

From a fresh source directory whose tree is
`de6a12b3d3f6cbaa008b983756a28a03572ecbc5`:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt -r study/requirements.txt
.venv/bin/python study/audits/finalist_package_preflight_scientific_successor.py \
  --output finalist_package_preflight_scientific_successor.json
```

The recorded run used Python 3.12.14 on Ubuntu 24.04 in a newly created virtual
environment. All declared dependencies resolved from the local pip cache; no
live dependency-download claim is made. The package passed all 8/8 checks,
enforced the immutable r7 scientific-successor rubric, and its nested canonical
preflight passed all 14 stages and 173 orchestrated response-free tests.

The bound candidate remains orientation-specific control-quality rank-1 at MSE
`0.001042745722096212`, 40/59 patient wins, 5/5 favorable folds and 19/24
target-average wins versus bandwidth-0.7. Bandwidth-0.7 remains the
operational/demo baseline. This execution does not turn repeated adaptive
development into independent validation.

## Exact scope

- The source directory was reconstructed with `git archive` from public commit
  `f9090a2b75ffbc3639006ecc9298b7f217b6f78b`; it was not a network clone.
- Dependency installation used the configured source and local pip cache. The
  package runner itself made zero network requests.
- The run used one existing host. It is not clean-new-machine certification.
- The descriptive bootstrap remains post-hoc and selection-naive. Patient-level
  rows and frozen bootstrap inputs are not public, so it is not independently
  recomputed or confirmatory.
- The documents' Windows replay statement remains unbound by a separate
  immutable machine-readable Windows receipt; independent reproduction is not
  claimed.
- This is software-installation and response-free package evidence. It is not
  biological validation, prospective organ-on-chip evidence, clinical
  validation, finalist status, or an official competition score.
- No private patient arrays, protected responses, source workbook, model fit,
  Kaggle edit, or Netlify deployment was involved.

All earlier clean-execution receipts remain byte-unchanged. Verify this receipt:

```bash
python3 study/audits/verify_clean_scientific_successor_finalist_package_execution.py --root .
python3 -m unittest discover -s study/audits \
  -p 'test_clean_scientific_successor_finalist_package_execution.py' -v
```

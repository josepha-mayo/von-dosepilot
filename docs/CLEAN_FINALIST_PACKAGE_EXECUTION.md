# Clean finalist-package execution

This receipt records a fresh, isolated execution of the published one-command finalist-package preflight after its reviewer-facing release.

## Reproduce

From a clean source checkout of public commit `19d4ca004705581ab3b4ebd7f710a49f298caeeb`:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt -r study/requirements.txt
.venv/bin/python study/audits/finalist_package_preflight.py \
  --output finalist_package_preflight.json
```

The recorded execution used Python 3.12.14 on Ubuntu 24.04.3 LTS, installed the declared dependencies into a newly created virtual environment, and then passed all eight package checks. The nested canonical preflight passed all 14 stages and 173 orchestrated response-free tests.

## Exact scope

- The source archive had tree `4601ff63fd1af15aa13a9daae10946502781cfbd`, exactly matching the published commit tree.
- The source directory was freshly reconstructed with `git archive`; it was not a network `git clone`.
- Dependency installation used live HTTPS package downloads. The package runner itself made zero network requests.
- The run used one existing host. It is not clean-new-machine certification.
- It verifies software installation and response-free package execution. It is not an independent biological validation, a prospective organ-on-chip result, physical provenance, clinical validation, or an official competition score.
- No private patient arrays, protected responses, source workbooks, model fitting, Kaggle edit, or Netlify deployment were involved.

The machine-readable aggregate receipt is `evidence/clean_finalist_package_execution_20261005.json`. Verify it with:

```bash
python3 study/audits/verify_clean_finalist_package_execution.py --root .
```

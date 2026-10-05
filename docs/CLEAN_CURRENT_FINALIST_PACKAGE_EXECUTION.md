# Clean current finalist-package execution

This receipt records a fresh-source, fresh-virtual-environment execution of the
current v2 one-command finalist-package preflight after it became the primary
reviewer entry point.

## Reproduce

From a fresh source directory whose tree is
`7ffe0b761f8e02ad8b784a653fac489538c7198a`:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt -r study/requirements.txt
.venv/bin/python study/audits/finalist_package_preflight_current.py \
  --output finalist_package_preflight_current.json
```

The recorded run used Python 3.12.14 on Ubuntu 24.04 with a newly created
virtual environment. All declared dependencies were installed from the local
pip cache. The current package passed all 8/8 checks, its eighth check verified
the current immutable finalist-rubric successor, and the nested canonical
preflight passed all 14 stages and 173 orchestrated response-free tests.

## Exact scope

- The source directory was reconstructed with `git archive` from a local
  commit whose tree exactly matched public commit
  `64424e9c0a8c158e47300398f892b2ec148ed7de`; it was not a network clone.
- The dependency installer was permitted to use its configured package source,
  but its output resolved every wheel and metadata file from cache. No claim of
  a live dependency download is made.
- The package runner itself made zero network requests.
- The run used one existing host. It is not clean-new-machine certification.
- This is software-installation and response-free package evidence. It is not
  independent biological validation, prospective organ-on-chip evidence,
  physical provenance, clinical validation, or an official competition score.
- No private patient arrays, protected responses, source workbooks, model fit,
  Kaggle edit, or Netlify deployment were involved.

The earlier v1 clean-execution receipt remains byte-unchanged and continues to
describe the historical v1 runner. Verify this current receipt independently:

```bash
python3 study/audits/verify_clean_current_finalist_package_execution.py --root .
python3 -m unittest discover -s study/audits \
  -p 'test_clean_current_finalist_package_execution.py' -v
```

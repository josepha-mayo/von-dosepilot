# Clean report-bound finalist-package execution

This receipt records a fresh-source, fresh-virtual-environment execution of the
primary report-bound v3 finalist-package preflight after it became the reviewer
entry point.

## Reproduce

From a fresh source directory whose tree is
`c8936f98815f79e187e6b8ecc6c52e7aebf9f1cb`:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt -r study/requirements.txt
.venv/bin/python study/audits/finalist_package_preflight_report_bound.py \
  --output finalist_package_preflight_report_bound.json
```

The recorded run used Python 3.12.14 on Ubuntu 24.04 in a newly created virtual
environment. The installer performed live HTTPS downloads for all ten wheel and
metadata artifacts; this differs from the earlier cache-only v2 clean run and
is disclosed rather than normalized away. The report-bound package passed all
8/8 checks, enforced the current-report rubric successor, and its nested
canonical preflight passed all 14 stages and 173 orchestrated response-free
tests.

## Exact scope

- The source directory was reconstructed with `git archive` from a local commit
  whose tree exactly matched public commit
  `ae04f83d2171df24f28a01d1fa530c57961b94d0`; it was not a network clone.
- Dependency installation used the configured package source and performed live
  downloads. The package runner itself made zero network requests.
- The run used one existing host. It is not clean-new-machine certification.
- Embedded public and exact-tree structural report rendering are verified; raw
  download success and browser-downloaded-byte equality remain unverified.
- This is software-installation and response-free package evidence. It is not
  independent biological validation, prospective organ-on-chip evidence,
  physical provenance, clinical validation, finalist status, or an official
  competition score.
- No private patient arrays, protected responses, source workbooks, model fit,
  Kaggle edit, or Netlify deployment were involved.

The v1 and v2 clean-execution receipts remain byte-unchanged. Verify this
report-bound receipt independently:

```bash
python3 study/audits/verify_clean_report_bound_finalist_package_execution.py --root .
python3 -m unittest discover -s study/audits \
  -p 'test_clean_report_bound_finalist_package_execution.py' -v
```

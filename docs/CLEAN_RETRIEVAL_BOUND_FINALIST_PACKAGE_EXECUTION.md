# Clean retrieval-bound finalist-package execution

This receipt records a fresh-source, fresh-virtual-environment execution of the
primary retrieval-bound v4 finalist-package preflight after it became the
reviewer entry point.

## Reproduce

From a fresh source directory whose tree is
`faa2cc0429e989420a945a494cc7ca625951a0c6`:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt -r study/requirements.txt
.venv/bin/python study/audits/finalist_package_preflight_retrieval_bound.py \
  --output finalist_package_preflight_retrieval_bound.json
```

The recorded run used Python 3.12.14 on Ubuntu 24.04 in a newly created virtual
environment. All declared dependencies resolved from the local pip cache. No
live dependency-download claim is made. The retrieval-bound package passed all
8/8 checks, enforced the current-report retrieval-rubric successor, verified
that the point-in-time repository-file bytes matched the exact-tree report, and
its nested canonical preflight passed all 14 stages and 173 orchestrated
response-free tests.

## Exact scope

- The source directory was reconstructed with `git archive` from a local commit
  whose tree exactly matched public commit
  `e46ee71de5d7c2f3694878ffbfb4547e1d32d126`; it was not a network clone.
- Dependency installation used the configured package source and local pip
  cache. The package runner itself made zero network requests.
- The run used one existing host. It is not clean-new-machine certification.
- Point-in-time GitHub repository-file retrieval and exact byte equality to the
  package report are verified. Anonymous raw HTTP, the GitHub browser Download
  button, and generic raw-PDF download remain unverified.
- This is software-installation and response-free package evidence. It is not
  independent biological validation, prospective organ-on-chip evidence,
  physical provenance, clinical validation, finalist status, or an official
  competition score.
- No private patient arrays, protected responses, source workbooks, model fit,
  Kaggle edit, or Netlify deployment were involved.

The v1, v2, and v3 clean-execution receipts remain byte-unchanged. Verify this
retrieval-bound receipt independently:

```bash
python3 study/audits/verify_clean_retrieval_bound_finalist_package_execution.py --root .
python3 -m unittest discover -s study/audits \
  -p 'test_clean_retrieval_bound_finalist_package_execution.py' -v
```

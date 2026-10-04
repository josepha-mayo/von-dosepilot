# Clean public-clone reviewer execution

On 4 October 2026, the documented reviewer quickstart was executed from a
fresh, shallow clone of public `master` and a newly created Python virtual
environment.  This check was deliberately separate from the development
worktrees used to build the release.

## Bound source

- commit: `edcb892d77ed6fdbed5548646b80f7b9a8ebd1a5`
- tree: `56bb7cf055720ac007d0a968cd41df85eb1b0527`
- Python: 3.12.14
- operating system: Ubuntu 24.04.3 LTS, Linux x86_64

The environment first installed `requirements.txt`, ran the current fictional
bandwidth lifecycle, then installed `study/requirements.txt` and ran the
current response-free release preflight:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python study/durable_runtime/run_bandwidth_lifecycle_demo.py \
  --output bandwidth_lifecycle_demo_001
.venv/bin/python -m pip install -r study/requirements.txt
.venv/bin/python study/audits/release_preflight_current.py \
  --output release_preflight.json
```

## Observed result

| Check | Result |
|---|---:|
| Fresh clone matched the bound commit and tree | PASS |
| Dependency installation in a new virtual environment | PASS |
| Six-call fictional bandwidth lifecycle | PASS |
| Fictional lifecycle wall time | 1 second |
| Current release-preflight stages | 14/14 PASS |
| Orchestrated response-free tests | 173 PASS |
| Release-preflight wall time | 11 seconds |
| Protected responses or private patient arrays read | No |
| Biological accuracy result created | No |
| Accepted Kaggle entry changed | No |

The lifecycle demonstrated the committed 64-reading interface, rejection of
an incomplete primary request, explicit baseline recovery, changed-reading
rejection, all 24 primary outputs and byte-identical export recovery using
seeded fictional inputs.

## Scope and limitations

This is a **clean-clone, clean-environment software execution check on one
host**.  It is not a clean-new-machine certification, independent biological
validation, prospective organ-on-chip evidence, a rerun of the public source
workbook reconstruction, or an official competition score.  It also does not
show that future package-index availability will remain unchanged.  The
machine-readable receipt records the exact source, requirement, lifecycle and
preflight hashes.

[Machine-readable receipt](../evidence/clean_reviewer_quickstart_20261004.json)

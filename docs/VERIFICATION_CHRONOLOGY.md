# DosePilot verification chronology

The public release checks are additive. Test totals increased as new claim surfaces and tamper cases were introduced; an older lower total is not evidence that tests failed. Historical receipts remain immutable and retain the count that was true when each was created.

| Public verification state | Completed stages | Orchestrated response-free tests | What changed |
|---|---:|---:|---|
| Portable reviewer quickstart | 14/14 | 157 | Current-model quickstart and Kaggle-link portability were bound. |
| Report/site and promotion-gate hardening | 14/14 | 168 | Schedule tamper cases and derived promotion-gate checks were added. The current ten-page report remains bound to this state. |
| Development governance | 14/14 | 171 | The candidate registry and prefrozen-proposal checks were added. |
| Finalist rubric evidence map | **14/14** | **173** | Criterion-to-evidence consistency checks were added. This is the latest canonical release-preflight state. |

The 173 tests are not 173 biological experiments. They are response-free software, evidence-consistency, acquisition, kernel, endpoint, schedule, organ-on-chip constraint, and fictional lifecycle checks. Numerical reproduction, software verification, retrospective development evidence, and independent biological validation remain distinct.

## Machine check

```bash
python study/audits/verify_verification_chronology.py --root .
```

The checker verifies the exact historical receipt hashes and counts, the latest evidence-index pointer, both public reviewer surfaces, and the following claim boundaries:

- no protected or private input is read;
- no new biological accuracy result is created;
- the accepted Kaggle entry is not changed;
- no official competition score is assigned.

The machine-readable chronology is `evidence/verification_chronology_20261004.json`.

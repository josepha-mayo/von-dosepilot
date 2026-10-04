# Downloadable state-bound evidence record

The live fictional workflow now lets a reviewer download the exact JSON shown by **Inspect full evidence record**. The export is generated in the browser from the same state record as the visible disclosure, so the filename, visible JSON, and downloadable bytes change together as the workflow advances.

## Export contract

Each file contains only six fields:

- schema and workflow state;
- plan, measurement, and result SHA-256 values, using JSON `null` before the corresponding evidence exists; and
- the result kind.

The fresh export contains three null digests. Committed and missing-reading exports contain only the stable plan digest. Historical-baseline recovery contains the plan and 23-output baseline-result digests while measurement remains null. Complete input contains the plan, 64-reading measurement, and 24-output bandwidth-0.7 result digests.

The export contains no raw readings, model outputs, patient data, private model weights, or protected-study data. It is a fictional browser-local software trace, not signed evidence, an external timestamp, write-once storage, physical provenance, assay-control validation, biological validation, clinical software, or prospective organ-on-chip evidence.

## Verification

The independent Node harness verifies all six workflow states, exact filenames, byte equality between the visible and downloadable records, null semantics, absence of readings and outputs, and the four reconstructed SHA-256 values. Production-browser checks independently decoded the live `data:application/json` links for fresh, recovery, and complete states and compared them byte-for-byte with the visible records.

```bash
node site/test_app_state.js
python3 study/audits/verify_live_demo_withholding.py
python3 -m unittest discover -s study/audits -p 'test_live_demo_withholding.py' -v
```

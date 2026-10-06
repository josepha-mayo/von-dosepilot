# DosePilot current-report retrieval-bound finalist-rubric evidence successor

**Purpose:** add the current report's verified public repository-file retrieval
to the immutable current-report rubric map. The predecessor already binds the
exact 92,307-byte report and its public embedded/structural rendering. This
successor additionally binds the independently recorded byte retrieval without
rewriting or broadening the predecessor.

The `30/30/20/10/10` weights remain the last platform-verified values from
**1 October 2026**. No refreshed-rubric claim, judge self-score, finalist
probability, official score, or changed-Kaggle-entry claim is made.

## Exact successor binding

| Item | Bound value |
|---|---|
| Immutable predecessor map | `evidence/finalist_rubric_evidence_r5_20261006.json` |
| Predecessor SHA-256 | `b8917193d24f486bf194bf7f3ad2ba6b63e25c716efc58b573ccb0760208107c` |
| Public byte-retrieval receipt | `evidence/public_report_byte_retrieval_verification_20261006.json` |
| Retrieval-receipt SHA-256 | `efa5356a6adbb4bbff483f9ab2036993ca87f9021d2cff65f076a8c6d741b489` |
| Current report SHA-256 | `23bd050d13b9724b3ae6dfb3ae63406609d2573edfcd957369556be99f4585f1` |
| Current report size | 92,307 bytes |
| Git blob SHA | `6899cb6b2c53c1c1d67a9fadb5d073923daaf21e` |
| Retrieval interface | GitHub repository-file fetch with base64 transfer encoding |

At immutable public commit
`43a5205d1ff04c4ebe2c93f2b463609f80629c05`, the repository-file response was
decoded to exactly 92,307 bytes. Its SHA-256 and Git blob identity exactly
matched `docs/DosePilot_Technical_Report_Current.pdf` in public tree
`1a823d4b8bfab4cccd6947437a85dee90aea8ce5`.

## What is inherited unchanged

The predecessor's five criteria and all scientific/package evidence remain
unchanged. In particular:

- bandwidth 0.7 remains repeated development at MSE
  `0.0010582750420801538`, p90 `0.0378942853087202`, 38/59 patient wins and
  5/5 favorable folds on 119 samples, 59 patients and 24 targets;
- the physical contract remains exactly 64 treatment wells, 32 per plate;
- the nested replay selected 0.7 inside all five outer fitting sets and exactly
  tied fixed 0.7, without becoming independent validation;
- the report-bound package remains 8/8 checks with nested canonical 14/14
  stages and 173 response-free tests; and
- Protected22 remains exposed with its full primary `NOT_ESTIMABLE`.

## Machine check

```bash
python3 study/audits/verify_finalist_rubric_evidence_current_retrieval.py --root .
python3 -m unittest discover -s study/audits \
  -p 'test_finalist_rubric_evidence_current_retrieval.py' -v
```

The machine-readable successor is
`evidence/finalist_rubric_evidence_r6_20261006.json`.

## Claim boundary

This verifies point-in-time retrieval through GitHub's public repository-file
interface and exact equality to the report bound into the package. It does not verify anonymous raw-HTTP access or GitHub's browser **Download** button. It
also does not establish future availability, content completeness,
accessibility conformance, authorship, signed/WORM storage, independent
biological validation, clinical utility, prospective organ-on-chip
performance, finalist status, or an official competition result. No model fit,
protected/private input read, Kaggle edit, or Netlify deployment occurred.

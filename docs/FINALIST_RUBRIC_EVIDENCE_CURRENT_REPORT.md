# DosePilot current-report-bound finalist-rubric evidence successor

**Purpose:** correct one presentation-evidence boundary in the immutable
current-package rubric map. The predecessor cited the public-render receipt for
an earlier 92,034-byte PDF. The current report has different, independently
verified bytes, so this successor binds the presentation criterion to the
current report's own render receipt without rewriting the predecessor.

The `30/30/20/10/10` weights remain the last platform-verified values from
**1 October 2026**. No refreshed-rubric claim, judge self-score, finalist
probability, official score, or changed-Kaggle-entry claim is made.

## Exact successor binding

| Item | Bound value |
|---|---|
| Immutable predecessor map | `evidence/finalist_rubric_evidence_r4_20261005.json` |
| Predecessor SHA-256 | `f673eea6d102745370e14b35c78e1c6d3e5e00574efe74ad9a1373e4279fb1e5` |
| Current render receipt | `evidence/public_report_render_verification_r2_20261005.json` |
| Current render receipt SHA-256 | `de99f25117086be218e638d7d8a7d6a1ba70dc020070e041e4d0405e0d883ecc` |
| Current report SHA-256 | `23bd050d13b9724b3ae6dfb3ae63406609d2573edfcd957369556be99f4585f1` |
| Current report size | 92,307 bytes |
| Public viewer commit binding | `a7483aa3a275d50aa32bdb043c52a203d8b8d41e` |
| Structural rendering | 10/10 A4 pages |

The current embedded viewer rendered the report and its **More Pages** control
reached the boundary showing the `Page 5` footer and the next page's `Negative
results and external evidence` heading. Response-free checks identified PDF
1.4, no encryption, no JavaScript, and rendered all ten exact-tree pages.

## What is inherited unchanged

The predecessor's problem-importance, technical-approach, results, and
reproducibility evidence remain unchanged. In particular:

- bandwidth 0.7 remains repeated development at MSE
  `0.0010582750420801538`, p90 `0.0378942853087202`, 38/59 patient wins and
  5/5 favorable folds on 119 samples, 59 patients and 24 targets;
- the physical contract remains exactly 64 treatment wells, 32 per plate;
- the nested replay selected 0.7 inside all five outer fitting sets and exactly
  tied fixed 0.7, without becoming independent validation;
- the primary v2 package remains 8/8 checks with nested canonical 14/14 stages
  and 173 response-free tests; and
- Protected22 remains exposed with its full primary `NOT_ESTIMABLE`.

## Machine check

```bash
python3 study/audits/verify_finalist_rubric_evidence_current_report.py --root .
python3 -m unittest discover -s study/audits \
  -p 'test_finalist_rubric_evidence_current_report.py' -v
```

The machine-readable successor is
`evidence/finalist_rubric_evidence_r5_20261006.json`.

## Claim boundary

This is point-in-time public embedded-render evidence and exact-tree structural
rendering. Raw download was not tested, and no browser-downloaded file was
captured or byte-compared. It does not establish future availability, content
completeness, accessibility conformance, independent biological validation,
clinical utility, prospective organ-on-chip performance, finalist status, or
an official competition result. No model fit, protected/private input read,
Kaggle edit, or Netlify deployment occurred.

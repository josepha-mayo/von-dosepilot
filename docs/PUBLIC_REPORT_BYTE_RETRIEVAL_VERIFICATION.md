# Public technical-report byte retrieval verification

Observed 6 October 2026 at 06:04:11 UTC.

The current public technical report was retrieved from the public GitHub repository at the immutable commit `43a5205d1ff04c4ebe2c93f2b463609f80629c05` through GitHub's repository-file interface with base64 transfer encoding. Decoding the returned content produced exactly 92,307 bytes with SHA-256 `23bd050d13b9724b3ae6dfb3ae63406609d2573edfcd957369556be99f4585f1` and Git blob SHA `6899cb6b2c53c1c1d67a9fadb5d073923daaf21e`.

All three values exactly match `docs/DosePilot_Technical_Report_Current.pdf` in the tested public tree `1a823d4b8bfab4cccd6947437a85dee90aea8ce5`. This independently establishes point-in-time public repository byte retrieval and equality to the report bound into the finalist package.

Retrieval route:

`https://github.com/josepha-mayo/von-dosepilot/blob/43a5205d1ff04c4ebe2c93f2b463609f80629c05/docs/DosePilot_Technical_Report_Current.pdf`

## Exact scope

This evidence verifies one successful commit-bound repository-file retrieval and an exact byte comparison. It does not verify an anonymous raw-HTTP request, GitHub's browser Download button, future availability, uninterrupted availability, accessibility conformance, report-content completeness, authorship, signed or WORM storage, biological validation, clinical suitability, finalist status, or an official score.

No model was fitted. No source workbook, patient-level predictions, private input, Protected22/Lib2 response, or other protected material was read. The accepted Kaggle entry and Netlify deployment were unchanged.

Offline verification:

```bash
python3 study/audits/verify_public_report_byte_retrieval.py --root .
python3 -m unittest discover -s study/audits -p 'test_public_report_byte_retrieval.py' -v
```

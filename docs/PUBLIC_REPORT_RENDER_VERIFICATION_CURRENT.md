# Current public technical-report render verification

On 5 October 2026 at 23:06 UTC, the current public technical report was opened
from its GitHub `master` route in an isolated browser. GitHub identified the
latest report commit as
`a7483aa3a275d50aa32bdb043c52a203d8b8d41e` and displayed a 90.1 KB file. The
embedded viewer source was bound to that exact commit and to
`docs/DosePilot_Technical_Report_Current.pdf`. The viewer rendered the report,
and its **More Pages** control loaded the boundary where the `Page 5` footer and
the next page's `Negative results and external evidence` heading were visible
together.

The exact PDF in the matching public tree was also checked response-free:

| Check | Result |
|---|---|
| SHA-256 | `23bd050d13b9724b3ae6dfb3ae63406609d2573edfcd957369556be99f4585f1` |
| Size | 92,307 bytes |
| `pdfinfo` | PASS: 10 A4 pages, PDF 1.4, unencrypted, no JavaScript |
| `pdftoppm` | PASS: all 10 pages rendered to PNG |
| Public embedded viewer | PASS: commit-bound report content rendered beyond the initial page boundary |

This is an immutable successor to the 5 October receipt for the earlier report
revision. The predecessor remains byte-unchanged and retains its historical
meaning; it is not evidence for the new PDF bytes.

This check does **not** establish a successful raw-file download or compare a
browser-downloaded file with the repository PDF. It also does not certify future
availability, content completeness, accessibility conformance, signed/WORM
evidence, biological validity, clinical suitability, finalist status, or an
official competition result. No authentication, model fit, protected/private
input read, Kaggle edit, or Netlify deployment occurred.

The machine-readable successor receipt is
`evidence/public_report_render_verification_r2_20261005.json`. Verify its
predecessor binding, public viewer binding, exact PDF properties, artifact
hashes, limitation, and claim boundaries without making a network request:

```bash
python3 study/audits/verify_public_report_render_verification_current.py --root .
python3 -m unittest discover -s study/audits -p 'test_public_report_render_verification_current.py' -v
```

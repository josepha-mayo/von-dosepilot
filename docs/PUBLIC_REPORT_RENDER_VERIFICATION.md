# Public technical-report render verification

On 5 October 2026 at 13:43 UTC, the current public technical report was opened
from its GitHub `master` route in an isolated browser.  GitHub exposed an
embedded PDF viewer whose source was bound to public commit
`d2cb880668c7801dfa96ffdeb6fd50142d7bb645` and to
`docs/DosePilot_Technical_Report_Current.pdf`.  The viewer rendered report
content, and its **More Pages** control loaded a later boundary where the
`Page 5` footer and the next page's `Negative results and external evidence`
heading were simultaneously visible.

The exact PDF in the matching public tree was also checked response-free:

| Check | Result |
|---|---|
| SHA-256 | `1d5d7098d53838373ab57ad32ab01d61d3dcfe8d577f8b3bfb09f33f1b4a0ff2` |
| Size | 92,034 bytes |
| `pdfinfo` | PASS: 10 A4 pages, PDF 1.4, unencrypted, no JavaScript |
| `pdftoppm` | PASS: all 10 pages rendered to PNG |
| Public embedded viewer | PASS: commit-bound report content rendered beyond the initial page boundary |

This closes the narrow rendering limitation left by the earlier route-identity
receipt.  It does **not** establish a successful raw-file download or an
independent byte comparison against a browser-downloaded file: waiting for the
browser download event timed out.  It also does not certify future availability,
content completeness, accessibility conformance, signed/WORM evidence,
biological validity, clinical suitability, or an official competition result.
No authentication, model fit, protected/private input read, Kaggle edit, or
Netlify deployment occurred.

The machine-readable receipt is
`evidence/public_report_render_verification_20261005.json`.  Verify its public
binding, exact PDF properties, artifact hashes, preserved limitation, and claim
boundaries without making a network request:

```bash
python3 study/audits/verify_public_report_render_verification.py --root .
python3 -m unittest discover -s study/audits -p 'test_public_report_render_verification.py' -v
```


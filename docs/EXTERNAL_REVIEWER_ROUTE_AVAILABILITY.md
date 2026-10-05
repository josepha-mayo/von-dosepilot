# External reviewer-route availability

On 5 October 2026 at 12:10 UTC, the five external routes required by the
reviewer package were opened in an isolated browser.  Each route resolved to
the expected public identity:

| Route | Observed public identity |
|---|---|
| Live fictional demo | `von DosePilot — 64 wells → 24 response summaries`; the expected page heading rendered |
| Demo video | `von DosePilot \| AI4S Drug-Screen Reconstruction Demo - YouTube`; a video element was present |
| Public repository | `josepha-mayo/von-dosepilot`; the repository identity rendered |
| 90-second reviewer entrypoint | `00_REVIEWER_START_HERE.md` on `master`; the reviewer heading rendered |
| Current technical report | `DosePilot_Technical_Report_Current.pdf` on `master`; the GitHub file identity rendered |

The observed redirect from `https://youtu.be/QeOGJIgx378` to the corresponding
`youtube.com/watch` URL is recorded explicitly.  The other four routes retained
their expected public URLs, apart from the demo's trailing slash.

This is a point-in-time public availability and page-identity check.  It does
not certify future uptime, uninterrupted video playback, PDF download or page
rendering, authenticated Kaggle state, content completeness, signed evidence,
biological validation, clinical suitability, or an official competition
result.  No sign-in, form submission, model fit, protected/private input read,
Kaggle edit, Netlify deployment, or repository write occurred during the
browser check.

The machine-readable receipt is
`evidence/external_reviewer_route_availability_20261005.json`.  Verify its
structure, route identities, artifact hashes, and claim boundaries without
making a network request:

```bash
python3 study/audits/verify_external_reviewer_route_availability.py --root .
python3 -m unittest discover -s study/audits -p 'test_external_reviewer_route_availability.py' -v
```

The existing repository-navigation audit remains distinct: it verifies local
and GitHub targets response-free, while this receipt records a dated external
browser observation.  The first general public-fetch attempt could not access
the five URLs through that retrieval service.  The isolated-browser check then
resolved all five routes.  This operational limitation is preserved in the
receipt and is not a product, model, or scientific failure.

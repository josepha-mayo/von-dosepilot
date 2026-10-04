# Reviewer-route integrity verification

The finalist-facing package has several entry surfaces: the repository README, the 90-second reviewer page, the current-report pointer, the prepared Kaggle writeup, and the criterion evidence map. A valid sentence is not useful to a reviewer if its target has moved or its anchor no longer exists.

Run the response-free verifier:

```bash
python study/audits/verify_reviewer_routes.py --root .
```

It checks the hash-bound entry surfaces, every relative repository target on those surfaces, every `github.com/josepha-mayo/von-dosepilot/blob/master/...` target, Markdown fragments, HTTPS syntax, and the presence of the demo, video, repository, reviewer-entry and current-report URLs. Eight adversarial tests cover receipt tampering, missing local and GitHub targets, path escape, anchor drift, video-link removal and claim inflation.

This is a repository-navigation check. It performs **zero network requests** and therefore does **not** verify external demo availability, video playback, Kaggle state or Netlify deployment state. It reads no private or protected input and creates no biological accuracy result or competition score.

The machine-readable receipt is `evidence/reviewer_route_integrity_20261004.json`. The canonical 14-stage/173-test release preflight remains unchanged; these eight tests are standalone and must not be added to the historical count retrospectively.

The first adversarial-suite invocation exposed a test-fixture omission: one test passed and seven errored because the temporary fixture did not copy the two hash-bound implementation files. This was not a route, scientific, or product failure. After the fixture was corrected to copy every hash-bound file, all eight tests passed.

An initial integration draft added links to the two already hash-bound public entry surfaces. The existing central evidence verifier correctly rejected that draft with `REVIEWER_PATH_ENTRY_HASH`. The final release preserves both bound surfaces byte-for-byte and publishes this verifier as an indexed, standalone addendum instead of silently invalidating the frozen reviewer receipt.

A broad, undocumented audit-directory discovery command also produced two import errors because historical tests expect `study/engine` on `PYTHONPATH`. The documented canonical preflight had already passed. Re-running the two affected historical modules with their required path passed 24/24 tests; this did not change the canonical 173-test receipt.

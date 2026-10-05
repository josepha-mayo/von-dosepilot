# DosePilot current finalist-rubric evidence map

**Purpose:** route an expert reviewer from each recorded Kaggle criterion to the
strongest currently verified public evidence, while keeping development results,
software execution, point-in-time route checks, and prospective claims separate.

This is an immutable successor to the 4 October evidence map.  It does **not**
rewrite that predecessor, assign DosePilot a judge score, estimate finalist
probability, or claim that repository work changed the accepted Kaggle entry.
The `30/30/20/10/10` weights remain the last platform-verified values from
**1 October 2026**.  Official-page retrieval was attempted again on 5 October
but remained unavailable, so no fresh-rubric claim is made.

| Recorded Kaggle criterion | Weight | Strongest current checkable evidence | Important limitation |
|---|---:|---|---|
| Problem importance and impact | 30% | The endpoint contract reconstructs 24 normalized log-dose AUC summaries from 64 identified treatment measurements, versus 416 eligible treatment measurements in the retrospective two-plate source profile. | This is measurement-count compression, not demonstrated cost, time, material, clinical, or organ-on-chip benefit. |
| Technical approach and innovation | 30% | A frozen 64-well/32-per-plate acquisition contract; bandwidth-0.7 additive residual reconstruction; separate A/B loss accounting; missing-reading withholding; and an inspectable, downloadable digest-only fictional workflow with offline verification. | The model is repeated adaptive development. Component methods have prior art; no patent-style novelty claim is made. Digest evidence is not signed, WORM, or physical provenance. |
| Results and validation | 20% | On 119 samples from 59 whole patients and all 24 targets, bandwidth 0.7 has MSE 0.001058275042, 38/59 patient wins, 5/5 favorable folds, and better p90 versus additive-1.0. A nested replay selected 0.7 inside all 5/5 outer training sets and exactly tied fixed 0.7. A co-optimized interpolation control was decisively rejected and closed. | The nested replay and negative control remain repeated development on exposed folds, not correction for the wider campaign or independent validation. Ten target means regress. Protected22 is exposed and its full primary is NOT_ESTIMABLE. |
| Reproducibility and implementation | 10% | Public source-to-results reconstruction passed. A one-command finalist-package runner passed 8/8 checks, including the canonical 14-stage/173-test preflight, from a fresh source directory and new Python environment on one existing host. | This was `git archive`, not a network clone or clean-new-machine certification. Reproduction and software execution are not new predictive evidence. Public code excludes patient arrays and fitted biological weights. |
| Presentation | 10% | All 5/5 required external reviewer routes resolved to their expected identities in an isolated browser. The current ten-page PDF rendered through GitHub's commit-bound embedded viewer, and its exact tree artifact rendered all ten pages response-free. | These are point-in-time checks, not future uptime or uninterrupted video playback. The browser download event timed out, so no downloaded-file byte comparison or raw-download-success claim is made. |

## Current evidence anchors

1. **Endpoint and budget:** `TARGET_DEFINITIONS.md` and `evidence/target_definitions_release_20261003.json` pin 24 outputs, 64 selected measurements, 32 per plate, and the 416-measurement retrospective source profile.
2. **Incumbent and selection scope:** `evidence/bandwidth_successor_20261003.json` records the incumbent metrics and adverse slices. `evidence/nested_bandwidth_selection_20261004.json` records 0.7 selected in all five outer fitting sets and the exact tie to fixed 0.7.
3. **Search honesty:** `evidence/DEVELOPMENT_SEARCH_REGISTRY.json` preserves closed failures. `evidence/cooptimized_calibrated_control_20261004.json` records the latest decisive control failure: 3/59 patient wins, 0/5 favorable folds, and 22/24 target regressions.
4. **Validation boundary:** `evidence/PROTECTED22_ACCESS_STATUS.json` records the exposed cohort and NOT_ESTIMABLE primary. The separate matched-CAF adaptation does not validate the incumbent's fitted weights.
5. **Runnable package:** `evidence/clean_finalist_package_execution_20261005.json` records 8/8 package checks with the nested 14-stage/173-test canonical preflight in a new environment.
6. **Presentation delivery:** `evidence/external_reviewer_route_availability_20261005.json` records 5/5 route identities. `evidence/public_report_render_verification_20261005.json` records public embedded rendering plus exact-tree structural rendering and the failed download-event capture boundary.

## Machine check

Run the response-free successor verifier:

```bash
python3 study/audits/verify_finalist_rubric_evidence_current.py --root .
python3 -m unittest discover -s study/audits -p 'test_finalist_rubric_evidence_current.py' -v
```

It first re-verifies the immutable predecessor map, then checks the latest
nested selection, closed negative control, clean package execution, public route
availability, report rendering, current ten-page report, artifact hashes, and
claim boundaries. It opens no source workbook, patient-level array, prediction
array, fitted biological model, or protected response.

The machine-readable successor is
`evidence/finalist_rubric_evidence_r2_20261005.json`.

## Claim boundary

The evidence supports an inspectable fixed-budget retrospective reconstruction
workflow, a reproducible software package, and point-in-time delivery checks.
It does not establish clinical utility, realized laboratory savings, calibrated
uncertainty, independent biological validation, prospective organ-on-chip
performance, an official competition score, finalist status, or a guaranteed
outcome.


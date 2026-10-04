# DosePilot finalist rubric evidence map

**Purpose:** give an expert reviewer a criterion-by-criterion route from the recorded Kaggle rubric to checkable evidence, while keeping development results, external adaptation, software execution, and prospective claims separate.

This page does **not** assign DosePilot a judge score, estimate finalist probability, or claim that repository updates have changed the accepted Kaggle entry. The rubric weights below are the last recorded Kaggle evaluation weights, verified on **1 October 2026**. Automated public retrieval of that page was unavailable on 4 October, so the map preserves the earlier verified weights instead of pretending they were freshly reconfirmed.

| Recorded Kaggle criterion | Weight | Strongest checkable evidence | Important limitation |
|---|---:|---|---|
| Problem importance and impact | 30% | The fixed endpoint contract reconstructs 24 normalized log-dose AUC summaries from 64 identified treatment measurements, versus 416 eligible treatment measurements in the two-plate retrospective source profile. | This is measurement-count compression, not demonstrated cost, time, material, clinical, or organ-on-chip benefit. |
| Technical approach and innovation | 30% | A frozen 64-well/32-per-plate acquisition contract; an additive cross-drug residual model with bandwidth 0.7; exact A/B loss accounting; identity-bound commit/recover/predict software; explicit missing-reading withholding. | The model is repeated adaptive development. Component methods have prior art; no patent-style novelty claim is made. |
| Results and validation | 20% | On 119 samples from 59 whole patients and all 24 targets, the incumbent MSE is 0.001058275042, with 38/59 patient wins, 5/5 favorable folds, and better p90 versus the immediate additive control. A separate matched-CAF adaptation passed its own frozen gate. | Ten target means regress versus the immediate control. The incumbent result is not selection-corrected independent validation. Protected22's full primary is NOT_ESTIMABLE, and the matched-CAF study does not validate the incumbent's fitted weights. |
| Reproducibility and implementation | 10% | The public source-to-results route passed, the current bandwidth replay passed without historical predictions, the durable lifecycle passed 65 tests, and a fresh response-free preflight passed 173 orchestrated tests. | Reproduction is not new predictive evidence. Public code excludes fitted biological weights and patient arrays; the operating demo uses fictional parameters and measurements. |
| Presentation | 10% | A 90-second reviewer path, live fictional-data demo link, public video link, current ten-page report, exact target definitions, evidence index, and failure ledger are present. | Link presence is not playback or deployment availability verification. The live accepted Kaggle page was not edited by this evidence-map work. |

## What a reviewer can verify quickly

1. **Endpoint and resource contract:** `TARGET_DEFINITIONS.md` and `evidence/target_definitions_release_20261003.json` pin 24 outputs, 64 selected treatment measurements, 32 per plate, and the 416-measurement retrospective source profile.
2. **Current same-task development result:** `evidence/bandwidth_successor_20261003.json` pins MSE, p90, patient/fold breadth, the ten adverse target means, plan hashes, and the public-input replay result.
3. **Selection honesty:** `evidence/DEVELOPMENT_SEARCH_REGISTRY.json` and `docs/DEVELOPMENT_SEARCH_GOVERNANCE.md` show the incumbent and preserved rejected families. The displayed bandwidth result remains a post-selection development point estimate.
4. **Validation boundary:** `evidence/PROTECTED22_ACCESS_STATUS.json` records the exposed cohort and NOT_ESTIMABLE primary. `evidence/stroma_context_confirmation_20260930.json` records a separate adapted-design result and its non-equivalence to incumbent-weight validation.
5. **Runnable evidence:** `evidence/r33_public_pipeline.json`, `evidence/bandwidth_lifecycle_20261003.json`, and the current preflight receipt distinguish numerical reproduction, fictional runtime execution, and biological evidence.

## Machine check

Run the response-free rubric verifier:

```bash
python study/audits/verify_finalist_rubric_evidence.py --root .
```

It checks the five recorded weights, artifact hashes, incumbent metrics, 64/32+32 resource contract, adverse target count, exposed Protected22 boundary, matched-CAF scope, public reconstruction, runtime checks, report/page count, and the absence of a self-assigned judge score. It opens no workbook, fitted model, patient-level array, prediction array, or protected response.

The machine-readable map is `evidence/finalist_rubric_evidence_20261004.json`.

## Claim boundary

The evidence supports an inspectable, fixed-budget retrospective reconstruction workflow and concrete software execution. It does not establish clinical utility, realized laboratory savings, prospective organ-on-chip performance, calibrated uncertainty, an official competition score, finalist status, or a guaranteed outcome.

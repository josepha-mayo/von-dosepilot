# Live demo withholding integrity

## Why this release exists

A direct production-browser audit on 4 October 2026 found a real presentation defect in the fictional lifecycle demo. Before the user completed the 64-well input, the interface reported zero outputs but still rendered all 24 seeded numerical values at reduced opacity. The baseline-only recovery state likewise reported 23 historical estimates while visually rendering 24 numbers.

This did not change a biological result, model, measurement plan, or stored evidence. It did weaken the demo's visible abstention contract: a reviewer could see numbers that the ledger said were withheld.

## Corrected state contract

The public demo now enforces these visible states:

| State | Current-model numbers | Historical baseline numbers | Explicitly withheld slots |
|---|---:|---:|---:|
| Fresh | 0 | 0 | 24 |
| Committed | 0 | 0 | 24 |
| One required reading missing | 0 | 0 | 24 |
| Baseline-only recovery | 0 | 23 | 1 |
| Complete | 24 | 0 | 0 |
| Reset | 0 | 0 | 24 |

Withheld slots contain no numerical value, proportional bar width, or hidden `data-value`. They expose an accessible `WITHHELD` label. In the fictional missing-value path, Afatinib is the one baseline head left withheld; the page does not imply that this choice is a biological missingness result.

## Verification

`node site/test_app_state.js` executes all six states in a minimal DOM harness and rejects numerical leakage before completion, an incorrect 23/1 recovery split, or incomplete 24-output completion.

The unchanged response-free release preflight also passed 14/14 stages with 173 orchestrated tests, and the central evidence verifier passed. A fresh production deployment was then checked in a browser:

- fresh state: 24 accessible `WITHHELD` slots, zero numerical outputs;
- missing state: 63/64 wells, zero current-model outputs, zero baseline outputs, 24 withheld slots;
- baseline recovery: 23 numerical baseline estimates and one accessible `Afatinib: withheld` slot;
- complete state: 24 current-model numerical summaries and zero withheld slots;
- no page-origin browser console error was observed.

The deployment receipt is `evidence/live_demo_withholding_20261004.json`; its standalone verifier is `study/audits/verify_live_demo_withholding.py`.

## Boundary

This is a reviewer-facing software-integrity improvement. It is not a new model fit, biological accuracy result, independent validation, prospective organ-on-chip experiment, clinical claim, or official competition score. It read no private patient arrays and no protected response values. The accepted Kaggle entry was not edited.

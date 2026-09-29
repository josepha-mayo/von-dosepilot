# von DosePilot: operating demonstration, R25

This is a **private video/replay candidate**. It contains invented model parameters,
identifiers and measurements only. It is not a clinical tool or a new organoid
accuracy evaluation, and no public release permission is implied.

## Run the same workflow

Use Python and NumPy (recorded environment: Python 3.13.5, NumPy 2.3.5):

```bash
python run_operating_demo.py --output new_demo_session
```

Use a fresh output directory. The command verifies the original synthetic package,
commits a 64-treatment-well plan, produces 24 response summaries, demonstrates an
explicit own-drug abstention with one null value, rejects wrong-dose and budget-63
requests, and recovers an intact original commitment after a deliberate export
failure. Expected failures are part of the demonstration and remain in
`COMMANDS.jsonl`. No automatic biological retries or imputations are performed.

`demo_steps.py` calls the unchanged `dosepilot.py` and `recover_plan.py` programs.
It prints both their actual process responses and clearly labelled summaries
calculated from the generated JSON. `present.py` adds reading pauses and chapter
text. The MP4 separately records this actual scripted terminal session on a new
virtual X11 display. It is not a human-operated live session or a language-model
conversation. The recording is silent and contains no time acceleration or
replacement result screens.

## Evidence versus demonstration

All live inputs and numerical parameters used here are fictional. The last
chapter quotes historical aggregate findings from the R24 report, separately
labelled as retrospective repeated-development evidence. Those figures are not
produced by these invented examples. R13 remains the retained scientific method;
R18 has a slightly lower unpromoted point estimate. No new predictive gain,
independent validation, clinical benefit, or realized cost saving is established.

This workflow instantiates a fixed compatible plan. It is not an arbitrary-budget
or missing-dose optimizer. Controls remain additional. A local commitment ledger
is an application control, not proof of laboratory execution or tamper-proof
storage. Recovery cannot reconstruct a corrupt or missing ledger.

## Files and rights

`PACKAGE_MANIFEST.json` still pins every original R24 synthetic package file.
`OPERATING_ASSET_MANIFEST.json` additionally pins the new presenter and driver.
`NOTICE_REVIEW.md` records the release boundary. No source workbook, private
patient-level study arrays, biological fitted model, API credential, font binary,
or dependency executable is bundled. The project owner's code-license decision
and final public release review remain pending. Dependencies are not vendored.

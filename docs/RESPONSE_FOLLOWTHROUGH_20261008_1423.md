# DosePilot research follow-through, 8 October 2026

## Decision
No new model replaces the retained 64-well-well or128-well versions. The original same 64-well-budget half-error goal remains unmet.

## Measured outcomes

| Procedure | Treatment wells | Patient-balanced full24 MSE | Interpretation |
|---|---:|---:|---|
| Retained scientific model | 64 | 0.001042745722096 | Unchanged |
| Required same 64-well half-error target | 64 | 0.000521372861048 | Not achieved |
| New query-local primary | 64 | 0.001058388693158 | Rejected |
| New standard-control primary | 64 | 0.001058325148293 | Rejected |
| New query-local nested procedure | 124 | 0.000523864140292 | 1.990489x vs retained 64-well; still below 2x |
| Retained higher-cost research tier | 128 | 0.000510265803186 | Unchanged |
| New query-local nested procedure | 128 | 0.000508835092853 | Slightly lower point estimate; not promoted |
| New fixed local secondary | 128 | 0.000506481942610 | 0.7415% lower mean than retained 128-well; not promoted |

The best fixed 128-well secondary improved 37/59 patient means and 4/5 fold means, with nonworse p90. It was specified before its outcomes but is not the primary 70-option nested selector. It remains a research candidate rather than a replacement under the campaign's consistency requirement. Its2.058801x comparison is against retained 64-well, with twice the treatment measurements; it is not another 2x improvement over retained 128-well.

The 124-well procedure uses 60 more measurements than the 64-well model and four fewer than 128. Its 1.99049x point estimate does not meet the literal half-error threshold. Standard-control transfer did not rescue that shortfall.

## Work completed
The first new family adapts own-drug ridge coefficients to query-specific neighborhoods using only purchased response features. It preserves the global additive spectral residual. The second family applies measured plate-control quality summaries to cross-fitted residuals through a shared scalar correction and rank1 target deviations. Both keep patients separated throughout model/panel selection, preserve the original 24 endpoints, and account separately for each A/B layout and cost tier.

Independent numerical verifiers reconstructed274,176 predictions. The local verifier used a separately implemented augmented weighted-regression solver; the control verifier also rebuilt the quality-feature algebra. Maximum numerical differences were5.97e-14 and4.66e-15. The original controls reproduced and all excluded-label/full-curve/control mutation sentinels were zero.

These are repeated-development results on 119 samples from 59 patients, not independent biological confirmation, clinical validation, or official competition scores. Numerical replay checks software integrity, not biological generalization.

## Locations and provenance
Local worktree: D:/von-dosepilot-local-response-tiers-20261008/
Control worktree: D:/von-dosepilot-control-transfer-tiers-20261008/
Local immutable run: D:\von-dosepilot-data\local_response_tiers_20261008_run1
Control immutable run: D:\von-dosepilot-data\control_transfer_tiers_20261008_run1
Frozen code commits: eaf33c0 and 9270dc1.
Local result SHA256: 0aadf5b616e32388e196209491adb015af535967181ab3fb495f1b582a1912b3
Control result SHA256: 34fc61309da82725e0f01f9c188a5f404949568291c7876e88d845b7bd63ad3a

No public push, Kaggle update, or replacement of either retained model was performed.

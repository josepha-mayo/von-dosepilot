# Nonlinear predictor-aware acquisition: rejected

Completed 8 October 2026 at 13:16:39 UTC. Frozen scientific code commit: 0056db1. This experiment did NOT achieve 2x, and did not improve the retained scientific model. No submission, public repository or shared worktree was changed.

## Results

| Procedure | Equal-patient full24 MSE | p90 patient RMSE |
|---|---:|---:|
| Retained scientific 64-well candidate | 0.001042745722096212 | 0.037419695944064885 |
| Required half-error threshold | 0.000521372861048106 | <=0.037419695944064885 |
| Reproduced operational control | 0.0010582750420801536 | 0.03789428530872017 |
| Nonlinear predictor-aware panel | 0.0010511556646128047 | 0.038511608158242776 |

The new panel is 0.672734% better than the older operational control, but 0.806519% worse than the retained scientific candidate. It improves 30/59 patient means and 3/5 outer-fold means versus the retained candidate. p90 worsens. Promotion and half-error gates both fail.

## What changed

Instead of choosing doses with a linear covariance proxy, a one-sweep discrete search scored complete 64-well panels using the actual own-drug ridge plus nonlinear additive spectral predictor. Each block considered the existing dose subset and two fitting-only shortlisted alternatives. The entire planner was rebuilt on each real training partition, inside five outer and three inner whole-patient folds. The planner itself used three training-contained selection splits. Its internal planning scores are selection objectives, not unbiased validation results. The original 24 targets, 64 distinct native doses, 32/32 plate split and A/B alternative-loss semantics were unchanged. This is repeated adaptive development, not independent biological confirmation.

## Integrity

Ten synthetic checks passed. An independent scorer reconstructed 11,424 predictions from saved model states and purchased query values, maximum difference 2.220446049250313e-16. The original operational control reproduced within 1.7763568394002505e-15. Rebuilding outerfold0 after altering excluded patient values/labels changed neither fitted states nor predictions (both max difference 0.0). No Protected22/Lib2 access or extra purchased measurements.

## Exact locations

Code and protocol: D:/von-dosepilot-nonlinear-panel64-20261008/study/
Raw private run: D:/von-dosepilot-data/nonlinear_panel64_20261008_run1/
Aggregate result: evidence/nonlinear_panel64_20261008.json
Independent verification: D:/von-dosepilot-data/nonlinear_panel64_20261008_run1/VERIFICATION.json

Freeze SHA256: fa8c1346fc861a406665e9d9c4b9205562b81dde3eb87a2b0df581d3d8fd96ae
Prediction SHA256: 2dd727bbb274310becaf49c4511a3e20f1e433881168e44aec2ab7c2ecd0f331
Result SHA256: b740907a6193632559dab601142c480f6e8d3835e9dc5e88a376aab0bd745a7e

## Execution note

The existing Windows Python 3.14 environment had numpy, scipy, pandas and sklearn and completed the run. No new environment was installed. The initial WSL synthetic-test launch stalled during its user-session startup; native Windows execution avoided changing WSL or unrelated running work. All project data, sources and results stayed on D:.

Decision: REJECT_RETAIN_SCIENTIFIC64. The numeric 2x target remains unmet. Do not relabel the small gain against the older baseline as an improvement against the stronger retained model.

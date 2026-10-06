# DosePilot measurement-budget upgrade curve

This is a post-hoc budget ablation, not model selection and not independent validation.

The study fixes seven budgets **before opening outcomes**: 48, 52, 56, 60, 64, 68, and 72 treatment wells. These correspond to 0, 4, 8, 12, 16, 20, or 24 third-dose upgrades on top of the same two-dose-per-target base.

For every fitting split:

1. Compute the existing R13 best size-2 and best size-3 native subset for each of 24 targets using fitting rows only.
2. Rank targets by the frozen fitting-only `upgrade_gain = proxy2 - proxy3` with the existing target-id tie break.
3. For upgrade count K, promote exactly the top K targets to their best size-3 subset and keep all others at their best size-2 subset.
4. Assign complementary A/B plates using the same alternating upgraded-target rule as R13. All tested K are even, so every deployment buys exactly half its wells from p1 and half from p2.
5. Select one shared ridge penalty independently for each budget from [0.01, 0.1, 1, 10] using the same 3 inner whole-patient folds.
6. Score the same 5 outer whole-patient folds with equal patient and target weight. A/B prediction vectors are never averaged; only their losses are averaged.

The 64-well point must reproduce historical R13 MSE 0.001144858681382854 within 1e-12. The 48-well point must reproduce the already frozen two-dose ablation MSE 0.0015432725382030184 within 1e-12.

All seven budgets will be reported regardless of direction. No budget may replace the promoted scientific successor from this experiment. No retry or post-outcome budget-grid change is allowed.

Input curve SHA-256: b192dc242362d74c4faa941752792336c7610d9bd403cccbf1cee7a8a1fc7c94
Catalog SHA-256: 84eae3976307448ac696852d39d1b2376cce479d8af5e386ce04097020deff5e

No Protected22 / Lib2 response access.

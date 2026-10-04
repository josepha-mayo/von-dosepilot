# Development-search governance

DosePilot uses a machine-checkable registry to keep repeated adaptive development honest. The registry is not a claim that trying many models makes the surviving point estimate independent. It does the narrower, useful job of making a curated set of 23 public aggregate model or acquisition candidates, negative decisions, the live comparator, the exact task denominator and the closed Protected22 boundary explicit. Conventional and reproduction-only controls are not enumerated as candidate families. It is a consistency and declaration gate, not a sandbox or access-control system. It does not claim to exhaust every private or historical experiment, so a passing new-family declaration is not proof of complete novelty.

Run the response-free registry check:

```bash
python study/governance/check_development_registry.py --root .
python -m unittest study/governance/test_development_registry.py
```

Before any future fit, create a proposal matching `dosepilot.candidate_proposal.v1` and run:

```bash
python study/governance/check_candidate_proposal.py --root . --proposal PROPOSAL.json
```

The proposal gate rejects duplicate family identities or fingerprints; a changed 119-sample/59-patient/24-target/64-well task, primary metric or A/B expected-loss estimand; a comparator other than the current bandwidth-0.7 incumbent; already opened outer outcomes; target/fold splicing; A/B prediction averaging; Protected22 access; automatic retries; and a weakened promotion gate. The declared SHA-256 must match an in-repository `study/**/PROTOCOL.json`. That strict JSON protocol must uniquely encode and exactly match the proposal's task, hypothesis, comparator, boundaries and promotion gate; duplicate or extra keys fail. Passing the checker validates the frozen declaration only; it does not authorize a fit, prove that a proposed family is scientifically distinct, or prove that a later runner obeyed the declaration.

The current registry includes sixteen rejected families and three unpromoted references, including the cross-patient bandwidth, simplex-stacking, fixed isotonic paid-feature and co-optimized calibrated-interpolation branches. Their aggregate MSEs are re-read from the linked public evidence rather than trusted only from duplicated registry numbers. The cross-patient branch's numerically lower point estimate remains rejected because it achieved only 4/5 favorable folds against a prefrozen all-five-fold successor rule. The co-optimized calibrated-interpolation control is closed after a one-shot result 35.9672% worse than bandwidth-0.7, with 3/59 patient wins and 0/5 favorable folds. Historical references and superseded incumbents remain visible. Protected22/Lib2 is marked exposed and closed for further model development.

This control reads public aggregate evidence only. It does not open the source workbook, patient rows, fitted weights, prediction arrays or protected responses; it creates no new biological accuracy result and does not modify the accepted Kaggle entry.

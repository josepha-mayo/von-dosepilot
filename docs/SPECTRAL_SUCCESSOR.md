# Spectral residual successor: a qualified development improvement

**Joseph Ayanda | 1 October 2026 | von DosePilot**

The new S2 procedure passes every unchanged internal replacement criterion against both R13 and the archived R18 reference. It is a constructed, inference-tested **research successor**, not independent biological validation, a clinical model or a competition win. The existing accepted Kaggle entry and original operating demo have not been replaced.

## Same task, materially lower error

All comparisons use the same 119 Lib1 samples, 59 whole patients, 24 fixed unclipped AUC targets, and 64 distinct physical treatment wells per deployment alternative, 32 on each plate. Acquisition is identical to R13. Expected A/B squared losses are averaged, never their predictions.

| Measure | R13 | R18 | S2 spectral successor |
|---|---:|---:|---:|
| Patient-balanced full24 MSE | 0.0011448587 | 0.0011414048 | **0.0010701439** |
| p90 patient expected RMSE | 0.04110782 | 0.04095931 | **0.03873324** |
| S2 strict patient wins against reference | 49/59 | 47/59 | Not applicable |
| S2 favorable outer-fold means | 5/5 | 5/5 | Not applicable |

The mean reduction is **6.5261% versus R13 and 6.2433% versus R18**. Both candidate orientation-wide MSEs, 0.0011189863 and 0.0010213016, are below both references' expected means. All five existing requirements pass against both references: at least 5% lower MSE, at least 40 patient wins, at least four favorable folds, nonworse p90 and both orientation means below the reference expected mean. No threshold was weakened.

Twenty of 24 target mean errors are nonworse than R13; Alisertib, Methotrexate, Napabucasin and Panobinostat regress. Ten patient means regress against R13. The descriptive paired-patient interval for S2-minus-R13 MSE is [-0.0001058371, -0.0000473383]. It is not selection-corrected and does not erase extensive reuse of these development patients.

See [aggregate values, adverse outcomes and execution hashes](../evidence/spectral_successor_20261001.json).

## What changed mathematically

The original own-drug ridge predictions provide a strong starting point. S2 learns a regularized correction from the same 64 purchased values to all 24 residual targets. It can share information across drugs without discarding the original own-drug estimator.

Inside each fitting slice, stack the two alternative training layouts with half of each patient's mass. Let Z be the base-standardized inputs, R the training residuals, and W the patient-balanced weights. Set H = Z'WZ + lambda I and take L L' = H. For G = L^-1 Z'WR, compute G = U diag(s) V'. Replace each singular value by max(s - f*s_max, 0), then transform back with L^-T. Prediction adds this linear correction to the original ridge output.

This is soft shrinkage of the **design-transformed coefficient spectrum**, not a nonlinear input model and not a nuclear-norm penalty on the raw coefficient matrix. Reduced-rank ridge is established prior art: Mukherjee and Zhu, 2011, DOI 10.1002/sam.10138. The contribution here is the tested residual formulation and its measurement-budget integration, not a new general theorem.

One common setting is selected by the original three inner whole-patient folds: f in {0.1, 0.3, 0.6}, lambda in {0.1, 1, 10}, plus no correction. The base ridge remains 0.01. Five outer whole-patient folds evaluate the entire procedure. Every fitting slice rebuilds its acquisition, centering, scaling and correction without its validation patients. Fitting residuals are training responses, not held-patient labels.

The first reduced-rank experiment and full-rank residual control reached 0.0010871593 and 0.0010848257 but missed the R18 margin. The smoother spectrum was proposed after those outcomes and frozen before its own run. Two matched tests combining corrections with the earlier R44 fixed plan reached 0.0010977059 and 0.0010790799 but failed the unchanged overall rules. These unsuccessful candidates are retained, not omitted.

## Reproduce from the public data route

First follow [PUBLIC_REPRODUCTION.md](PUBLIC_REPRODUCTION.md) to reconstruct the exact public-source Lib1 TRAIN CSV and install the pinned study requirements. The spectral command does not need the old private metadata kit or historical predictions:

```bash
python study/spectral_residual/reproduce.py --curves reconstructed_train/train_curves.csv --output spectral_replay --fit-final
```

A fresh repository clone on the author's laptop ran this command successfully. It reproduced R13 and S2 to better than 1e-12, including all five selected settings and 49 patient wins. The earlier public workbook reconstruction was reused, not downloaded or reinterpreted again. The full R18 patient-level gate was separately checked from authenticated historical arrays; this public command does not fabricate missing R18 outputs.

The optional final construction selects parameters using all 59 development patients and its own fixed three-fold split. It selected f=0.1 and lambda=1. This creates a deployable parameter artifact, not another accuracy estimate. Its weights and resulting patient arrays stay outside public commits.

## Inference and the important missing-data tradeoff

S2's correction uses measurements from other drugs. **All 64 values are required.** It does not inherit R13's ability to withhold only one drug head when that head's measurement is missing.

The low-level inference command validates model and plan digests, native identities, exact concentrations, drugs, complementary plates, unique physical-well labels, sample/run consistency and finite values. It reorders supplied records by identity, not list position. A missing input, duplicate or incompatible measurement yields no predictions; values are never imputed or clipped.

```bash
python study/spectral_residual/inference.py --model-dir spectral_replay/final_model --measurements measurements.json --output prediction.json
```

The JSON request has top-level `sample_id`, `run_id`, `orientation` (A or B) and `measurements`. Every one of the 64 records contains matching `sample_id` and `run_id`, plus `native_id`, `drug_id`, `dose_nM`, `plate` (p1 or p2), `well_id` and numeric `value`. Use the constructed plan's identities and concentrations. The caller supplies physical well labels; this wrapper cannot certify that a supplied number was actually measured in that well. It is not a replacement for the existing inventory/commitment workflow or laboratory quality assurance.

### Hash-bound operating workflow

`operating_workflow.py` closes the gap between that low-level arithmetic wrapper and an inspectable scientist workflow. Before any values are supplied, `commit` requires:

- a caller-recorded SHA-256 trust anchor for `CONSTRUCTION.json`;
- explicit sample, run and A/B orientation identities;
- two distinct plate-instance identities;
- exactly 64 caller-declared treatment wells whose native ID, drug, exact dose and plate match the fitted plan;
- 32 treatment wells on each plate;
- unique physical resources; and
- separate declared vehicle and viability controls outside the 64-treatment-well count.

It writes a create-exclusive commitment record before exporting a blank measurement template. `predict` accepts all 64 identified finite values only after rebuilding the commitment and matching it to that record. It writes the create-exclusive prediction record before exporting the 24-output result; the evidence includes construction, plan, model, commitment and measurement-file hashes. A changed commitment for the same model/sample/run frame or changed measurements after its recorded prediction are rejected. Repeating the exact same operation may recover a missing deterministic export after an interrupted write.

After constructing a model, record the trust anchor somewhere outside the mutable model directory:

```bash
sha256sum spectral_replay/final_model/CONSTRUCTION.json
mkdir spectral_operating_ledger
```

Prepare `inventory.json` using schema `dosepilot.spectral_inventory.v1`. It contains `sample_id`, `run_id`, `orientation`, `plate_instances`, 64 `treatment_wells`, and `controls`. Each treatment row contains `native_id`, `drug_id`, `dose_nM`, `plate`, and `well_id`; each control contains `control_type`, `plate`, and `well_id`.

Commit before reading responses:

```bash
python study/spectral_residual/operating_workflow.py commit \
  --model-dir spectral_replay/final_model \
  --construction-sha256 <previously-recorded-sha256> \
  --inventory inventory.json \
  --commitment committed_plan.json \
  --template measurements_to_fill.json \
  --ledger-dir spectral_operating_ledger
```

After measurements are identified and filled, predict once:

```bash
python study/spectral_residual/operating_workflow.py predict \
  --model-dir spectral_replay/final_model \
  --construction-sha256 <previously-recorded-sha256> \
  --commitment committed_plan.json \
  --measurements completed_measurements.json \
  --output prediction.json \
  --ledger-dir spectral_operating_ledger
```

The records detect byte and identity mismatches under an ordinary, benign filesystem. They are not signed, WORM-protected or immutable against a user who can edit/delete the directory. They cannot prove that a declared inventory exists or that a submitted number came from a physical well. The presence of vehicle and viability declarations also does not establish whether controls are sufficient per plate or assay. Hardware feasibility, laboratory quality assurance and control design remain the scientist's responsibility.

## Verification and release boundary

Forty-two spectral/runtime tests now pass: the original 27 spectral-algebra and low-level inference tests plus 15 operating-workflow tests. The operating tests cover exact budgets and controls, caller trust anchors, commitment canonicalization/tampering, wrong identities, missing/nonfinite values, uncommitted use, changed-frame rejection, deterministic export recovery and a concurrent changed-measurement race. The six previously developed fast-planner tests remain separate. A separately written explicit-patient-loop verifier passed 894 checks, including 678 numerical comparisons, all gates and five alternative-whitening model checks. Maximum metric difference was 4.44e-16; the alternative-whitening coefficient discrepancy was at most 6.91e-17.

On the independently constructed final artifact, 238 sample/orientation input sets matched direct matrix evaluation within 2.22e-16. Removing each of the 64 inputs in turn withheld every output. These are implementation tests on training records, not 238 independent validation observations.

All nine downloaded Python source files matched the locally tested source hashes. The cached-moment planner is additive; original scientific engines are unchanged. The three attempted external reviewer sessions returned no completed review due to database/provider failures. Verification claims refer to actual coordinator-authored calculations, not nonexistent reviewer approvals.

The source, tests, public-route runner and aggregate receipts are published. No original workbook, patient arrays or biological weights are published. No new Lib2 response was read. Lib2 remains exposed and its previous unavailable primary remains unavailable. The historical accepted entry is preserved while this successor's wider input-dependency contract is integrated into the next submission package.

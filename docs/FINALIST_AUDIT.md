# DosePilot finalist audit

**Purpose:** make the central 64-well claim auditable without asking a judge to reconstruct it from scattered experiment folders.

This is a **development-evidence audit**, not new biological validation. The current frozen model is the bandwidth-0.7 additive drug-group kernel.

## One-screen result

| Item | Frozen value |
|---|---:|
| Patient-balanced MSE | **0.001058275042** |
| Previous additive MSE | 0.001060552730 |
| Original R13 MSE | 0.001144858681 |
| p90 patient expected RMSE | **0.037894285** |
| Patient wins vs additive | **38 / 59** |
| Favorable outer folds vs additive | **5 / 5** |
| Patient wins vs R13 / R18 | **49 / 59 / 47 / 59** |
| Target means nonworse vs additive | **14 / 24** |

The bandwidth change is deliberately modest: it changes one global Gaussian-group lengthscale from 1.0 to **0.7**. It changes **no purchased well**. The improvement versus the immediate additive predecessor is about **0.215%**, while the complete method remains about **7.56% below R13**.

## The 64-well evaluation contract

1. **Split by whole patient.** All samples from one patient stay on the same side of every outer or inner fold.
2. **A is one 64-well deployment.** It purchases 64 distinct treatment wells, exactly 32 on each source plate.
3. **B is a separate alternative 64-well deployment.** It independently obeys the same 64 / 32+32 budget.
4. **No 128-well prediction exists.** A and B predictions are produced separately from their own purchased values.
5. **Score the two alternatives separately.** Compute squared error for A and B independently, then average those losses. Never average A/B prediction vectors.
6. **Targets are evaluator-only at prediction time.** The 24 reference response summaries enter scoring, not inference.
7. **Controls are declared separately from the treatment-well budget.** They are not silently counted as free treatment measurements.

The 238 runtime checks are **119 samples x 2 alternative orientations**. They are software replay checks, not 238 independent biological samples.

## Reproduce the frozen estimator

After following docs/PUBLIC_REPRODUCTION.md to reconstruct the hash-bound Lib1 TRAIN CSV:

    python study/hybrid_residual/reproduce_bandwidth.py       --curves reconstructed_train/train_curves.csv       --output bandwidth_replay       --fit-final

The completed public-input replay records:

- bandwidth-0.7 MSE: 0.0010582750420801538
- previous additive MSE: 0.001060552730112811
- R13 MSE: 0.0011448586813828537
- 38/59 patient wins versus additive
- 5/5 favorable folds
- no historical prediction input
- no old private metadata kit.

The constructed runtime was separately exercised on 238 sample/orientation records; direct matrix values agreed within 2.22e-16. Every one of 64 single-missing-position cases withheld the primary prediction. Those are software checks on existing training records, not new validation samples.

## Target-level honesty

The overall model improves, but it is **not uniformly better**. Fourteen target-average errors are nonworse versus the previous additive model; ten regress. The complete aggregate target table is below.

| Target | Bandwidth 0.7 MSE | Previous additive | Delta vs additive |
|---|---:|---:|---:|
| 5-FU | 0.0012109 | 0.0012135 | -2.66e-06 |
| AZD7762 | 0.0011229 | 0.0011230 | -1.70e-07 |
| Afatinib | 0.0012636 | 0.0012587 | +4.90e-06 |
| Alisertib | 0.0007791 | 0.0007884 | -9.33e-06 |
| Atorvastatin | 0.0007435 | 0.0007450 | -1.52e-06 |
| Bemcentinib | 0.0011495 | 0.0011397 | +9.71e-06 |
| Encorafenib | 0.0020088 | 0.0020077 | +1.09e-06 |
| Gedatolisib | 0.0011101 | 0.0011217 | -1.15e-05 |
| Gemcitabine | 0.0010259 | 0.0010393 | -1.34e-05 |
| Idasanutlin | 0.0011422 | 0.0011385 | +3.61e-06 |
| LCL161 | 0.0010025 | 0.0009981 | +4.40e-06 |
| LGK974 | 0.0010470 | 0.0010543 | -7.28e-06 |
| Lapatinib | 0.0008506 | 0.0008476 | +3.02e-06 |
| Luminespib | 0.0006862 | 0.0006871 | -8.92e-07 |
| Methotrexate | 0.0009082 | 0.0009140 | -5.84e-06 |
| Napabucasin | 0.0011706 | 0.0011825 | -1.19e-05 |
| Palbociclib | 0.0016282 | 0.0016397 | -1.15e-05 |
| Panobinostat | 0.0007854 | 0.0007903 | -4.83e-06 |
| Pevonedistat | 0.0009652 | 0.0009729 | -7.66e-06 |
| Regorafenib | 0.0010900 | 0.0010786 | +1.13e-05 |
| SN-38 | 0.0005674 | 0.0005671 | +3.43e-07 |
| TAS-102 | 0.0014476 | 0.0014532 | -5.60e-06 |
| Trametinib | 0.0009038 | 0.0009038 | +8.45e-09 |
| Volasertib | 0.0007894 | 0.0007884 | +9.68e-07 |

The largest absolute regressions are visible directly in the table. This is why the submission reports aggregate MSE, patient breadth, fold breadth, p90, and adverse target results together.

## Selection history, compactly

| Stage | MSE | Status |
|---|---:|---|
| R13 own-drug reconstruction | 0.0011448587 | historical retained baseline |
| S2 spectral residual | 0.0010701439 | improved development model |
| Additive drug-group kernel | 0.0010605527 | previous incumbent |
| **Bandwidth-0.7 additive** | **0.0010582750** | **current development incumbent** |
| Bandwidth 1.4 | 0.0010637094 | rejected |
| Residual-alignment reweighting | 0.0010608378 | rejected |
| Multioutput acquisition sweep | 0.0010665434 | rejected |
| Iterated additive, 2 cycles | 0.0010693535 | rejected |
| A/B consistency regularization | 0.00108007+ | rejected |

Many other exploratory branches are preserved in project history. This table does not imply independent replication. It shows that the current estimator survived explicit incumbent-facing screens rather than being reported only because its decimal was lowest.

## Synthetic failure-envelope audit

The frozen bandwidth model was also evaluated **post hoc, without refitting or selecting a new model**, under simple synthetic measurement perturbations.

- Independent Gaussian noise at 0.01 z-units increased mean MSE by about **0.062%** across five fixed seeds.
- At 0.05 z-units, mean MSE increased about **1.38%**.
- At 0.10 z-units, mean MSE increased about **5.58%**.
- A coherent ±5% multiplicative offset affecting one source plate was much more damaging, increasing MSE by about **14.5% to 16.8%**.
- A single missing purchased value still withholds the primary model output; no replacement treatment well or silent imputation is used.

These are synthetic software stress tests on the reused development population, **not estimates of real assay CV or biological robustness**. Their practical implication is narrower: future wet-lab integration should prioritize plate-level calibration/QC and prospectively validate any correction rule.

See `docs/SIMULATED_ASSAY_ROBUSTNESS.md` and `evidence/bandwidth_robustness_20261003.json`.

## Evidence levels

**Demonstrated development prediction performance:** whole-patient nested Lib1 evaluation above.

**Demonstrated software execution:** identity-bound 64-well runtime, missing-input withholding, public-input replay, source/evidence consistency tests, and a separate durable commit/recover/predict lifecycle for the current bandwidth-0.7 model. The predecessor additive lifecycle remains a distinct historical contract.

**Prospective biological utility:** organ-on-chip execution and actual laboratory savings still require a future independently specified assay study. The software contains a constraint compiler and execution-manifest path, but that is not measured chip performance.

**External evidence:** matched-CAF adaptation passed its own support gate; FORECAST-1 and eLife did not fully pass theirs. Protected22's full primary was not estimable and prior exposure prevents an untouched-confirmation claim. None of those are silently promoted into validation of the current fitted bandwidth model.

## Machine-check this page's claims

Run:

    python study/audits/verify_finalist_audit.py --root .

The verifier is response-free. It checks pinned public receipt/source hashes, the current benchmark, 64 / 32+32 physical budget, reproduction status, runtime check counts, all 24 target aggregate rows, target regression identities, and validation-scope labels. It reads no private patient rows or Protected22 responses.

See also:

- evidence/finalist_audit_manifest_20261003.json
- evidence/bandwidth_target_deltas_20261003.csv
- evidence/bandwidth_successor_20261003.json
- docs/BANDWIDTH_SUCCESSOR.md
- docs/SIMULATED_ASSAY_ROBUSTNESS.md
- docs/PROSPECTIVE_OOC_VALIDATION_CONTRACT.md
- docs/BANDWIDTH_DURABLE_LIFECYCLE.md
- live fictional-data demo: https://von-dosepilot.netlify.app

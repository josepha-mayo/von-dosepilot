# von DosePilot: structured research and explicit baseline recovery

**Joseph Ayanda | 2 October 2026 | Research software**

## Decision

The two new structured-kernel candidates did **not** beat the strongest recovered additive-kernel control. Neither is promoted. The numerical control to beat is **0.001060552730112811**, not the older S2 value of 0.0010701439454817465.

A separate, completed engineering improvement is now available: an explicitly requested baseline-only recovery report for incomplete additive-model inputs. A single missing reading can leave **23 older own-drug baseline estimates available**, while the affected head and every additive-model prediction remain withheld. This is not a replacement primary score or a new missing-data accuracy claim.

## The actual model experiments

The additive result already existed in the shared workspace at source commit `4afbac69059d88d433186df96b94be104d36b608`. This continuation recovered it, independently rebuilt its controls and checked its comparison rules; it did not invent or count that prior experiment again.

Every row uses the same **119 Lib1 samples, 59 whole patients, 24 original targets and 64 physical treatment wells per alternative, 32 per plate**. A/B squared losses are averaged; prediction vectors are not. The original five outer and three inner patient-separated folds are retained.

| Complete procedure | Patient-balanced MSE | p90 patient RMSE |
|---|---:|---:|
| Original R13 | 0.001144858681 | 0.041107825 |
| S2 spectral control | 0.001070143945 | 0.038733242 |
| **Recovered additive control** | **0.001060552730** | **0.038073112** |
| New pair-interaction mixture | 0.001062886193 | 0.038502265 |
| New mean/contrast kernel | 0.001064080098 | 0.038220088 |

The **pair mixture** models products of separately centered drug-group Gaussian similarities. It is 0.220% worse than additive, winning 25/59 patient averages and 2/5 folds. The **mean/contrast kernel** separately represents group-average response and within-group pattern. It is 0.333% worse, winning 20/59 patients and 1/5 folds. Both also worsen p90 versus additive. All four successor criteria fail for each arm.

Both new candidates beat S2 and pass the old R13/R18 screens, but accepting either would move backward from the stronger additive result. Their negative outcomes are retained. No favorable targets were spliced into another predictor and no search grid was expanded after the outcomes.

The recovered additive control is 0.896% below S2, with 45/59 patient wins and all five folds improving. It is 7.364% below R13 and 7.084% below R18, with 49/59 and 47/59 patient wins respectively. Its full original checks were recomputed and passed. These remain repeatedly reused development data, not independent biological validation.

## What the recovery feature changes

The additive correction depends on all 64 values. Its normal prediction path still rejects an incomplete input. The new command is separate and requires `--acknowledge-baseline-only`.

It validates the committed inventory, model trust anchor, sample/run, every native/drug/dose/plate/well identity and all 64 records. Only explicit JSON `null` marks an unavailable reading. Invalid numbers, duplicates, identity mismatches and omitted records are rejected, not silently treated as missing.

For each target with all of its own two or three required readings present, the command evaluates only the original own-drug baseline component. It never fills a missing coordinate or calls the global predictor with a fabricated value. Outputs are stored under **`baseline_predictions`**, with `BASELINE_ONLY` provenance; **`primary_predictions` stays empty**. The affected target is withheld.

Recovery reports have their own append-only ledger, separate from the primary prediction ledger. Replaying an identical report restores an interrupted export; later recovery records can fill missing observations but cannot rewrite or discard previously recorded values. The guarded completion command checks that history before handing a fully observed input to the unchanged primary backend. Its full predictions match the original backend exactly.

Use `complete_recovery.py` for that checked handoff. The older ordinary primary CLI is deliberately unchanged and does not independently consult the optional recovery journal. Caller-declared inventory checks and local file hashes do not certify that a measurement was physically performed or make this clinical software.

## Run the fully fictional demonstration

From the repository root, with its NumPy requirement installed:

```bash
python study/hybrid_residual/run_baseline_recovery_demo.py --output recovery_demo_001
```

This writes seeded fictional model parameters, an inventory commitment, one-missing-value input, a separate baseline-only report and `SUMMARY.json`. The observed demonstration result is **0 primary predictions, 23 labelled baseline predictions, 1 affected target withheld**. It downloads no patient data and performs no biological experiment. It is a new command-line demonstration, not a replacement for the already submitted video.

For a constructed additive model and an existing committed inventory:

```bash
python study/hybrid_residual/recover_baseline.py --model-dir MODEL_DIR --construction-sha256 TRUSTED_HASH --commitment commitment.json --measurements incomplete.json --output baseline_only.json --ledger-dir ledger --acknowledge-baseline-only
```

After actual missing readings arrive, use the history-preserving completion route:

```bash
python study/hybrid_residual/complete_recovery.py --model-dir MODEL_DIR --construction-sha256 TRUSTED_HASH --commitment commitment.json --measurements complete.json --output primary.json --ledger-dir ledger
```

`TRUSTED_HASH` must be the independently verified construction receipt digest. Neither command fits a model or recalculates study accuracy.

## Checks completed

There are **33 new synthetic tests**: 12 kernel-mathematics cases, 18 baseline-recovery cases and 3 completion-history cases. The full kernel/runtime regression suite passed **64 tests**, including those 21 recovery/completion tests; do not add the overlapping counts.

A separate explicit-patient-loop audit verified **216 comparison groups**, including all target metrics, the 200 inner configuration scores and every declared decision. Ten selected models were checked with explicit pair enumeration and a direct weighted linear-system solution. Maximum metric difference was 3.33e-16 and held-patient prediction discrepancy was 2.22e-16.

The existing fitted additive artifact was checked under **15,232 artificial single-missing masks** over 238 sample/orientation records. All 350,336 available baseline scalar comparisons agreed with direct arithmetic within 2.22e-16. The masks are software cases, not 15,232 patients or independent validation observations. Actual-ledger checks also passed two incomplete stages, export restoration, observation-preserving completion and protection of an already recorded primary result. Control reservations in these tests are fictional.

## Failures, rights and boundaries

An initial source-transport paste was corrupt and was rejected before extraction or numerical execution. Readable GitHub source, with exact local/remote hash checks, replaced it. An initial synthetic test incorrectly required equality of nonidentifiable dual coefficients; the corrected assertion checks identifiable training and query predictions. The production solver was not changed. Both failures are recorded rather than erased.

Pairwise products and sums of positive-semidefinite kernels are established mathematics. Relevant prior art: Durrande et al., *ANOVA kernels and RKHS of zero mean functions*, DOI `10.1016/j.jmva.2012.08.016`, arXiv `1106.3571`. No new general kernel theorem, causal drug interaction, clinical benefit or competition win is claimed.

No protected Lib2 responses or original workbook were read. Lib2 remains exposed and its earlier full primary remains not estimable. **This baseline-recovery utility does not repair that study, change its denominator or authorize imputation.** No live Kaggle entry or submitted video was edited.

Public files contain original code, fictional fixtures and aggregate evidence. Kernel model archives contain training features and remain private, together with patient-level predictions. The complete two-reference research runner requires the retained historical reference receipts; the fictional demo and synthetic tests do not. The existing public-data reconstruction route remains separate. Exact input, source, result and verification hashes are recorded in the companion evidence JSON.

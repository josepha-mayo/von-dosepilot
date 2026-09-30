# von DosePilot

**24 research response summaries from 64 traceable treatment wells.**

MIT-licensed research software by Joseph Ayanda for the AI4S Open Innovation challenge.

**Demo video:** https://youtu.be/QeOGJIgx378

## What it does

DosePilot turns a compatible assay inventory into one committed 64-treatment-well layout, keeps the physical identity of every required observation, and produces 24 drug-response summaries from complete measurements.

The operating workflow also:
- withholds the affected output when a required value is missing;
- rejects wrong concentration identities and insufficient budgets;
- recovers the same committed layout after export failure instead of selecting a new one.

The public demo uses fictional measurements and model parameters so it can be run without private biological data.

## Run the demonstration

```bash
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt
python run_demo.py --output demo_run_001
```

No GPU, API key, or language-model API is required.

## Exact public source

The historical raw drug-screen workbook is now tied to an exact public artifact: Mendeley Data v3 lists `Data S4.xlsx` at **15,886,254 bytes** with SHA-256 `3847aa93b2a84c7d5d0b04c26494f39f35963fc41e96eae97d8a180fbc33d81c`, exactly matching DosePilot's frozen source identity. The dataset is listed as CC BY 4.0.

Verify that live metadata anonymously with:

```bash
python study/acquire_public_source.py --check-only
```

**R33 now reconstructs the biological development results from this public workbook without the old private input bundle.** It recovered all 49,504 TRAIN measurements with an exact CSV hash, and a fresh-environment replay matched all four frozen R9/R13 metrics. See [full commands and evidence](docs/PUBLIC_REPRODUCTION.md). This is improved reproducibility, not a new accuracy or independent-validation claim.

## Retrospective development result

| Complete procedure | Patient-balanced MSE |
|---|---:|
| Earlier paired-well comparator, R9 | 0.0017214230 |
| Matched paired-native comparator | 0.0017379326 |
| **Retained broader-coverage procedure, R13** | **0.0011448587** |

The development study used 119 organoid samples from 59 whole patients at the same 64-treatment-well budget. The complete selected source curves contain **416 eligible target-treatment measurements per sample (208 per plate)**; the 64-well policy therefore uses **15.38%** of that retrospective treatment-measurement count. This **84.62% measurement-count reduction is not a claim of equal savings in money, materials, or elapsed laboratory time**. R13 reduced MSE by **33.49%** versus R9 and **34.13%** versus the matched paired-native control, with **53/59 patient means** and **5/5 outer-fold means** improving.

A separately optimized piecewise-linear interpolation acquisition policy was also tested at the same 64-well budget. It reached MSE **0.0024168103**; R13 was **52.63% lower**, with lower patient-mean error for **59/59 patients** and lower mean error in **5/5 folds**. This remains repeated development evidence, not independent confirmation.

## Separate external CRC confirmation

A post-submission external experiment froze the DosePilot sparse-reconstruction **design** on a different public metastatic-CRC organoid study before opening its FORECAST-1 confirmation responses. The community cohort supplied development data; FORECAST-1 was held back from model, acquisition, scaler, penalty and threshold selection.

Under a new eight-drug task with the same design principle and a 21-measurement budget, 13 of 19 FORECAST-1 PDTO lines were complete under the prefrozen all-values-required rule. On those complete patients, learned sparse reconstruction reached patient-balanced MSE **0.0021715** versus **0.0038552** for a separately optimized interpolation policy at the identical measurement count, a **43.67% reduction**. It improved **10/13 patient means**, was nonworse on **7/8 targets**, and improved the prespecified five-drug overlap subset. The paired-patient descriptive bootstrap interval for learned-minus-interpolation MSE was `[-0.002809, -0.000581]`.

The deliberately strict prefrozen support gate nevertheless **did not fully pass** because it required at least 12 strict patient wins out of the original 19 source patients; six source lines were incomplete and the learned procedure won 10 of the 13 complete patients. The gate was not relaxed after seeing the outcomes. This supports transfer of the sparse acquisition/reconstruction pattern, but it is **not direct external validation of the original fitted 24-drug R13 model**. See [the full external confirmation record](docs/EXTERNAL_CRC_CONFIRMATION.md).

## External matched-CAF stromal stress test

A second post-submission experiment used the separate Farin et al. public colorectal-cancer organoid/CAF biobank. The entire split, normalization, sparse model, independently optimized interpolation comparator and four-part gate were frozen before any RLU outcome was decoded. Development used 13 metadata-complete monoculture organoid IDs; confirmation used **15 different organoid IDs** with matched autologous tumor-CAF cocultures.

The new four-drug task used 11 replicate-averaged dose-level readouts out of 28 available positive-dose readouts. On the one-shot matched-CAF confirmation, learned sparse reconstruction reached MSE **0.0029697** versus **0.0052366** for optimized interpolation, **43.29% lower**. It won **10/15 organoid means**, was nonworse on **3/4 drug MSEs**, and improved p90 organoid RMSE from **0.10986** to **0.06666**. The fixed descriptive bootstrap interval for learned-minus-interpolation mean organoid MSE was **[-0.004234, -0.000497]**. **All four prefrozen gate components passed.**

This is organoid-ID-distinct confirmation of the sparse reconstruction design under a stromal coculture context. It does **not** prove unique-patient independence for every ID, directly validate the original R13 weights, equate dose-level summaries with physical wells, or validate clinical/OoC hardware performance. See [the frozen protocol and aggregate evidence](docs/STROMA_CONTEXT_CONFIRMATION.md).

## Stronger comparator audit: important qualification

A subsequent **post-hoc** test added training-only slope/intercept calibration to each drug's optimized interpolation output, without adding measurements. On the same eight-drug FORECAST assessment, calibrated interpolation improved to MSE **0.0028731**. The unchanged learned result is **24.42% lower**, not 43.67% lower against this stronger control; its descriptive paired interval **includes zero**. The original failed support gate remains failed.

On matched-CAF data, the same calibration procedure instead worsened interpolation to MSE **0.0058699**. The learned result remains better than both tested interpolation readouts; retain the conservative **43.29%** advantage against the better-performing original control as the headline. All **14 synthetic calibration tests** passed, and saved predictions and every target metric were separately checked. See [the full calibrated-control audit](docs/CALIBRATED_CONTROL_AUDIT.md).

These are additional analyses of already exposed data, not new independent confirmations. A later six-drug FORECAST analysis also reuses the same source cohort and must not be counted a second time. See [the evidence ledger](docs/EVIDENCE_LEDGER.md).


## Protected Lib2 exact-support attempt: incomplete

A separately frozen one-shot study attempted to evaluate the **22 R13 heads with exact cross-library support** on the historically reserved Lib2 frame. The two shifted-grid targets, Gedatolisib and Palbociclib, were excluded before numerical access; the unchanged R13 model then required 58 dose-level readouts per deployment alternative, matched by a TRAIN-only optimized interpolation comparator.

The importer encountered a required nonnumeric response **before any prediction vector or efficacy metric was constructed**. Under the frozen no-retry rule, the study is therefore **incomplete and has no Lib2 efficacy score**. No complete-case rescue, patient removal, imputation, target shrinking, or second attempt is used. See [the exact22 incomplete-study record](docs/LIB2_EXACT22_INCOMPLETE.md).

## Public eLife CRC-organoid retrospective stress test

A separate public eLife CRC-organoid workbook was used for a five-drug, 12-organoid retrospective test of the sparse-reconstruction **design pattern**. Each procedure used **13 of 54 dose-level target-support readouts**. Learned own-drug reconstruction reached MSE **0.0041734** versus **0.0060423** for separately optimized interpolation, **30.93% lower**, with better target MSE on **4/5 drugs** and lower p90 organoid RMSE.

The fixed stress gate nevertheless **did not pass**: learned reconstruction won only **7/12 organoid-level losses**, and the paired-organoid descriptive interval `[-0.004760, +0.000574]` crosses zero. Numerical source values had also been visible during source-structure inspection before the protocol freeze, so this is not blind confirmation. It does not test the original fitted R13 weights or establish physical-well equivalence. See [the eLife stress-test record](docs/ELIFE_SPARSE_STRESS.md).

## Report and submission materials

- [Concise technical report PDF](docs/DosePilot_Technical_Report_Public.pdf) (historical report)
- [R33 reproduction and R34 experiment addendum](docs/KAGGLE_R33_ADDENDUM.md)
- [Separately optimized interpolation control](docs/POST_SUBMISSION_CONTROL.md)
- [Separate external CRC confirmation](docs/EXTERNAL_CRC_CONFIRMATION.md)
- [External matched-CAF stromal stress test](docs/STROMA_CONTEXT_CONFIRMATION.md)
- [Calibrated interpolation comparator audit](docs/CALIBRATED_CONTROL_AUDIT.md)
- [Evidence ledger and cohort deduplication](docs/EVIDENCE_LEDGER.md)
- [Protected Lib2 exact22 incomplete-study record](docs/LIB2_EXACT22_INCOMPLETE.md)
- [Public eLife sparse-reconstruction stress test](docs/ELIFE_SPARSE_STRESS.md)
- [Public-workbook reproduction commands](docs/PUBLIC_REPRODUCTION.md)
- [Kaggle writeup](docs/KAGGLE_WRITEUP.md)
- [Method and scope](docs/METHOD_AND_LIMITS.md)
- [Data and reproduction notes](docs/DATA_AND_REPRODUCTION.md)

## Repository contents

- `demo/`: operating predictor, recovery logic, fictional inputs, and replay scripts.
- `study/engine/`: original scientific modules used by the project.
- `study/acquire_public_source.py`: verifies or downloads the exact public Mendeley Data S4 workbook.
- `study/PUBLIC_SOURCE.json`: pinned public dataset/file identity, licence metadata and SHA-256.
- `study/reproduce_compact.py`: scientific replay using one reconstructed TRAIN CSV.
- `study/prepare_compact_source.py`: metadata-driven public-workbook to TRAIN reconstruction.
- `study/TRAIN_CATALOG.json`: fixed patient-free drug/dose catalog, with a separate provenance notice.
- `study/reproduce_train.py`: historical 16-file-kit reproduction wrapper, retained unchanged.
- `study/prepare_from_source_v3.py`: exact-byte Lib1 TRAIN source importer.
- `study/external_elife_sparse/`: frozen protocol, runner, and synthetic tests for the public eLife retrospective stress test.
- `evidence/`: aggregate, non-patient-level result summaries.

## Scope and license

DosePilot is research software. The public repository does not include patient measurements, the original source workbook, or the private fitted biological model.

Original project code, documentation, and fictional fixtures are released under the [MIT License](LICENSE). External papers, datasets, and dependencies retain their own rights; see [NOTICE](NOTICE.md).

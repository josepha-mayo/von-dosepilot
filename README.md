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

## Report and submission materials

- [Concise technical report PDF](docs/DosePilot_Technical_Report_Public.pdf) (historical report)
- [R33 reproduction and R34 experiment addendum](docs/KAGGLE_R33_ADDENDUM.md)
- [Separately optimized interpolation control](docs/POST_SUBMISSION_CONTROL.md)
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
- `evidence/`: aggregate, non-patient-level result summaries.

## Scope and license

DosePilot is research software. The public repository does not include patient measurements, the original source workbook, or the private fitted biological model.

Original project code, documentation, and fictional fixtures are released under the [MIT License](LICENSE). External papers, datasets, and dependencies retain their own rights; see [NOTICE](NOTICE.md).

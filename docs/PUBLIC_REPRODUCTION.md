# R33: public-workbook reproduction

This route reconstructs the retained R9/R13 **development results**, not a new validation score. It replaces the old 16-file private input bundle with an exact public workbook, executable metadata-selection rules and a 29,451-byte drug/dose catalog containing no individual sample, patient or run identifiers.

## Run from the repository root

Use Python 3.12 or 3.13 and install the pinned study dependencies in a new environment. The demo-only requirements are not sufficient for the scientific replay.

```bash
python -m venv .study-venv
# Linux/macOS:
source .study-venv/bin/activate
# Windows instead: .study-venv\Scripts\activate
python -m pip install -r study/requirements.txt
python study/acquire_public_source.py --output Data_S4.xlsx
python study/prepare_compact_source.py --source-xlsx Data_S4.xlsx --output reconstructed_train --execute-lib1-only
python study/reproduce_compact.py --curves reconstructed_train/train_curves.csv --output reconstructed_results
```

All output paths must be new. Do not overwrite, delete or silently retry a failed attempt. The acquisition step requires internet access; reconstruction and fitting need no API, GPU, paid service or private account. If the exact verified workbook is already present, use that file rather than downloading it again.

The scientific command emits four comparisons and returns success only when each agrees with the frozen result within absolute MSE tolerance `1e-12`. Keep the input, source and result receipts together.

## Exact identities

The source is Mendeley Data v3, DOI `10.17632/hr94h42xdc.3`, file `Data S4.xlsx`, 15,886,254 bytes. Its SHA-256 is `3847aa93b2a84c7d5d0b04c26494f39f35963fc41e96eae97d8a180fbc33d81c`.

The reconstructed TRAIN CSV must hash to `b192dc242362d74c4faa941752792336c7610d9bd403cccbf1cee7a8a1fc7c94`. Similar data, a changed workbook or altered metadata do not qualify as this reproduction.

## What the reconstruction does

The first pass reads only input metadata, fixes all 24 target drugs and their original dose intervals, and chooses the earliest naturally ordered eligible Lib1 run for each sample. Eligibility requires both source plates and complete dose support. It must recover exactly 119 samples, 59 whole patients and 49,504 selected wells before any viability value is requested.

The second pass consumes the same authenticated workbook bytes. It uses the original reviewed extractor to decode only the declared Lib1 TRAIN viability cells. Required nonnumeric, missing or nonfinite values cause failure, not imputation or removal of the sample. The resulting CSV is checked against its exact historical byte identity before it is written.

The compact loader rebuilds all target integrals, native measurements, query descriptors and physical-well identities. The 16 scientific engine files, study lock, acquisition method, patient folds and model-selection procedure remain unchanged. Each alternative predicts from 64 treatment wells, split 32 per plate. The evaluation averages alternative **losses**, never two alternatives' predictions.

## Expected patient-balanced MSE

| Procedure | Frozen MSE |
|---|---:|
| R9 own-drug heads | 0.0017214230057830812 |
| R9 shared heads | 0.002136395428366182 |
| R13 broader coverage | 0.001144858681382854 |
| Matched paired-native control | 0.001737932637554947 |

## Tests and evidence

```bash
PYTHONPATH=study/engine python -m unittest discover -s study -p 'test_compact*.py' -v
```

On Windows, set `PYTHONPATH` to `study/engine` in the current shell first. There are 34 unique tests covering metadata-only selection, protected-library exclusion, complete targets and population, physical identities, fixed hashes, duplicate wells/doses, malformed XML and invalid measurements.

`evidence/r33_compact_input_replay.json` records the exact prepared-input comparison: all 39,032 native input scalars and well identities matched, all 18 representation checks passed and all four model metrics reproduced. That earlier check alone is not the public-workbook execution; the composed source/replay result is recorded separately.

## Scope and interpretation

This is retrospective reconstruction of measured response summaries in the already-exposed TRAIN cohort. It does not establish clinical benefit, prospective organ-on-chip performance, calibrated uncertainty or independent predictive validation. Reproducing an MSE is not lowering that MSE.

The workbook contains broader study data. XML and shared-string parsing necessarily encounters uninterpreted bytes; the access claim is **zero semantic/numerical Lib2 response conversions**, not that no Lib2 bytes exist in the file. No raw-signal values are converted. The protected independent cohort is not a permitted extension of this command.

Generated result directories contain patient-level measurements, predictions and fitted weights. Keep them outside a public commit. This repository distributes code, a patient-free catalog and aggregate evidence, not the workbook or patient arrays. A Python input audit is not an operating-system security sandbox.

The author deposit lists CC BY 4.0. Cite Kryeziu, Sveen and Lothe, Mendeley Data v3, DOI `10.17632/hr94h42xdc.3`, and the study DOI `10.1016/j.xcrm.2026.102840`. External data and derived metadata retain their applicable attribution requirements; the project's MIT licence does not relicense the dataset. See `study/TRAIN_CATALOG_NOTICE.md`.

The existing PDF and original experiment reports are historical documents. This addendum and its execution receipts describe the new reproduction route without rewriting earlier failures or claiming a new biological result.

## Completed source-to-results execution

The exact public-workbook reconstruction and subsequent fresh-environment model replay both passed. The source stage decoded exactly 49,504 TRAIN values with zero Lib2 numerical response and raw-signal conversions. All four model comparisons matched, with maximum absolute difference 2.168404344971009e-19. The composed receipt is `evidence/r33_public_pipeline.json`; clean-environment test output is `evidence/r33_clean_tests.txt`. Earlier component-only receipts retain their original scope flags and are not silently rewritten as end-to-end results.

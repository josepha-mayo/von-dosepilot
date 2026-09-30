# Data access and reproduction

## Current status: R33 source-to-results route verified

The historical biological development results can now be rebuilt without the old private metadata bundle. The new route combines the exact public Data S4 workbook, an executable input-only selection recipe, a patient-free drug/dose catalog and the unchanged scientific engines.

The public-workbook reconstruction recovered the exact historical TRAIN CSV: 119 samples from 59 patients and 49,504 measurements. A subsequent model replay in a newly installed isolated environment matched all four frozen R9/R13 MSEs; the largest absolute difference was `2.168404344971009e-19`. Thirty-four unique fixture tests also passed in that environment.

See [complete commands, scope and expected outputs](PUBLIC_REPRODUCTION.md) and [the composed execution receipt](../evidence/r33_public_pipeline.json). This is a completed reproducibility improvement, **not new predictive accuracy or independent validation**.

## Three distinct routes

The fictional operating demo remains `python run_demo.py --output NEWDIR`. It needs only Python and NumPy and demonstrates runtime behaviour rather than biological accuracy.

The new biological route is:

```bash
python -m pip install -r study/requirements.txt
python study/acquire_public_source.py --output Data_S4.xlsx
python study/prepare_compact_source.py --source-xlsx Data_S4.xlsx --output rebuilt_train --execute-lib1-only
python study/reproduce_compact.py --curves rebuilt_train/train_curves.csv --output rebuilt_results
```

The original `reproduce_train.py --inputs ...` route is retained unchanged for historical compatibility. It still expects its old 16-file kit. That kit is neither distributed nor required by the new compact route.

## Public source and attribution

The author deposit is Mendeley Data v3, DOI `10.17632/hr94h42xdc.3`, listed as CC BY 4.0. `Data S4.xlsx` has file ID `7302f514-ae1f-42a4-a0f9-77d4ebf468e9`, 15,886,254 bytes and SHA-256 `3847aa93b2a84c7d5d0b04c26494f39f35963fc41e96eae97d8a180fbc33d81c`.

- Author dataset: https://data.mendeley.com/datasets/hr94h42xdc/3
- Source study: https://doi.org/10.1016/j.xcrm.2026.102840
- Article record: https://pubmed.ncbi.nlm.nih.gov/42208542/

Credit Kryeziu, Sveen and Lothe. The dataset and applicable derived metadata retain their external attribution requirements. Original project code is MIT-licensed; it does not relicense the author dataset. See [catalog notice](../study/TRAIN_CATALOG_NOTICE.md).

## Access and evidence limits

Both reconstruction passes consume the same authenticated workbook snapshot. Input metadata determines eligibility before viability access. The execution logged 49,504 selected TRAIN viability conversions, zero Lib2 numerical response conversions and zero raw-signal conversions. XML parsing still encounters uninterpreted workbook bytes; these counts are not a claim of a byte-level security boundary.

The first resource-bounded reconstruction attempt timed out during metadata parsing before its numerical-access marker. It is preserved. The unchanged successor received an explicitly reviewed longer wall-clock allowance and completed in 495.07 seconds on a shared laptop. The model process completed in 69.99 seconds; its internal replay timer was 49.15 seconds. Those are operational timings, not general hardware benchmarks.

The source extraction used an existing Python 3.12.3 / NumPy 2.3.5 environment. The tests and model replay used a new isolated environment with all six pinned study dependencies. This is not a claim that an independent reviewer reproduced the work or that every stage ran on a clean new machine.

The protected independent cohort remains excluded. No clinical benefit, prospective organ-on-chip performance, calibrated uncertainty or new predictive improvement is established. Generated patient-level data and fitted outputs stay local and are not part of the public repository.

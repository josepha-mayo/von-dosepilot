# DosePilot technical addendum: public reproduction completed

30 September 2026. This repository addendum does not, by itself, confirm that the Kaggle page text has been edited.

## A reproducible biological result, not only a synthetic demo

DosePilot's four historical R9/R13 development results can now be reconstructed from the exact public Mendeley Data v3 workbook without the old private input bundle. The source recipe recovered the historical 119-sample, 59-patient TRAIN population and all 49,504 selected measurements, with a byte-identical output CSV.

A new isolated environment then rebuilt the plans, fits and predictions through the unchanged scientific engines. All four patient-balanced MSEs matched the study lock within absolute tolerance `1e-12`; the largest observed difference was `2.168404344971009e-19`. All 34 unique reconstruction/loader fixture tests passed in that environment.

The public route now consists of the acquisition helper, `prepare_compact_source.py`, a patient-free fixed drug/dose catalog, and `reproduce_compact.py`. It requires no GPU, paid API, private account or nonpublic dataset. Acquisition needs internet; the remaining computation is local. Full instructions and aggregate execution evidence are in [PUBLIC_REPRODUCTION.md](PUBLIC_REPRODUCTION.md) and [r33_public_pipeline.json](../evidence/r33_public_pipeline.json).

The first metadata-only attempt timed out under its initial wall-clock limit. The preserved unchanged successor completed after a reviewed runtime allowance change. The source step used an existing matching Python/NumPy environment; tests and model replay used the fresh environment. This was coordinator verification, not independent external certification.

## A tested challenger that was not promoted

A prespecified additive nonlinear own-drug predictor was tested at the same physical budget and patient-separated nested evaluation. Its MSE was 0.001146185234155711 versus the retained control's 0.0011448586813828535, a 0.1158704% increase. It failed the promotion screen. R13 remains retained. The negative result, all target/fold summaries and verification are preserved in [R34_NEGATIVE_RESULT.md](R34_NEGATIVE_RESULT.md).

## Unchanged limits

These are adaptive retrospective development results, not an independent test or clinical claim. The public-workbook run logged zero numerical Lib2 response conversions and zero raw-signal conversions. The protected independent cohort remains excluded. The study used ordinary organoid plates, not a prospective organ-on-chip experiment. Source data remain credited to Kryeziu, Sveen and Lothe under the deposit's listed CC BY 4.0 terms; no patient-level arrays or fitted biological weights are published here.

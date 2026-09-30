# Data access and reproduction: current limits

## Route A: invented operating workflow

The complete runnable input and invented model are in `demo/`. `python run_demo.py --output NEWDIR` needs only Python and NumPy. It demonstrates software behavior, not the biological accuracy score.

## Route B: prepared-data reproduction

The original wrapper and 16 unchanged scientific engines are in `study/`. In the earlier R16 run, the separately held prepared Lib1 inputs regenerated the reported R9/R13 measurements, plans and fitted outputs.

After an exact-hash input kit is available, the command shape is:

```bash
python -m pip install -r study/requirements.txt
python study/reproduce_train.py --inputs /path/to/input_kit --output new_reproduction
```

The complete prepared input kit is not yet supplied by this public release. `STUDY_LOCK.json` names every required file, byte hash, dependency version and expected metric. Do not substitute similar data and call it an exact reproduction.

## Route C: exact public source

The source workbook identity is now resolved, not inferred. Mendeley Data version 3 publicly lists `Data S4.xlsx` with:

- dataset DOI: `10.17632/hr94h42xdc.3`
- listed licence: `CC BY 4.0`
- file id: `7302f514-ae1f-42a4-a0f9-77d4ebf468e9`
- byte count: `15,886,254`
- SHA-256: `3847aa93b2a84c7d5d0b04c26494f39f35963fc41e96eae97d8a180fbc33d81c`

That SHA-256 is exactly the historical workbook lock used by DosePilot. The project no longer relies on a merely similar or unverified public download.

The anonymous metadata route and exact expected identity are pinned in `study/PUBLIC_SOURCE.json`. Verify the live public record without downloading the workbook:

```bash
python study/acquire_public_source.py --check-only
```

Or acquire the exact public workbook with byte-count and SHA-256 verification:

```bash
python study/acquire_public_source.py --output Data_S4.xlsx
```

The importer `study/prepare_from_source_v3.py` authenticates that exact workbook before parsing and restricts numerical viability reads to the declared Lib1 TRAIN selection. It does not authorize a protected independent-test read.

## What is still missing for full public biological reproduction

The remaining gap is narrower: the frozen TRAIN selection, contract and query metadata needed to convert the public workbook into the exact prepared input kit are not yet published as a reviewed public bundle. The source workbook itself is no longer the blocker.

Full public reproduction will be claimed only after that metadata route is released, the source-to-prepared conversion is executed from the public route, and `reproduce_train.py` regenerates the locked R9/R13 metrics in a clean environment.

## Provenance

- Article: https://pubmed.ncbi.nlm.nih.gov/42208542/
- Study DOI: https://doi.org/10.1016/j.xcrm.2026.102840
- Author dataset: https://data.mendeley.com/datasets/hr94h42xdc/3
- Dataset DOI: https://doi.org/10.17632/hr94h42xdc.3

The source dataset and this project's code have separate licences. DosePilot code and documentation are MIT-licensed; the cited Mendeley dataset is listed by its publisher as CC BY 4.0. External rights remain with their respective holders.

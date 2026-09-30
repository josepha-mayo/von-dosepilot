# Data access and reproduction: current limits

## Route A: invented operating workflow

The complete runnable input and invented model are in `demo/`. `python run_demo.py --output NEWDIR` needs only Python and NumPy. It demonstrates software behavior, not the biological accuracy score.

## Route B: already-verified prepared-data reproduction

The original wrapper and 16 unchanged engines are in `study/`. In the earlier R16 run, the separately held prepared Lib1 inputs regenerated the reported R9/R13 measurements, plans and fitted outputs. That historical check was on an existing environment, not a clean public installation.

After a legitimately available, exact-hash input kit exists, the command shape is:

```bash
python -m pip install -r study/requirements.txt
python study/reproduce_train.py --inputs /path/to/authorized/input_kit --output new_reproduction
```

**The required input kit is not publicly supplied by this public code release.** Do not run this command with substituted data or call it an anonymously reproducible public result. `STUDY_LOCK.json` names all required files, hashes, dependency versions and output expectations.

## Route C: exact original source

The code-only v3 helper is included for inspection. It parses the same byte snapshots it authenticates and applies the existing Lib1-only selection. It has been tested on invented fixtures, not end to end on the exact original workbook. It requires the original workbook plus separate frozen metadata templates. Those templates and the original workbook are NOT bundled here.

Public source records for provenance, not a permission determination:
- Article: https://pubmed.ncbi.nlm.nih.gov/42208542/
- DOI: https://doi.org/10.1016/j.xcrm.2026.102840
- Author deposit: https://data.mendeley.com/datasets/hr94h42xdc/3

The exact historical workbook SHA256 is `3847aa93b2a84c7d5d0b04c26494f39f35963fc41e96eae97d8a180fbc33d81c`. A changed download is not silently treated as the same input. A URL is not proof of byte identity or redistribution rights.

## Public source status

The associated authors' dataset is publicly listed at Mendeley Data version 3:

- Dataset: https://data.mendeley.com/datasets/hr94h42xdc/3
- DOI: https://doi.org/10.17632/hr94h42xdc.3
- Listed licence: Creative Commons Attribution 4.0 International
- Data S4 is described by the authors as the raw drug-sensitivity screening measurements, including sample, run, library, compound, concentration, plate/well, signal and normalized viability fields.

This materially improves the public provenance route, but it does **not** by itself prove that the historical workbook used by DosePilot is byte-identical to a particular Mendeley file. The project therefore keeps the historical SHA256 lock and refuses to silently substitute a changed or merely similar download.

## Required before claiming full public reproduction

Resolve applicable source and derived-asset permissions; publish an approved complete metadata/acquisition route without private-account dependency; conduct the specifically authorized source reconstruction using the reviewed exact contract; retain a terminal failure or exact output comparison; and verify installation/run from that public route. None of those steps is completed merely by including this document. No protected independent test is authorized by possession of this code.

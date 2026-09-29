# von DosePilot

**24 research response summaries from 64 traceable treatment wells.**

MIT-licensed research software by Joseph Ayanda. This repository contains a runnable **synthetic operating demo**, original study code and historical aggregate evidence. It does not contain patient measurements or the trained biological model.

## Run the demonstration

```bash
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt
python run_demo.py --output demo_run_001
```

Use a fresh output directory. The recorded environment is Python 3.13.5 and NumPy 2.3.5. No GPU, API key or model API is needed. All model parameters and measurements used by the demo are **fictional**; its output is not the study's accuracy result.

The demo commits a 64-well layout (32 per plate), produces 24 predictions, withholds one affected prediction when an input is null, rejects a wrong dose and an insufficient budget, and recovers the SAME committed layout after an intentional export failure. Expected error exits are deliberate test cases.

## Read the report

[Concise technical report](docs/DosePilot_Technical_Report.md) | [Method and limitations](docs/METHOD_AND_LIMITS.md)

## Historical evidence, separate from the demo

| Complete procedure | Patient-balanced MSE |
|---|---:|
| Earlier paired-well comparator, R9 | 0.0017214230 |
| Matched paired-native comparator | 0.0017379326 |
| Retained broader-coverage procedure, R13 | **0.0011448587** |

The retrospective development comparison used 119 organoid samples from 59 whole patients at the same 64-treatment-well budget. Error decreased 33.49% versus R9 and 34.13% versus the matched control. Six drugs and six patients worsened versus R9; Gedatolisib and Palbociclib together worsened 20.94%. R18 has the slightly lower observed point, 0.0011414048, but did not pass the original replacement rule. R13 is the retained operational procedure, not the literal minimum observed score.

These are repeated-development findings, **not independent validation**, prospective organ-on-chip results, a clinical claim, or evidence of actual monetary/material savings. See `evidence/aggregate_results.json`.

## Repository contents

- `demo/`: original operating predictor, committed-plan recovery, fictional inputs and replay scripts.
- `study/engine/`: 16 unchanged original scientific modules.
- `study/reproduce_train.py`: locked prepared-data reproduction wrapper.
- `study/prepare_from_source_v3.py`: exact-byte source importer, supplied for inspection.
- `docs/`: concise report, attribution and explicit reproduction limits.

## Biological reproduction status

**The historical biological results are not yet reproducible from this public repository alone.** The private prepared-input kit and metadata templates are excluded. The prepared-data route previously reproduced recorded R9/R13 results, but the original-source importer has only been fixture-tested. Do not substitute the synthetic demo for biological reproduction. Read [data and reproduction status](docs/DATA_AND_REPRODUCTION.md) for exact requirements and source provenance.

## Scope and license

The operating model instantiates a fixed supported inventory plan; it does not optimize arbitrary budgets or silently substitute concentrations. Independent validation and the 64-well second-library adapter remain unresolved. This is research software, not a clinical tool.

Original code, documentation and fictional fixtures: [MIT License](LICENSE). External papers, datasets and dependencies retain their own rights; see [NOTICE](NOTICE.md).

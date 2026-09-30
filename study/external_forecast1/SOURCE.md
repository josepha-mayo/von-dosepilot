# External FORECAST-1 source

This directory contains original DosePilot analysis code only. It does **not** redistribute the source workbooks or patient-level predictions.

Source article: Tan et al., *Cell Reports Medicine* (2023), DOI `10.1016/j.xcrm.2023.101335`, PMCID `PMC10783557`.

The article's supplementary archive is available from Europe PMC:

```text
https://www.ebi.ac.uk/europepmc/webservices/rest/PMC10783557/supplementaryFiles
```

Extract these files locally:

| File | Role | SHA-256 |
|---|---|---|
| `mmc3.xlsx` | community single-agent development cohort | `dadea8de4da8b67456dd930f13370058e94097a36e8891bc38b4e77affcd92ea` |
| `mmc5.xlsx` | FORECAST-1 external cohort | `9bc3611ba8d45c4ed31ebf28bae0e5ce91b9349bf09f616eefb158e02ec89d63` |
| `mmc4.xlsx` | article processed-AUC table used only for a post-hoc secondary check | `c769732edc1ef21bdf8981bbf6ffa141c390a1a5af839a908a63e86ed1b165a9` |

The source article is distributed under CC BY-NC-ND 4.0. The repository's MIT license applies to original DosePilot code and documentation, not to these source workbooks.

## Reproduce the support-complete sensitivity analysis

Create a fresh Python environment and install:

```bash
python -m pip install -r study/external_forecast1/requirements.txt
```

Copy the three verified source workbooks into a private working directory. Preserve a new output directory for every attempt.

From `study/external_forecast1/`:

```bash
python -m unittest discover -s . -p 'test_support_complete_sensitivity.py' -v
python support_complete_sensitivity.py \
  --community /path/to/mmc3.xlsx \
  --forecast /path/to/mmc5.xlsx \
  --processed /path/to/mmc4.xlsx \
  --protocol PROTOCOL_SUPPORT_COMPLETE.md \
  --output /new/path/attempt
```

The program commits external prediction arrays before it calculates aggregate FORECAST-1 scores. Generated predictions contain patient-level data and must stay outside public commits.

This is a later support-complete sensitivity analysis, not a replacement for the prefrozen eight-drug confirmation in `docs/EXTERNAL_CRC_CONFIRMATION.md`.

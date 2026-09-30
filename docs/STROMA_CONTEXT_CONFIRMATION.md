# External stromal-context confirmation

30 September 2026. This is a post-submission external stress test of the DosePilot sparse reconstruction **design pattern**, not direct validation of the original 24 fitted R13 heads.

## Separate public dataset

The source is Farin et al., *Cancer Discovery* (2023), DOI `10.1158/2159-8290.CD-23-0050`, PMCID `PMC10551667`. The matched organoid/CAF dataset is Mendeley Data v1, DOI `10.17632/fypp6xhkjy.1`. The exact source file used here is `Drug_sensitivity_all_lines.txt`, SHA-256 `f9a9a51fd77ae1a5b19ad71fc236ce446223b3c2fcc66631ab304ab69bec78f0`.

The paper and dataset describe colorectal-cancer patient-derived tumor organoids tested against 5-FU, oxaliplatin, SN-38 and gefitinib in mono- and CAF coculture. Their CC BY-NC-ND 4.0 source data are not redistributed by this repository.

## Frozen split before outcomes

Only source metadata fields were decoded while defining the study. No RLU value had been interpreted when the protocol, parser, model family, comparator, split and gate were frozen.

Development used 13 metadata-complete **monoculture organoid IDs**. Primary confirmation used 15 different organoid IDs with metadata-complete, same-numeric matched tumor-CAF cocultures. The two ID sets have zero overlap. We do not claim the IDs prove 28 distinct patients because that mapping was not independently established for this split.

One metadata-incomplete remaining organoid was excluded before any outcomes. No confirmation organoid was removed after outcomes.

## Fixed reconstruction task

For each organoid/condition/drug, replicate RLU values are averaged at each concentration and normalized by the same drug/condition DMSO mean. The target is unclipped trapezoidal AUC over log concentration across all seven positive source-native doses.

Each full condition therefore has 28 dose-level readouts. The sparse procedure uses 11 replicate-averaged readouts: two doses per drug plus three third-dose upgrades. These are **dose-level summaries, not physical-well counts**.

The learned procedure uses the original DosePilot idea: fitting-only covariance allocation (alpha 0.1), own-drug ridge heads and one shared penalty selected from `{0.01, 0.1, 1, 10}`. Development selection is leave-one-organoid-out and rebuilds planning/scaling/fitting inside every fold.

The comparator is constant-tail piecewise-linear log-dose interpolation. It independently optimizes its own dose subsets and upgrades under the identical 11-readout budget.

Development selected ridge penalty 0.1. Leave-one-organoid-out MSE was **0.0083621** for learned reconstruction versus **0.0118516** for optimized interpolation. Confirmation outcomes were still unopened.

## One-shot matched-CAF confirmation

The confirmation intent pinned the exact source, protocol, parser, confirmation code, final model, both acquisition plans, 15 organoid/fibroblast pairs and a four-part promotion gate before any confirmation RLU field was decoded.

| Primary matched coculture | Learned | Optimized interpolation |
|---|---:|---:|
| MSE | **0.0029697** | 0.0052366 |
| RMSE | **0.05450** | 0.07236 |
| p90 organoid RMSE | **0.06666** | 0.10986 |

Learned reconstruction had **43.29% lower MSE**, won **10/15 organoid means**, and was nonworse on **3/4 drug MSEs**. The fixed-seed descriptive bootstrap interval for learned-minus-interpolation mean organoid MSE was **[-0.004234, -0.000497]**.

All four prefrozen gate components passed:
1. lower primary coculture MSE;
2. at least 9/15 strict organoid wins;
3. at least 3/4 drug MSEs nonworse;
4. nonworse p90 organoid RMSE.

There was no retuning, post-outcome exclusion, prediction clipping or automatic confirmation retry.

The prespecified secondary held-out monoculture diagnostic also favored learned reconstruction: MSE **0.0036080** versus **0.0057686** for interpolation. The change from held-out monoculture to coculture is descriptive only; it is not a causal estimate of CAF effects.

A second calculation reopened only the saved private prediction arrays, not the source file, and exactly reproduced the reported MSEs, gate counts and bootstrap interval.

## Reproduce aggregate results

Download the exact source file from Mendeley Data yourself; the repository does not redistribute it. Then run:

```bash
python -m venv .stroma-venv
source .stroma-venv/bin/activate   # Windows: .stroma-venv\Scripts\activate
python -m pip install numpy
PYTHONPATH=study/external_stroma python -m unittest study/external_stroma/test_stroma_common.py -v
python study/external_stroma/reproduce_stroma_confirmation.py \
  --source /path/to/Drug_sensitivity_all_lines.txt \
  --output stroma_reproduction_001
```

The reproduction command rebuilds development selection and the held-out aggregate metrics from the pinned source. It is post-confirmation reproducibility, not another blinded confirmation.

## Evidence boundary

This result strengthens evidence that the **sparse acquisition/reconstruction pattern** can transfer to different organoid data and a stromal coculture context. It does not establish:
- external validation of the original fitted R13 weights or all 24 original targets;
- 64 physical-well savings in this source experiment;
- unique-patient independence for every organoid ID in this split;
- clinical treatment benefit or calibrated uncertainty;
- prospective microfluidic or organ-on-chip hardware performance;
- an official competition score or rank.

The original R13 retrospective result, Tan et al. FORECAST-1 experiment, and this Farin et al. matched-CAF stress test answer different questions and should not be pooled into one invented accuracy number.

Aggregate evidence is in `evidence/stroma_context_confirmation_20260930.json`. The exact prefrozen protocol and original analysis code are under `study/external_stroma/`.
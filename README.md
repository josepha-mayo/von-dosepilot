# von DosePilot

**24 research response summaries from 64 traceable treatment wells.**

MIT-licensed research software by Joseph Ayanda for the AI4S Open Innovation challenge.

DosePilot treats measurement selection as part of the model. It chooses a fixed treatment-well layout, checks the identity of purchased observations, and reconstructs 24 dose-response curve areas. It is research software, not clinical treatment guidance.

## Latest verified research result: spectral residual successor

The new S2 model improves patient-balanced MSE from **0.0011448587 to 0.0010701439**, a **6.53% reduction versus R13**, using the same 119 samples, 59 whole patients, 24 targets and 64 physical treatment wells per deployment alternative.

| Comparison | S2 result |
|---|---:|
| MSE reduction versus retained R13 | **6.53%** |
| MSE reduction versus prior R18 reference | **6.24%** |
| Strict patient wins versus R13 / R18 | **49/59 / 47/59** |
| Favorable outer-fold means versus either reference | **5/5** |
| p90 patient expected RMSE, R13 to S2 | **0.041108 to 0.038733** |
| Original internal replacement criteria | **All pass against both references** |

These are **repeated adaptive development results**, not independent biological confirmation or an official competition score. Ten patients and four target means still regress versus R13. The accepted Kaggle entry and historical R13 operating demo remain intact while this research successor is integrated.

S2 keeps R13's acquisition and own-drug baseline, then learns a spectrally regularized correction from the same purchased values. No additional wells or hidden prediction ensemble are used. Because that correction shares information across drugs, **all 64 measurements are required**: a missing required value withholds every output, rather than only one drug head.

[Method, all results and limitations](docs/SPECTRAL_SUCCESSOR.md) · [Aggregate evidence and hashes](evidence/spectral_successor_20261001.json) · [Spectral source and tests](study/spectral_residual/)

## Run it

### Original operating demonstration

```bash
python -m pip install -r requirements.txt
python run_demo.py --output demo_run_001
```

The existing demonstration uses fictional measurements and parameters. It shows a committed physical layout, valid prediction, affected-head abstention for the original R13 dependency structure, wrong-dose rejection and recovery after export failure. This remains separate from the new global-correction inference command.

**Demo video:** https://youtu.be/QeOGJIgx378

### Reproduce and construct the spectral successor

Follow [the public-workbook workflow](docs/PUBLIC_REPRODUCTION.md) to reconstruct the exact Lib1 TRAIN CSV and install `study/requirements.txt`. Then:

```bash
python study/spectral_residual/reproduce.py --curves reconstructed_train/train_curves.csv --output spectral_replay --fit-final
```

A fresh repository clone on the author's laptop reproduced the new MSE and all 49 patient wins without the old private input kit or historical predictions. The final model constructor selected spectrum fraction 0.1 and ridge penalty 1 using a fixed training-only split. Construction is not another validation result.

```bash
python study/spectral_residual/inference.py --model-dir spectral_replay/final_model --measurements measurements.json --output prediction.json
```

The [inference request format and missing-input rules](docs/SPECTRAL_SUCCESSOR.md#inference-and-the-important-missing-data-tradeoff) bind sample, run, drug, exact concentration, plate and well identities. The wrapper cannot verify the physical origin of a number supplied by a caller. It does not replace laboratory quality assurance or the existing inventory-commitment workflow.

No GPU, language-model API or paid model service is required for reproduction or runtime. Input acquisition uses the separately licensed public source; generated patient arrays and biological model weights should stay outside public commits.

## Verification

**33 unique synthetic tests passed**, covering spectral algebra, physical-planner equivalence, serialization and input rejection. A separate explicit-patient-loop audit passed **894 checks**, including all internal gates and five alternative-whitening model checks. The constructed artifact also passed **238 sample/orientation input comparisons** and all **64 single-missing-position checks**. Those runtime checks use training records; they are not independent biological observations. The attempted external reviewer batch produced zero completed reviews and is not counted as validation.

## Evidence beyond the development score

The external studies evaluate adaptations of the sparse-reconstruction design, not S2's fitted parameters. Their qualifications remain unchanged:

- [Matched-CAF stromal assessment](docs/STROMA_CONTEXT_CONFIRMATION.md): original support gate passed; [published patient-case identities were checked separately](docs/STROMA_PATIENT_IDENTITY_AUDIT.md).
- [FORECAST-1](docs/EXTERNAL_CRC_CONFIRMATION.md) and [eLife retrospective stress test](docs/ELIFE_SPARSE_STRESS.md): original support gates did not fully pass. [Calibrating the interpolation control](docs/CALIBRATED_CONTROL_AUDIT.md) narrowed the FORECAST advantage.
- [Protected22](docs/PROTECTED22_RESULT.md): full primary not estimable because five required responses were nonnumeric; prior cross-session exposure prevents an untouched-cohort claim. [All planned records are marked exposed](evidence/PROTECTED22_ACCESS_STATUS.json). S2 did not read them.

[Evidence ledger](docs/EVIDENCE_LEDGER.md) · [Full pre-spectral README, preserved unchanged](README_PRE_SPECTRAL_20261001.md)

## Submission materials and scope

[Prepared Kaggle writeup](docs/KAGGLE_WRITEUP.md) · [Historical technical PDF](docs/DosePilot_Technical_Report_Public.pdf) · [Current spectral addendum](docs/SPECTRAL_SUCCESSOR.md) · [Declared organ-on-chip constraint compiler](docs/OOC_FEASIBILITY.md)

The historical PDF and prepared writeup predate the spectral result; the addendum supplies the current research evidence. A file in this repository is not proof that the live Kaggle entry was edited. No duplicate entry, official rank improvement, prospective laboratory saving, clinical benefit or S2 external validation is claimed.

Original project code, documentation and fictional fixtures use the [MIT License](LICENSE). External papers, datasets and dependencies retain their own rights; see [NOTICE](NOTICE.md) and the study-specific documentation. The repository contains no patient arrays or fitted biological weights.

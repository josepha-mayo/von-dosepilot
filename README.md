# von DosePilot

**24 research response summaries from 64 traceable treatment wells.**

MIT-licensed research software by Joseph Ayanda for the AI4S Open Innovation challenge.

DosePilot treats measurement selection as part of the model. It chooses a fixed treatment-well layout, checks the identity of purchased observations, and reconstructs 24 dose-response curve areas. It is research software, not clinical treatment guidance.

## 2 October update: stronger control, explicit missing-reading recovery

A previously completed additive-kernel result was independently rebuilt at **MSE 0.001060552730**, versus S2's 0.001070143945, with the same 119 samples, 59 patients, 24 targets and 64-well budget. It improves 45/59 patient means and all five folds against S2, and passes the original R13/R18 development checks. This is a reproduced shared-workspace result, not a new independent validation. Two newly tested structured kernels did not beat that stronger control and were rejected.

The new optional recovery command preserves a different kind of value: with one explicitly missing reading and otherwise valid committed identities, it can return **23 clearly labelled older own-drug baseline estimates** while withholding the affected head and **all additive-model predictions**. It never imputes the missing value. The normal primary path still requires all 64 inputs. A separate completion command verifies that observations recorded during recovery have not been rewritten before producing the complete primary result.

```bash
python study/hybrid_residual/run_baseline_recovery_demo.py --output recovery_demo_001
```

This one-command example is entirely fictional and downloads no patient data. It demonstrates 0 primary outputs and 23 baseline-only outputs, not new biological accuracy. [Results, commands and limits](docs/STRUCTURED_KERNELS_AND_RECOVERY.md) · [Source-bound evidence](evidence/structured_kernels_recovery_20261002.json)

## S2 spectral successor: 1 October benchmark

The S2 model improves patient-balanced MSE from **0.0011448587 to 0.0010701439**, a **6.53% reduction versus R13**, using the same 119 samples, 59 whole patients, 24 targets and 64 physical treatment wells per deployment alternative.

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

The recommended runtime is now a two-stage, hash-bound workflow: commit an exact caller-declared 64-well inventory before responses are supplied, then fill its template and predict. It requires 32 treatment wells per plate, separate declared vehicle and viability controls, an externally recorded construction hash and create-exclusive evidence records.

```bash
python study/spectral_residual/operating_workflow.py commit \
  --model-dir spectral_replay/final_model \
  --construction-sha256 <previously-recorded-sha256> \
  --inventory inventory.json \
  --commitment committed_plan.json \
  --template measurements_to_fill.json \
  --ledger-dir spectral_operating_ledger

python study/spectral_residual/operating_workflow.py predict \
  --model-dir spectral_replay/final_model \
  --construction-sha256 <previously-recorded-sha256> \
  --commitment committed_plan.json \
  --measurements completed_measurements.json \
  --output prediction.json \
  --ledger-dir spectral_operating_ledger
```

The [operating contract and missing-input rules](docs/SPECTRAL_SUCCESSOR.md#hash-bound-operating-workflow) bind model, plan, sample, run, drug, exact concentration, plate, well and measurement bytes. They cannot verify the physical origin of a caller-supplied number, make an editable filesystem immutable or replace laboratory quality assurance.

No GPU, language-model API or paid model service is required for reproduction or runtime. Input acquisition uses the separately licensed public source; generated patient arrays and biological model weights should stay outside public commits.

## Verification

**42 spectral/runtime tests and six fast-planner tests passed**, covering spectral algebra, physical-planner equivalence, serialization, response-independent commitment, trust anchors, exact inventory binding, controls, concurrent once-only recording, create-exclusive evidence and input rejection. A separate explicit-patient-loop audit passed **894 checks**, including all internal gates and five alternative-whitening model checks. The constructed artifact also passed **238 sample/orientation input comparisons** and all **64 single-missing-position checks**. Fifteen additional consistency tests reconcile the public evidence index with four independently pinned receipt hashes and finalized judge-facing documents. These are software checks, not independent biological observations. The attempted external reviewer batch produced zero completed reviews and is not counted as validation.

The 2 October update adds 33 new synthetic cases. Its kernel/runtime regression suite passes 64 tests, including the 21 new recovery/completion cases. Separate audits verify 216 numerical comparison groups and 15,232 artificial missing-input cases. [Exact counts, overlap and limitations](docs/STRUCTURED_KERNELS_AND_RECOVERY.md#checks-completed).

## Evidence beyond the development score

The external studies evaluate adaptations of the sparse-reconstruction design, not S2's fitted parameters. Their qualifications remain unchanged:

- [Matched-CAF stromal assessment](docs/STROMA_CONTEXT_CONFIRMATION.md): original support gate passed; [published patient-case identities were checked separately](docs/STROMA_PATIENT_IDENTITY_AUDIT.md).
- [FORECAST-1](docs/EXTERNAL_CRC_CONFIRMATION.md) and [eLife retrospective stress test](docs/ELIFE_SPARSE_STRESS.md): original support gates did not fully pass. [Calibrating the interpolation control](docs/CALIBRATED_CONTROL_AUDIT.md) narrowed the FORECAST advantage.
- [Protected22](docs/PROTECTED22_RESULT.md): full primary not estimable because five required responses were nonnumeric; prior cross-session exposure prevents an untouched-cohort claim. [All planned records are marked exposed](evidence/PROTECTED22_ACCESS_STATUS.json). S2 did not read them. The baseline-recovery utility does not repair that study or change its denominator.

[Evidence ledger](docs/EVIDENCE_LEDGER.md) · [Full pre-spectral README, preserved unchanged](README_PRE_SPECTRAL_20261001.md)

## Submission materials and scope

[Prepared Kaggle writeup](docs/KAGGLE_WRITEUP.md) · [Historical technical PDF](docs/DosePilot_Technical_Report_Public.pdf) · [Spectral addendum](docs/SPECTRAL_SUCCESSOR.md) · [2 October research and recovery update](docs/STRUCTURED_KERNELS_AND_RECOVERY.md) · [Declared organ-on-chip constraint compiler](docs/OOC_FEASIBILITY.md)

The historical PDF predates the spectral result. The prepared repository writeup and spectral addendum include the 1 October evidence; the 2 October document supplies the newer work. A file in this repository is not proof that the live Kaggle entry was edited. No duplicate entry, official rank improvement, prospective laboratory saving, clinical benefit or new external validation is claimed.

Original project code, documentation and fictional fixtures use the [MIT License](LICENSE). External papers, datasets and dependencies retain their own rights; see [NOTICE](NOTICE.md) and the study-specific documentation. The repository contains no patient arrays or fitted biological weights.

# DosePilot target definitions

The exact 24 endpoint definitions, full source dose grids, integration bounds, quadrature rules, and frozen predictor doses are documented in:

**[docs/TARGET_DEFINITIONS.md](docs/TARGET_DEFINITIONS.md)**

Machine-readable metadata: evidence/target_definitions_20261003.json

Response-free verifier:

    python study/audits/verify_target_definitions.py --root .

Public-TRAIN reproduction:

    python study/audits/reproduce_target_definitions.py \
      --curves reconstructed_train/train_curves.csv \
      --output reproduced_target_definitions.json

This is a measurement/endpoint contract, not new biological validation.

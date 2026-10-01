# Organ-on-chip declared-constraint compiler

DosePilot's retrospective predictive evidence comes from ordinary organoid plates, not an organ-on-chip experiment. A plate treatment well is not automatically a chip, channel, circuit or run. The response-free logical resource compiler in `demo/ooc_feasibility.py` makes that boundary executable.

Given an already committed `von.acquisition.v1` plan and a caller-declared `von.ooc.inventory.v1`, it returns either:

- a deterministic manifest with all 64 treatment requests bound to exact drug, concentration, channel, circuit, reservoir, compartment, exposure and timepoint identities; or
- an incompatibility with a concrete reason.

The compiler rejects missing or substituted doses, duplicate physical/action/control identities, different exposures sharing one flow circuit or reservoir, missing treatment positions, plan-budget tampering, controls hidden inside the 64-treatment budget, and controls that reuse or share treatment/control circuits or reservoirs. Vehicle and viability controls are both mandatory and remain separate resources.

## Run the synthetic witness

First run the existing invented operating demo in a fresh directory:

```bash
python demo/run_operating_demo.py --output /tmp/dosepilot-demo
```

Create an explicitly synthetic one-independent-circuit-per-treatment inventory, then compile it:

```bash
python demo/ooc_feasibility.py make-synthetic-fixture \
  --plan /tmp/dosepilot-demo/plan.json \
  --output /tmp/dosepilot-ooc-inventory.json

python demo/ooc_feasibility.py compile \
  --plan /tmp/dosepilot-demo/plan.json \
  --inventory /tmp/dosepilot-ooc-inventory.json \
  --output /tmp/dosepilot-ooc-manifest.json
```

The fixture is invented and deliberately generous: each requested treatment receives an independent synthetic circuit. It is not a commercial device specification or proof that a laboratory has the resources. Its purpose is to demonstrate the contract and rejection paths without implying biological evidence.

Run the seventeen response-free tests:

```bash
cd demo
python -m unittest test_ooc_feasibility.py -v
```

## Claim boundary

A compatible manifest proves only that the unauthenticated, caller-declared resources satisfy the encoded logical constraints. It does not prove physical feasibility, vendor compatibility, laboratory execution, predictive performance, clinical utility, correct flow rate or volume, material/adsorption control, pump availability, tissue compatibility, calibrated uncertainty or prospective organ-on-chip validation. A real deployment must replace the synthetic fixture with a reviewed device/run inventory and add every protocol-specific constraint not represented here.

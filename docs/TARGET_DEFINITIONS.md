[Reading 103 lines from start (total: 103 lines, 0 remaining)]

# DosePilot target definitions

**Status: frozen development endpoint definition.** This page defines exactly what the 24 reported outputs mean. It adds no new biological result.

## The endpoint, mathematically

For drug target j and source plate r, let the supplied normalized viability observations be a piecewise-linear function of log concentration. On the fixed target interval [L_j, U_j], DosePilot's reference endpoint is:

    AUC_jr = integral(log(L_j)..log(U_j)) v_jr(x) dx / (log(U_j) - log(L_j))

The implementation evaluates that integral exactly as a trapezoid over the source dose nodes inside the interval, with **linear interpolation in log-dose at a boundary when the boundary is between source doses**.

The scored target is:

    target_j = (AUC_j,p1 + AUC_j,p2) / 2

Important consequences:

- the supplied viability values are **not clipped** before integration;
- the output is a dimensionless normalized log-dose AUC of the measured viability profile;
- it is **not IC50**, not a drug rank, and not a clinical response label;
- purchased DosePilot measurements can also be nodes that contribute to the measured reference AUC, so this is reconstruction of a measured full-profile summary, not recovery of a noiseless independent truth;
- A/B are alternative **input layouts**, not the two reference plates. Each A or B deployment consumes one frozen 64-well subset drawn across p1 and p2; the target definition itself always averages the full p1 and p2 AUCs.

## Measurement accounting

Across the 24 targets, one source plate contains **208 target-dose nodes**: 22 drugs have nine doses, while LCL161 and SN-38 have five. Across p1+p2 that is **416 source treatment measurements per sample**.

One frozen DosePilot deployment purchases **64 measurements**, exactly **32 from p1 and 32 from p2**. That is **15.38%** of the full source treatment-measurement count. This percentage is measurement-count compression only; it is **not** a claim of the same percentage reduction in laboratory cost, time, controls, or chip resources.

## The 24 frozen targets

Boundary interpolation says whether the AUC integration bound is between source dose nodes rather than exactly on one.

| Target | Full source doses (nM) | AUC interval (nM) | Frozen predictor doses (nM) | Boundary interpolation |
|---|---|---|---|---|
| 5-FU | 1, 3, 1E+1, 3E+1, 1E+2, 3E+2, 1E+3, 3E+3, 1E+4 | 3E+1 to 1E+4 | 1E+3, 3E+3 | none |
| AZD7762 | 0.1, 0.3, 1, 3, 1E+1, 3E+1, 1E+2, 3E+2, 1E+3 | 3 to 1E+3 | 1E+2, 3E+2 | none |
| Afatinib | 0.1, 0.3, 1, 3, 1E+1, 3E+1, 1E+2, 3E+2, 1E+3 | 0.3 to 1E+3 | 1E+1, 1E+2, 3E+2 | none |
| Alisertib | 1, 3, 1E+1, 3E+1, 1E+2, 3E+2, 1E+3, 3E+3, 1E+4 | 3 to 1E+4 | 1E+2, 1E+3, 1E+4 | none |
| Atorvastatin | 1, 3, 1E+1, 3E+1, 1E+2, 3E+2, 1E+3, 3E+3, 1E+4 | 3E+1 to 1E+4 | 3E+2, 1E+3, 3E+3 | none |
| Bemcentinib | 1, 3, 1E+1, 3E+1, 1E+2, 3E+2, 1E+3, 3E+3, 1E+4 | 1E+1 to 1E+4 | 3E+2, 3E+3 | none |
| Encorafenib | 0.1, 0.3, 1, 3, 1E+1, 3E+1, 1E+2, 3E+2, 1E+3 | 0.3 to 1E+3 | 3E+1, 3E+2 | none |
| Gedatolisib | 0.1, 0.3, 1, 3, 1E+1, 3E+1, 1E+2, 3E+2, 1E+3 | 2.5 to 1E+3 | 3E+1, 1E+2, 3E+2 | lower |
| Gemcitabine | 0.1, 0.3, 1, 3, 1E+1, 3E+1, 1E+2, 3E+2, 1E+3 | 0.3 to 1E+3 | 1E+1, 1E+2, 3E+2 | none |
| Idasanutlin | 1, 3, 1E+1, 3E+1, 1E+2, 3E+2, 1E+3, 3E+3, 1E+4 | 3 to 1E+4 | 3E+2, 1E+3, 3E+3 | none |
| LCL161 | 2.5, 7.5, 2.5E+2, 7.5E+2, 2.5E+4 | 7.5 to 2.5E+4 | 2.5E+2, 7.5E+2, 2.5E+4 | none |
| LGK974 | 1, 3, 1E+1, 3E+1, 1E+2, 3E+2, 1E+3, 3E+3, 1E+4 | 3 to 1E+4 | 1E+1, 1E+3, 3E+3 | none |
| Lapatinib | 0.1, 0.3, 1, 3, 1E+1, 3E+1, 1E+2, 3E+2, 1E+3 | 3 to 1E+3 | 3E+1, 1E+2, 3E+2 | none |
| Luminespib | 0.1, 0.3, 1, 3, 1E+1, 3E+1, 1E+2, 3E+2, 1E+3 | 0.3 to 1E+3 | 1E+1, 3E+1, 3E+2 | none |
| Methotrexate | 0.5, 1.5, 5, 15, 5E+1, 1.5E+2, 5E+2, 1.5E+3, 5E+3 | 1.5 to 5E+3 | 1.5E+2, 5E+2, 1.5E+3 | none |
| Napabucasin | 2, 6, 2E+1, 6E+1, 2E+2, 6E+2, 2E+3, 6E+3, 2E+4 | 6 to 2E+4 | 6E+2, 2E+3 | none |
| Palbociclib | 1, 3, 1E+1, 3E+1, 1E+2, 3E+2, 1E+3, 3E+3, 1E+4 | 15 to 1E+4 | 3E+2, 1E+3, 3E+3 | lower |
| Panobinostat | 0.1, 0.3, 1, 3, 1E+1, 3E+1, 1E+2, 3E+2, 1E+3 | 3 to 1E+3 | 1E+1, 3E+1, 1E+2 | none |
| Pevonedistat | 1, 3, 1E+1, 3E+1, 1E+2, 3E+2, 1E+3, 3E+3, 1E+4 | 3 to 1E+4 | 3E+2, 1E+3 | none |
| Regorafenib | 1, 3, 1E+1, 3E+1, 1E+2, 3E+2, 1E+3, 3E+3, 1E+4 | 3E+1 to 1E+4 | 3E+2, 3E+3 | none |
| SN-38 | 1, 3, 1E+2, 3E+2, 1E+4 | 1 to 3E+3 | 3, 1E+2, 3E+2 | upper |
| TAS-102 | 1, 3, 1E+1, 3E+1, 1E+2, 3E+2, 1E+3, 3E+3, 1E+4 | 31.25 to 1E+4 | 1E+2, 1E+3, 1E+4 | lower |
| Trametinib | 0.025, 0.075, 0.25, 0.75, 2.5, 7.5, 25, 75, 2.5E+2 | 0.075 to 2.5E+2 | 2.5, 7.5, 75 | none |
| Volasertib | 0.1, 0.3, 1, 3, 1E+1, 3E+1, 1E+2, 3E+2, 1E+3 | 0.3 to 1E+3 | 1E+1, 1E+2 | none |

Four targets use one interpolated integration boundary:

- **Gedatolisib:** lower bound 2.5 nM lies between 1 and 3 nM.
- **Palbociclib:** lower bound 15 nM lies between 10 and 30 nM.
- **TAS-102:** lower bound 31.25 nM lies between 30 and 100 nM.
- **SN-38:** upper bound 3000 nM lies between 300 and 10000 nM.

The exact dose-only quadrature weights for all 24 targets are recorded in evidence/target_definitions_20261003.json. For every target those nonnegative weights sum to 1.

## What the predictor actually receives

The final bandwidth-0.7 model keeps the frozen 64-treatment acquisition schedule. For each selected drug+dose identity, orientation A chooses one of the two source plates and orientation B chooses the complementary plate. The model receives the **64 raw purchased normalized-viability values from one orientation only**.

It does **not** receive:

- the unpurchased full curves;
- the 24 target AUCs;
- the other orientation's purchased values;
- a 128-well A+B ensemble;
- Protected22/Lib2 responses.

The public frozen A/B schedules in evidence/frozen_bandwidth_orientation_A_plan_20261003.json and evidence/frozen_bandwidth_orientation_B_plan_20261003.json bind every selected target, dose, source plate, and position.

## Reproduce this definition from the public TRAIN route

After reconstructing the authenticated train_curves.csv described in docs/PUBLIC_REPRODUCTION.md:

    python study/audits/reproduce_target_definitions.py       --curves reconstructed_train/train_curves.csv       --output reproduced_target_definitions.json

The script verifies the pinned TRAIN bytes and identities, derives each drug's dose grid, confirms that the same grid exists for every sample and both plates, reconstructs the target-only quadrature from dose metadata, and binds the selected predictor inputs to the frozen A/B plans.

**It deliberately performs zero numerical conversions of the viability field.** It is a target-definition/measurement-contract reconstruction, not a new accuracy analysis.

For a response-free repository audit, run:

    python study/audits/verify_target_definitions.py --root .

That verifier checks the committed target metadata, integration arithmetic, 24-target coverage, 416-measurement full-profile accounting, 64 / 32+32 frozen predictor budget, A/B complementarity, and the table above.

## Scope

This definition is fixed for the reported Lib1 development evidence. It does not make the endpoint clinically validated. A future prospective organ-on-chip study must use a prespecified reference assay and decide before collection whether this same endpoint remains scientifically appropriate; see docs/PROSPECTIVE_OOC_VALIDATION_CONTRACT.md.
